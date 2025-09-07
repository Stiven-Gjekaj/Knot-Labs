import json
import os
from Mesh.tools.gen_videos import make_video, save_video, load_master_categories


def test_load_master_categories(tmp_path):
    p = os.path.join(tmp_path, 'master.txt')
    with open(p, 'w', encoding='utf-8') as f:
        f.write('a video about cats | a photo of cats\n')
        f.write('a video about dogs | a photo of dogs\n')
    cats = load_master_categories(p)
    assert 'cats' in cats and 'dogs' in cats


def test_make_video_and_save(tmp_path):
    post = make_video('creator123', ['cats', 'dogs', 'birds'])
    assert post['creator'] == 'creator123'
    assert 'Category' in post and isinstance(post['Category'], dict)
    assert len(post['Category']['micro']) <= 5
    out = save_video(post, str(tmp_path))
    data = json.load(open(out, 'r', encoding='utf-8'))
    assert data['postID'] == post['postID']
