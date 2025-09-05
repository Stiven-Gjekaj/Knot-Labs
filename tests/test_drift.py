from drift import Drift


def test_rank_orders():
    posts = {
        "a": {"likes": 1, "comments": 0, "shares": 0, "gifts": 0},
        "b": {"likes": 0, "comments": 1, "shares": 0, "gifts": 0},
    }
    d = Drift()
    ranked = d.rank(posts)
    assert ranked[0][0] == "b"
