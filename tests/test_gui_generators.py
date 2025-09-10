import os
import tkinter as tk
import pytest


def test_gui_generators_smoke(tmp_path, monkeypatch):
    # Work in a temp cwd so GUI writes under tmp_path/Mesh
    monkeypatch.chdir(tmp_path)

    import gui_demo as gui

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk not available in headless environment")
    root.withdraw()
    try:
        app = gui.App(root)
        # Generate users (random genders)
        app.gen_users_n.delete(0, tk.END)
        app.gen_users_n.insert(0, "2")
        app.on_gen_users()
        users_dir = os.path.join("Mesh", "Users")
        assert os.path.isdir(users_dir)
        assert len([n for n in os.listdir(users_dir) if n.endswith('.json')]) >= 2

        # Generate posts (using any creator id present)
        files = [n for n in os.listdir(users_dir) if n.endswith('.json')]
        creator_id = files[0].split('.')[0]
        app.gen_posts_n.delete(0, tk.END)
        app.gen_posts_n.insert(0, "3")
        app.on_gen_posts()
        posts_dir = os.path.join("Mesh", "Posts")
        assert os.path.isdir(posts_dir)
        assert len([n for n in os.listdir(posts_dir) if n.endswith('.json')]) >= 3
    finally:
        root.destroy()
