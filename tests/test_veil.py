from veil import Veil


def test_classify_returns_three():
    v = Veil()
    tags = v.classify("funny_video.mp4")
    assert len(tags) == 3


def test_classify_keyword_logic():
    v = Veil()
    tags = v.classify("soccer_highlights.mp4")
    assert "sports" in tags
