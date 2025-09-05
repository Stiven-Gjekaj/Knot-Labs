"""Simple PySimpleGUI wrapper around CLI."""
from __future__ import annotations

from pathlib import Path

import PySimpleGUI as sg  # type: ignore

from demo import CLI


def main():
    root = Path(__file__).resolve().parent
    cli = CLI(root)
    layout = [
        [sg.Multiline(size=(80, 20), key="-OUT-")],
        [sg.Input(key="-IN-")],
        [sg.Button("Run"), sg.Button("Clear"), sg.Button("Exit")],
    ]
    window = sg.Window("Knot", layout, finalize=True)
    out = window["-OUT-"]
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, "Exit"):
            break
        if event == "Clear":
            out.update("")
            continue
        if event == "Run":
            line = values["-IN-"]
            if line.strip().lower() in {"exit", "quit"}:
                break
            cli.run(line.split())
            out.update(out.get() + "\n", append=False)
    window.close()


if __name__ == "__main__":
    main()
