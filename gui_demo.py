#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import threading
try:
    import PySimpleGUI as sg  # type: ignore
except Exception as _e:  # pragma: no cover
    print(
        "PySimpleGUI failed to import. Please reinstall from the private index:\n"
        "  python -m pip uninstall -y PySimpleGUI\n"
        "  python -m pip cache purge\n"
        "  python -m pip install --force-reinstall --extra-index-url https://PySimpleGUI.net/install PySimpleGUI\n"
        "(Use 'python3' on macOS/Linux.)\n"
        f"Details: {_e}"
    )
    raise SystemExit(1)

# Validate the installed PySimpleGUI provides the expected API
if not hasattr(sg, "Window"):
    print(
        "PySimpleGUI installed does not provide Window(). Reinstall from the private index:\n"
        "  python -m pip uninstall -y PySimpleGUI\n"
        "  python -m pip cache purge\n"
        "  python -m pip install --force-reinstall --extra-index-url https://PySimpleGUI.net/install PySimpleGUI\n"
        "(Use 'python3' on macOS/Linux.)"
    )
    raise SystemExit(1)
from typing import Optional

import demo as core
from Scribe.search import build_index


def _ensure_paths_on_sys_path() -> None:
    # Ensure Veil src path is available for subprocess calls that rely on environment
    root = os.path.dirname(os.path.abspath(__file__))
    veil_src = os.path.join(root, 'Veil', 'src')
    if os.path.isdir(veil_src) and veil_src not in (os.environ.get('PYTHONPATH','').split(os.pathsep)):
        os.environ['PYTHONPATH'] = veil_src + os.pathsep + os.environ.get('PYTHONPATH','')


def _notify(window: sg.Window, text: str) -> None:
    window['-LOG-'].print(text)


def create_layout() -> list:
    return [
        [sg.Text('Knot-Labs GUI')],
        [sg.Frame('Create User', [
            [sg.Text('Username'), sg.Input(key='-USER-NAME-'), sg.Button('Create User')]
        ])],
        [sg.Frame('Create Post + Analyze', [
            [sg.Text('Creator (userID or username)'), sg.Input(key='-CREATOR-ID-')],
            [sg.Text('Media File'), sg.Input(key='-MEDIA-'), sg.FileBrowse()],
            [sg.Button('Post & Analyze')]
        ])],
        [sg.Frame('Interact', [
            [sg.Text('Viewer'), sg.Input(key='-VIEWER-ID-'), sg.Text('Creator'), sg.Input(key='-AUTHOR-ID-'), sg.Text('PostID'), sg.Input(key='-POST-ID-')],
            [sg.Button('Like'), sg.Button('Comment'), sg.Button('Share'), sg.Text('Gift Amount'), sg.Input(key='-GIFT-AMT-', size=(8,1)), sg.Button('Gift')]
        ])],
        [sg.Frame('Rank', [
            [sg.Text('Active User'), sg.Input(key='-ACTIVE-')], sg.Button('Rank Top 20')
        ])],
        [sg.Frame('Search', [
            [sg.Text('Query'), sg.Input(key='-SEARCH-Q-'), sg.Text('Top K'), sg.Input(key='-SEARCH-K-', size=(6,1))],
            [sg.Button('Search')]
        ])],
        [sg.Frame('Simulate', [
            [sg.Button('Simulate Interactions')]
        ])],
        [sg.Multiline(key='-LOG-', size=(100, 20), autoscroll=True, reroute_stdout=True, reroute_stderr=True)],
        [sg.Button('Quit')]
    ]


def main() -> None:
    _ensure_paths_on_sys_path()
    core._ensure_dirs()

    window = sg.Window('Knot-Labs GUI', create_layout(), finalize=True)

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Quit'):
            break
        try:
            if event == 'Create User':
                user = core.create_test_user(values.get('-USER-NAME-') or None)
                _notify(window, f"Created user: {user.get('userID')}")

            elif event == 'Post & Analyze':
                creator = values.get('-CREATOR-ID-') or ''
                media = values.get('-MEDIA-') or ''
                if not os.path.isfile(media):
                    _notify(window, 'Select a valid media file')
                    continue
                post = core.post_and_classify(creator, media)
                if post:
                    _notify(window, f"Created post {post.get('postID')} with cats: {post.get('Categories')}")
                else:
                    _notify(window, 'Post creation failed (check creator)')

            elif event in ('Like', 'Comment', 'Share', 'Gift'):
                viewer = values.get('-VIEWER-ID-') or ''
                author = values.get('-AUTHOR-ID-') or ''
                postid = values.get('-POST-ID-') or ''
                if event == 'Like':
                    core.like_post(viewer, author, postid)
                    _notify(window, 'Applied Like')
                elif event == 'Comment':
                    core.comment_post(viewer, author, postid)
                    _notify(window, 'Applied Comment')
                elif event == 'Share':
                    core.share_post(viewer, author, postid)
                    _notify(window, 'Applied Share')
                elif event == 'Gift':
                    try:
                        amt = float(values.get('-GIFT-AMT-', '1') or '1')
                    except Exception:
                        amt = 1.0
                    core.gift_post(viewer, author, postid, amt)
                    _notify(window, f'Applied Gift ({amt})')

            elif event == 'Rank Top 20':
                active = values.get('-ACTIVE-') or ''
                out = core.rank_for_user(active)
                if out:
                    _notify(window, 'Top 20:')
                    for pid, sc in out[:20]:
                        _notify(window, f"  {pid} | score={sc}")
                else:
                    _notify(window, 'No ranking results for user')

            elif event == 'Simulate Interactions':
                # Run simulation in a worker to keep UI responsive
                def run_sim():
                    core.simulate_update()
                    _notify(window, 'Simulation complete.')
                threading.Thread(target=run_sim, daemon=True).start()

            elif event == 'Search':
                q = values.get('-SEARCH-Q-') or ''
                try:
                    k = int(values.get('-SEARCH-K-', '10') or '10')
                except Exception:
                    k = 10
                if not q.strip():
                    _notify(window, 'Enter a query')
                    continue
                try:
                    idx = build_index(core.POSTS_DIR, backend='bow')
                    res = idx.search(q, k=k)
                    _notify(window, f"Search results ({len(res)}):")
                    for pid, sc in res:
                        _notify(window, f"  {pid} | score={sc:.3f}")
                except Exception as e:
                    _notify(window, f"Search failed: {e}")

        except Exception as e:
            _notify(window, f"Error: {e}")

    window.close()


if __name__ == '__main__':
    main()
