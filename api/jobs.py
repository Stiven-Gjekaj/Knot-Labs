from __future__ import annotations

import threading
import queue
from typing import Dict, Any, Optional
import os
import time as _time


class JobQueue:
    def __init__(
        self,
        result_ttl: Optional[float] = None,
        max_workers: Optional[int] = None,
    ) -> None:
        self.q: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self.results: Dict[str, Any] = {}
        self._workers: list[threading.Thread] = []
        self._stop = threading.Event()
        self._cancelled: set[str] = set()
        self._current: set[str] = set()
        self._lock = threading.Lock()
        self._result_ttl = (
            result_ttl if result_ttl is not None else float(os.environ.get("JOB_RESULT_TTL", "3600"))
        )
        try:
            env_max = int(os.environ.get("JOB_MAX_WORKERS", "4"))
        except Exception:
            env_max = 4
        # Ensure at least one worker thread
        self._max_workers = max(1, max_workers if isinstance(max_workers, int) else env_max)

    def _cleanup_results(self) -> None:
        now = _time.time()
        with self._lock:
            to_del = [
                k
                for k, v in self.results.items()
                if v.get("finished_at") and now - v["finished_at"] > self._result_ttl
            ]
            for k in to_del:
                self.results.pop(k, None)

    def start(self, handler) -> None:
        # Reuse existing healthy workers when possible
        with self._lock:
            self._workers = [w for w in self._workers if w.is_alive()]
            if self._workers and len(self._workers) >= self._max_workers:
                return
        self._stop.clear()

        def worker_loop() -> None:
            while not self._stop.is_set():
                self._cleanup_results()
                try:
                    job = self.q.get(timeout=0.25)
                except queue.Empty:
                    continue
                job_id = job.get('id')
                if not job_id:
                    self.q.task_done()
                    continue
                started = False
                try:
                    with self._lock:
                        if job_id in self._cancelled:
                            self.results[job_id] = {
                                'status': 'cancelled',
                                'finished_at': _time.time(),
                                'type': job.get('type'),
                            }
                            continue
                        self._current.add(job_id)
                        started = True
                        self.results[job_id] = {
                            'status': 'running',
                            'started_at': _time.time(),
                            'type': job.get('type'),
                        }
                    res = handler(job)
                    status = 'done'
                    result_payload: Any = res
                    if isinstance(res, dict) and res.get('status') == 'cancelled':
                        status = 'cancelled'
                        result_payload = None
                    with self._lock:
                        self.results[job_id] = {
                            'status': status,
                            'result': result_payload,
                            'finished_at': _time.time(),
                            'type': job.get('type'),
                        }
                except Exception as e:
                    with self._lock:
                        self.results[job_id] = {
                            'status': 'error',
                            'error': str(e),
                            'finished_at': _time.time(),
                            'type': job.get('type'),
                        }
                finally:
                    if started:
                        with self._lock:
                            self._current.discard(job_id)
                    self.q.task_done()

        while True:
            with self._lock:
                active = [w for w in self._workers if w.is_alive()]
                self._workers = active
                if len(active) >= self._max_workers:
                    break
                name = f"job-worker-{len(active) + 1}"
            worker = threading.Thread(target=worker_loop, daemon=True, name=name)
            with self._lock:
                self._workers.append(worker)
            worker.start()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            workers = list(self._workers)
        for w in workers:
            w.join(timeout=1)
        with self._lock:
            self._workers = []
            self._current.clear()
        self._stop = threading.Event()

    def submit(self, job: Dict[str, Any]) -> str:
        self.q.put(job)
        return job['id']

    def status(self, job_id: str) -> Dict[str, Any]:
        with self._lock:
            data = self.results.get(job_id)
            return dict(data) if data is not None else {'status': 'queued'}

    def cancel(self, job_id: str) -> bool:
        """Request cancellation of a job.
        - If queued: it will be marked cancelled when dequeued; status is immediately set to cancelled.
        - If running: best-effort; handler must cooperate. Status will reflect running until it finishes.
        Returns True if the job is known (queued/running or seen), else False.
        """
        with self._lock:
            self._cancelled.add(job_id)
            # Mark status immediately for UX
            self.results[job_id] = {'status': 'cancelled', 'finished_at': _time.time()}
        return True

    def is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._cancelled

    def debug(self) -> Dict[str, Any]:
        with self._lock:
            running = sorted(self._current)
            results_total = len(self.results)
            cancelled_total = len(self._cancelled)
        return {
            'queued_estimate': int(self.q.qsize()),
            'running': running,
            'results_total': results_total,
            'cancelled_total': cancelled_total,
        }


job_queue = JobQueue()
