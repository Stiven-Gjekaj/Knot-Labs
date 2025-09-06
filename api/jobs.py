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
                    res = handler(job)
                    self.results[job_id] = {'status': 'done', 'result': res}
                except Exception as e:
                    self.results[job_id] = {'status': 'error', 'error': str(e)}
                finally:
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


job_queue = JobQueue()

