from pathlib import Path

# Expose modules from Veil/src/veil without requiring PYTHONPATH tweaks
_pkg = Path(__file__).resolve().parent.parent / 'Veil' / 'src' / 'veil'
if _pkg.is_dir():
    __path__.append(str(_pkg))  # type: ignore[name-defined]
