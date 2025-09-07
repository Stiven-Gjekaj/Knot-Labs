import os
import tkinter as tk


def test_gui_generators_smoke(tmp_path, monkeypatch):
    # Work in a temp cwd so GUI writes under tmp_path/Mesh
    monkeypatch.chdir(tmp_path)

    import gui_demo as gui

    root = tk.Tk()
    root.withdraw()
    try:
        app = gui.App(root)
        # Generate users
        app.gen_users_n.delete(0, tk.END)
        app.gen_users_n.insert(0, "2")
        app.gen_users_gender.set("female")
        app.on_gen_users()
        users_dir = os.path.join("Mesh", "Users")
        assert os.path.isdir(users_dir)
        assert len([n for n in os.listdir(users_dir) if n.endswith('.json')]) >= 2

        # Generate posts (using any creator id present)
        # Pick one created user id from file name
        files = [n for n in os.listdir(users_dir) if n.endswith('.json')]
        creator_id = files[0].split('.')[0]
        app.gen_posts_n.delete(0, tk.END)
        app.gen_posts_n.insert(0, "3")
        app.gen_posts_creator.insert(0, creator_id)
        app.gen_posts_country.set("US")
        app.on_gen_posts()
        posts_dir = os.path.join("Mesh", "Posts")
        assert os.path.isdir(posts_dir)
        assert len([n for n in os.listdir(posts_dir) if n.endswith('.json')]) >= 3
    finally:
        root.destroy()

