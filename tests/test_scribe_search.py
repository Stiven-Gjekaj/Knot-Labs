import json
import os
from Scribe.search import build_index


def test_build_and_search_bow(tmp_path):
    posts_dir = tmp_path / 'Posts'
    posts_dir.mkdir()
    with open(posts_dir / 'p1.json', 'w', encoding='utf-8') as f:
        json.dump({
            'postID': 'p1',
            'description': 'Funny cats playing and jumping',
            'Category': { 'macro': 'cats', 'meso': 'pets', 'micro': ['cats', 'pets'] }
        }, f)
    with open(posts_dir / 'p2.json', 'w', encoding='utf-8') as f:
        json.dump({
            'postID': 'p2',
            'description': 'Delicious recipes and cooking tips',
            'Category': { 'macro': 'food', 'meso': 'recipes', 'micro': ['food', 'recipes'] }
        }, f)

    idx = build_index(str(posts_dir), backend='bow')
    res = idx.search('cats', k=5)
    assert res and res[0][0] == 'p1'
