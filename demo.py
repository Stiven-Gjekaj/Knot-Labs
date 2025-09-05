"""Interactive demo tying Mesh, Veil, Scribe and Drift together."""
from pathlib import Path
import shlex
import uuid
from typing import Callable, Dict
import sys

# Allow imports from component directories
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "Knot-Mesh"))
sys.path.insert(0, str(ROOT / "Knot-Veil"))
sys.path.insert(0, str(ROOT / "Knot-Scribe"))
sys.path.insert(0, str(ROOT / "Knot-Drift"))

from mesh import Mesh
from veil import Veil
from scribe import Scribe
from drift import Drift

mesh: Mesh
veil: Veil
scribe: Scribe
drift: Drift
COMMANDS: Dict[str, Callable]
DATA_DIR = Path("Knot-Mesh/data")


def show_commands() -> None:
    """Display available commands."""
    print("Available commands:")
    for name in sorted(COMMANDS):
        print(f"  {name}")
    print("  exit")


def post(path: str) -> None:
    pid = mesh.create_post(path, veil=veil)
    post = mesh.get_post(pid)
    print(f"Posted {pid} with tags {post['tags']}")


def like(pid: str) -> None:
    mesh.increment(pid, "likes")
    print(f"Liked {pid}")


def comment(pid: str) -> None:
    mesh.increment(pid, "comments")
    print(f"Commented on {pid}")


def gift(pid: str) -> None:
    mesh.increment(pid, "gifts")
    print(f"Gifted {pid}")


def share(pid: str) -> None:
    mesh.increment(pid, "shares")
    print(f"Shared {pid}")


def rank(n: int) -> None:
    ranked = drift.rank(mesh.all_posts(), algorithm="simple")[:n]
    for pid, post, score in ranked:
        print(f"{pid} score={score} tags={post['tags']}")


def feed(n: int) -> None:
    ranked = drift.rank(mesh.all_posts(), algorithm="feedback")[:n]
    for pid, post, score in ranked:
        print(f"{pid} score={score} tags={post['tags']}")


def search(query: str) -> None:
    results = scribe.search(query)
    ranked = drift.rank(dict(results))
    for pid, post, score in ranked:
        print(f"{pid} score={score} tags={post['tags']}")


def populate_users(n: int) -> None:
    users_dir = DATA_DIR / "Users"
    users_dir.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        name = f"user{i+1}"
        mesh.add_user(name)
        (users_dir / f"{name}.json").touch()
    print(f"Added {n} users")


def populate_posts(n: int) -> None:
    posts_dir = DATA_DIR / "Posts"
    posts_dir.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        path = posts_dir / f"sample_video_{i+1}.mp4"
        path.touch()
        mesh.create_post(str(path), veil=veil)
    print(f"Added {n} videos")


def populate_categories(n: int) -> None:
    categories_dir = DATA_DIR / "categories"
    categories_dir.mkdir(parents=True, exist_ok=True)
    selected = Veil.DEFAULT_CATEGORIES[:n]
    with open(categories_dir / "mastercategories.txt", "w", encoding="utf-8") as f:
        for cat in selected:
            f.write(f"a video about {cat} | a photo of {cat}\n")
    veil.categories = selected
    print(f"Loaded {n} categories")


def setup(user_id: str) -> None:
    """Initialise module globals for a demo session."""
    global mesh, veil, scribe, drift, COMMANDS

    DATA_DIR.mkdir(exist_ok=True)
    mesh = Mesh(path=str(DATA_DIR / f"mesh_data_{user_id}.json"))
    veil = Veil()
    scribe = Scribe(mesh)
    drift = Drift()

    COMMANDS = {
        "post": lambda args: post(args[0]),
        "like": lambda args: like(args[0]),
        "comment": lambda args: comment(args[0]),
        "gift": lambda args: gift(args[0]),
        "share": lambda args: share(args[0]),
        "rank": lambda args: rank(int(args[0])),
        "feed": lambda args: feed(int(args[0])),
        "search": lambda args: search(" ".join(args)),
        "populate_users": lambda args: populate_users(int(args[0])),
        "populate_posts": lambda args: populate_posts(int(args[0])),
        "populate_categories": lambda args: populate_categories(int(args[0])),
        "help": lambda args: show_commands(),
    }


def main() -> None:
    """Simple REPL to interact with the system."""
    user_id = str(uuid.uuid4())
    setup(user_id)
    mesh.add_user(f"user_{user_id}", uid=user_id)
    print(f"userID {user_id}")
    show_commands()

    while True:
        try:
            line = input("\n> ")
        except (EOFError, KeyboardInterrupt):
            break
        parts = shlex.split(line)
        if not parts:
            continue
        if parts[0] in {"exit", "quit"}:
            break
        cmd, *args = parts
        func = COMMANDS.get(cmd)
        if func:
            try:
                func(args)
            except Exception as exc:  # pragma: no cover - demo only
                print(f"Error: {exc}")
        else:
            print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
