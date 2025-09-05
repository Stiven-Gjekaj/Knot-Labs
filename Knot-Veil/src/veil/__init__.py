"""Veil package."""

__all__ = ["__version__", "main"]
__version__ = "0.1.0"


def main() -> None:
    """Entry point for the legacy CLI.

    Importing ``classify_veil`` lazily avoids importing heavy optional
    dependencies (Whisper, TensorFlow) when simply importing :mod:`veil` or
    using the newer :mod:`veil.run` module.
    """
    from .classify_veil import main as _main

    _main()
