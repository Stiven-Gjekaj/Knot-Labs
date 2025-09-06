PY=python

.PHONY: install test demo gui labels cli psg-reinstall gui-fix

install:
	$(PY) -m pip install -r requirements.txt

test:
	pytest -q

demo:
	$(PY) demo.py

gui:
	$(PY) gui_demo.py

labels:
	$(PY) Mesh/tools/build_mastercategories.py

cli:
	$(PY) cli_demo.py --help

psg-reinstall:
	-$(PY) -m pip uninstall -y PySimpleGUI
	-$(PY) -m pip cache purge
	$(PY) -m pip install --force-reinstall --extra-index-url https://PySimpleGUI.net/install PySimpleGUI

gui-fix:
	$(PY) scripts/reinstall_pysimplegui.py
