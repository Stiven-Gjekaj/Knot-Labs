import os
import json
import demo


def test_apply_action_to_post_like():
    post = {
        'likesCount': 0,
        'commentsCount': 0,
        'shareCount': 0,
        'giftsCount': 0,
        'payPerViewCount': 0,
        'Score': 0.0,
    }
    out = demo._apply_action_to_post(post, 'like')
    assert out['likesCount'] == 1
    assert out['Score'] >= 1.0


def test_bump_user_after_action_basic():
    viewer = {'ViewerScore': {}, 'CategoryScores': {}, 'RecentCreators': []}
    creator = {'userID': 'c1', 'CreatorScore': 0}
    categories = ['cats', 'dogs']
    v, c = demo._bump_user_after_action(viewer, creator, categories, 2, 3)
    assert v['ViewerScore']['c1'] >= 2
    assert v['CategoryScores']['cats'] >= 1
    assert c['CreatorScore'] >= 3


def test_to_category_parser_and_fallback(tmp_path, monkeypatch):
    # Expose helper by importing function indirectly via demo module
    # Create a small master file
    master = os.path.join(tmp_path, 'master.txt')
    with open(master, 'w', encoding='utf-8') as f:
        f.write('a video about cats | a photo of cats\n')
        f.write('a video about dogs | a photo of dogs\n')
        f.write('a video about birds | a photo of birds\n')
        f.write('a video about foxes | a photo of foxes\n')
        f.write('a video about bears | a photo of bears\n')

    # Patch MASTER_PATH
    monkeypatch.setattr(demo, 'MASTER_PATH', master)

    class FakeRes:
        def __init__(self, text):
            self.stdout = text
            self.stderr = ''

    def fake_run(cmd, capture_output, text, check, env):
        return FakeRes('Predictions: a video about birds, a photo of foxes')

    monkeypatch.setattr(demo.subprocess, 'run', fake_run)
    cats = demo._run_veil_and_get_categories('dummy.mp4', topk=5)
    # Should strip prompts and fill to 5 unique entries
    assert 'birds' in cats and 'foxes' in cats
    assert len(cats) == 5
