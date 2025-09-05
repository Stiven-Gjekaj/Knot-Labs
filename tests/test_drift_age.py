import time
from drift import Drift


def test_age_log_decay_and_filter():
    d = Drift()
    now = time.time()
    posts = {
        'fresh': {'likes': 10, 'comments': 0, 'shares': 0, 'gifts': 0, 'created_at': now},
        'mid': {'likes': 10, 'comments': 0, 'shares': 0, 'gifts': 0, 'created_at': now - 45 * 86400},
        'old': {'likes': 1000, 'comments': 0, 'shares': 0, 'gifts': 0, 'created_at': now - 91 * 86400},
    }
    ranked = d.rank(posts)
    ids = [pid for pid, _, _ in ranked]
    assert 'old' not in ids
    assert ids[0] == 'fresh'
    assert len(ranked) == 2
    assert ranked[1][2] < ranked[0][2]
