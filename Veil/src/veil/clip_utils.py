from functools import lru_cache
from typing import Any, Tuple, cast
import warnings
import clip as clip_lib  # type: ignore

# Silence type checker complaints for dynamically typed third-party module
clip = cast(Any, clip_lib)

try:  # Ensure we have OpenAI's tokenizer
    from clip import clip as _clip_submodule  # type: ignore
except Exception:  # pragma: no cover - defensive
    _clip_submodule = None

if not hasattr(clip, "_tokenizer") and (
    _clip_submodule is None or not hasattr(_clip_submodule, "_tokenizer")
):
    warnings.warn(
        "The installed 'clip' package lacks OpenAI's tokenizer; install it via "
        "'pip install git+https://github.com/openai/CLIP.git'",
        RuntimeWarning,
    )


@lru_cache(maxsize=None)
def get_clip_model(model_name: str, device: str = "cpu") -> Tuple[Any, Any]:
    """Load a CLIP model once and cache it for reuse.

    Parameters
    ----------
    model_name: str
        Name of the CLIP model to load.
    device: str
        Device on which to load the model.
    Returns
    -------
    Tuple[Any, Any]
        A tuple of (model, preprocess) as returned by ``clip.load``.
    """
    return clip.load(model_name, device=device)

