.PHONY: help venv install setup run clean check check-faiss check-ffmpeg

PY := $(if $(wildcard .venv/Scripts/python.exe),.venv/Scripts/python.exe,$(if $(wildcard .venv/bin/python),.venv/bin/python,python))

help:
	@echo "Targets:"
	@echo "  venv    - create .venv if missing"
	@echo "  install - upgrade pip and install -r requirements.txt"
	@echo "  setup   - venv + install"
	@echo "  run     - start uvicorn with .env"
	@echo "  clean   - remove .venv"
	@echo "  check   - verify FAISS and FFmpeg presence"

venv:
	@if [ ! -d .venv ]; then \
		python -m venv .venv; \
	fi

install:
	$(PY) -m pip install --upgrade pip
	@if [ -f requirements.txt ]; then \
		$(PY) -m pip install -r requirements.txt; \
	fi

setup: venv install

run:
	$(PY) -m uvicorn --env-file .env api.main:app --reload

clean:
	rm -rf .venv

check: check-faiss check-ffmpeg

check-faiss:
	@echo "[check] FAISS (optional)"
	@$(PY) -c "import importlib,sys; ok=importlib.util.find_spec('faiss') is not None; print('FAISS:', 'ok' if ok else 'missing'); sys.exit(0 if ok else 1)" \
	|| { echo "Hint: install CPU wheel via: pip install faiss-cpu (Linux/macOS) or use Conda on Windows: conda install -c pytorch faiss-cpu"; exit 1; }

check-ffmpeg:
	@echo "[check] FFmpeg"
	@ffmpeg -version >/dev/null 2>&1 && echo "FFmpeg: ok" \
	|| { echo "FFmpeg: missing"; echo "Install: Windows(choco): choco install ffmpeg; macOS: brew install ffmpeg; Debian/Ubuntu: sudo apt-get install -y ffmpeg"; exit 1; }
