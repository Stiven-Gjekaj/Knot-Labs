import threading
import time

from api.jobs import JobQueue


def test_jobqueue_cancel_before_run():
    q = JobQueue()
    ran = {}

    def handler(job):
        ran['called'] = True
        return 'ok'

    q.start(handler)
    job_id = 'j1'
    q.cancel(job_id)
    q.submit({'id': job_id, 'type': 'x'})
    time.sleep(0.3)
    status = q.status(job_id)
    q.stop()
    assert status['status'] == 'cancelled'
    assert 'called' not in ran


def test_jobqueue_result_ttl_cleanup():
    q = JobQueue(result_ttl=0.1)

    def handler(job):
        return 'ok'

    q.start(handler)
    job_id = q.submit({'id': 'j2', 'type': 'x'})
    # Wait for completion
    while q.status(job_id)['status'] in {'queued', 'running'}:
        time.sleep(0.05)
    assert job_id in q.results
    # Wait for TTL to expire and cleanup to run
    time.sleep(0.5)
    assert job_id not in q.results
    q.stop()


def test_jobqueue_runs_jobs_concurrently():
    q = JobQueue(max_workers=4)
    start_gate = threading.Event()
    all_started = threading.Event()
    lock = threading.Lock()
    started_ids: list[str] = []

    def handler(job):
        with lock:
            started_ids.append(job['id'])
            if len(started_ids) == 4:
                all_started.set()
        # wait until test signals to finish
        start_gate.wait(timeout=2)
        return 'ok'

    q.start(handler)
    for i in range(4):
        q.submit({'id': f'job{i}', 'type': 'x'})

    assert all_started.wait(timeout=2), f"expected 4 jobs to start, got {started_ids}"
    start_gate.set()

    for i in range(4):
        job_id = f'job{i}'
        while q.status(job_id)['status'] not in {'done', 'error', 'cancelled'}:
            time.sleep(0.05)

    q.stop()
