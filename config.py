from __future__ import annotations

import os
import pathlib


def repo_root() -> str:
    return str(pathlib.Path(__file__).resolve().parent)


def mesh_dir() -> str:
    return os.environ.get('MESH_DIR', os.path.join(repo_root(), 'Mesh'))


def users_dir() -> str:
    return os.path.join(mesh_dir(), 'Users')


def posts_dir() -> str:
    return os.path.join(mesh_dir(), 'Posts')


def master_path() -> str:
    return os.path.join(mesh_dir(), 'mastercategories.txt')


def veil_src_path() -> str:
    return os.path.join(repo_root(), 'Veil', 'src')

