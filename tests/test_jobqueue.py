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