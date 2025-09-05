"""Populate Mesh with sample users and videos."""
import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from mesh import Mesh
from veil import Veil


def generate(users: int, videos: int) -> None:
    mesh = Mesh()
    veil = Veil()
    for i in range(users):
        mesh.add_user(f"user{i+1}")
    for i in range(videos):
        path = f"sample_{i+1}.mp4"
        mesh.create_post(path, veil=veil)
    print(f"Generated {users} users and {videos} videos")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Populate Mesh with sample data")
    parser.add_argument("users", type=int, nargs="?", default=5)
    parser.add_argument("videos", type=int, nargs="?", default=5)
    args = parser.parse_args()
    generate(args.users, args.videos)
