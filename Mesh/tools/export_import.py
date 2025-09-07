#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from typing import Dict, Iterable


def _iter_json_files(dir_path: str) -> Iterable[str]:
    if not os.path.isdir(dir_path):
        return []
    for name in os.listdir(dir_path):
        if name.endswith('.json'):
            yield os.path.join(dir_path, name)


def export_ndjson(users_dir: str, posts_dir: str, out_path: str) -> None:
    with open(out_path, 'w', encoding='utf-8') as out:
        # Users
        for p in _iter_json_files(users_dir):
            try:
                data = json.load(open(p, 'r', encoding='utf-8'))
                out.write(json.dumps({'_type': 'user', **data}, ensure_ascii=False) + '\n')
            except Exception:
                continue
        # Posts
        for p in _iter_json_files(posts_dir):
            try:
                data = json.load(open(p, 'r', encoding='utf-8'))
                out.write(json.dumps({'_type': 'post', **data}, ensure_ascii=False) + '\n')
            except Exception:
                continue


def import_ndjson(in_path: str, users_dir: str, posts_dir: str) -> Dict[str, int]:
    os.makedirs(users_dir, exist_ok=True)
    os.makedirs(posts_dir, exist_ok=True)
    c_users = c_posts = 0
    seen_users = set(os.path.splitext(n)[0] for n in os.listdir(users_dir) if n.endswith('.json'))
    seen_posts = set(os.path.splitext(n)[0] for n in os.listdir(posts_dir) if n.endswith('.json'))
    for line in open(in_path, 'r', encoding='utf-8'):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get('_type') == 'user':
            uid = rec.get('userID')
            if not uid or uid in seen_users:
                continue
            path = os.path.join(users_dir, f'{uid}.json')
            json.dump(rec, open(path, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
            seen_users.add(uid)
            c_users += 1
        elif rec.get('_type') == 'post':
            pid = rec.get('postID')
            if not pid or pid in seen_posts:
                continue
            path = os.path.join(posts_dir, f'{pid}.json')
            json.dump(rec, open(path, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
            seen_posts.add(pid)
            c_posts += 1
    return {'users': c_users, 'posts': c_posts}


def main() -> None:
    p = argparse.ArgumentParser(description='Export/Import Mesh data as NDJSON')
    sub = p.add_subparsers(dest='cmd')
    pexp = sub.add_parser('export', help='export to NDJSON')
    pexp.add_argument('--users', default=os.path.join('Mesh', 'Users'))
    pexp.add_argument('--posts', default=os.path.join('Mesh', 'Posts'))
    pexp.add_argument('--out', required=True)
    pimp = sub.add_parser('import', help='import from NDJSON')
    pimp.add_argument('--in', dest='inp', required=True)
    pimp.add_argument('--users', default=os.path.join('Mesh', 'Users'))
    pimp.add_argument('--posts', default=os.path.join('Mesh', 'Posts'))
    args = p.parse_args()
    if args.cmd == 'export':
        export_ndjson(args.users, args.posts, args.out)
    elif args.cmd == 'import':
        stats = import_ndjson(args.inp, args.users, args.posts)
        print(json.dumps(stats))
    else:
        p.print_help()


if __name__ == '__main__':
    main()

