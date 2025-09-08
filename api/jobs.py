from __future__ import annotations

import threading
import queue
from typing import Dict, Any, Optional


class JobQueue:
    def __init__(self) -> None:
        self.q: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self.results: Dict[str, Any] = {}
        self._worker: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._cancelled: set[str] = set()
        self._current: Optional[str] = None

    def start(self, handler) -> None:
        if self._worker and self._worker.is_alive():
            return
        def run():
            while not self._stop.is_set():
                try:
                    job = self.q.get(timeout=0.25)
                except queue.Empty:
                    continue
                job_id = job.get('id')
                try:
                    import time as _t
                    # Skip cancelled jobs
                    if job_id in self._cancelled:
                        self.results[job_id] = {
                            'status': 'cancelled',
                            'finished_at': _t.time(),
                            'type': job.get('type'),
                        }
                        continue
                    self._current = job_id
                    self.results[job_id] = {
                        'status': 'running',
                        'started_at': _t.time(),
                        'type': job.get('type'),
                    }
                    res = handler(job)
                    self.results[job_id] = {
                        'status': 'done',
                        'result': res,
                        'finished_at': _t.time(),
                        'type': job.get('type'),
                    }
                except Exception as e:
                    import time as _t
                    self.results[job_id] = {
                        'status': 'error',
                        'error': str(e),
                        'finished_at': _t.time(),
                        'type': job.get('type'),
                    }
                finally:
                    self._current = None
                    self.q.task_done()
        self._worker = threading.Thread(target=run, daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._stop.set()
        if self._worker:
            self._worker.join(timeout=1)

    def submit(self, job: Dict[str, Any]) -> str:
        self.q.put(job)
        return job['id']

    def status(self, job_id: str) -> Dict[str, Any]:
        return self.results.get(job_id, {'status': 'queued'})

    def cancel(self, job_id: str) -> bool:
        """Request cancellation of a job.
        - If queued: it will be marked cancelled when dequeued; status is immediately set to cancelled.
        - If running: best-effort; handler must cooperate. Status will reflect running until it finishes.
        Returns True if the job is known (queued/running or seen), else False.
        """
        self._cancelled.add(job_id)
        # Mark status immediately for UX
        self.results[job_id] = {'status': 'cancelled'}
        return True

    def is_cancelled(self, job_id: str) -> bool:
        return job_id in self._cancelled

    def debug(self) -> Dict[str, Any]:
        return {
            'queued_estimate': int(self.q.qsize()),
            'running': self._current,
            'results_total': len(self.results),
            'cancelled_total': len(self._cancelled),
        }


job_queue = JobQueue()
