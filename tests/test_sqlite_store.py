import os
import sqlite3
from Mesh.sqlite_store import init_db, save_user, save_post


def test_sqlite_write(tmp_path):
    db = tmp_path / "knot.db"
    os.environ["KNOT_DB"] = str(db)
    init_db(str(db))
    # Save a user
    u = {"userID": "u1", "username": "alice", "Gender": "female", "created_at": 1.0}
    save_user(u, str(db))
    # Save a post
    p = {"postID": "p1", "creator": "u1", "Categories": ["cats"], "country": "US", "created_at": 2.0}
    save_post(p, str(db))
    # Verify rows
    con = sqlite3.connect(str(db))
    try:
        cur = con.cursor()
        cur.execute("select count(1) from users where userID=?", ("u1",))
        assert cur.fetchone()[0] == 1
        cur.execute("select count(1) from posts where postID=?", ("p1",))
        assert cur.fetchone()[0] == 1
    finally:
        con.close()

