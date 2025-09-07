PY=python

.PHONY: install test demo gui labels cli

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
