from typing import Any, Dict, List, Optional, cast
import os
import warnings
import tempfile
import contextlib
import wave
from functools import lru_cache
import numpy as np
import torch
import ffmpeg as ffmpeg_lib  # type: ignore
from faster_whisper import WhisperModel  # type: ignore
from .utils import normalize_tensor
from .clip_utils import clip, get_clip_model

# Silence type checker complaints for dynamically typed third-party modules
ffmpeg = cast(Any, ffmpeg_lib)


@lru_cache(maxsize=None)
def get_whisper_model(model_size: str) -> WhisperModel:
    """Load a faster-whisper model once and cache it for reuse."""
    device = "cpu"
    compute_type = "int8"
    return WhisperModel(model_size, device=device, compute_type=compute_type)


def _labels_look_like_prompts(categories: List[str]) -> bool:
    if not categories:
        return False
    first = categories[0].lower().strip()
    return first.startswith("a video ") or first.startswith("a photo ")


def _extract_wav_ffmpeg(inp: str, sr: int = 16000) -> tuple[str, int]:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    out = tmp.name
    tmp.close()
    try:
        (
            ffmpeg
            .input(inp)
            .output(out, acodec="pcm_s16le", ac=1, ar=sr, loglevel="error")
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return out, sr
    except Exception:
        # Clean up on failure
        try:
            if os.path.exists(out):
                os.unlink(out)
        except OSError:
            pass
        raise


def _read_wav_to_np(path: str) -> tuple[np.ndarray, int]:
    with contextlib.closing(wave.open(path, "rb")) as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        fr = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
    if sampwidth != 2:
        raise RuntimeError(f"Expected 16-bit PCM, got sample width {sampwidth}")
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if n_channels > 1:
        audio = audio.reshape(-1, n_channels).mean(axis=1)
    return audio, fr


def classify_audio_yamnet(video_path: str, topk: int = 3) -> List[tuple[str, float]]:
    """Classify audio events in *video_path* using YAMNet.

    Returns a list of ``(label, score)`` pairs for the top *topk* classes.
    If TensorFlow or the YAMNet model is unavailable the function returns an
    empty list and issues a warning.
    """
    try:  # Import TensorFlow lazily so installs without TF still work
        import tensorflow as tf  # type: ignore
        import tensorflow_hub as hub  # type: ignore
    except Exception:  # pragma: no cover - depends on optional deps
        warnings.warn("TensorFlow not available; YAMNet classification skipped.")
        return []

    wav_path = None
    try:
        wav_path, sr = _extract_wav_ffmpeg(video_path, sr=16000)
        waveform, sr = _read_wav_to_np(wav_path)
        model = hub.load("https://tfhub.dev/google/yamnet/1")
        scores, _, _ = model(waveform)
        scores = scores.numpy().mean(axis=0)
        class_map_path = model.class_map_path().numpy().decode("utf-8")
        with open(class_map_path, "r", encoding="utf-8") as f:
            class_names = [c.strip() for c in f.readlines()]
        top_idx = scores.argsort()[::-1][:topk]
        return [(class_names[i], float(scores[i])) for i in top_idx]
    except Exception as e:  # pragma: no cover - runtime warning only
        warnings.warn(f"YAMNet classification failed ({e!r}); returning empty results.")
        return []
    finally:
        if wav_path and os.path.exists(wav_path):
            try:
                os.unlink(wav_path)
            except OSError:
                pass


def transcribe_audio(video_path, model_size="small"):
    """Transcribe audio from a video (or fallback WAV) using faster-whisper.

    This CPU-only implementation always uses int8 inference.
    """
    model = get_whisper_model(model_size)

    try:
        # Try direct path (let faster-whisper open the media)
        segments, _ = model.transcribe(video_path)
        text = " ".join(seg.text.strip() for seg in segments)
        return text
    except Exception:
        # Fallback: extract WAV via ffmpeg, transcribe raw PCM
        wav_path = None
        try:
            wav_path, sr = _extract_wav_ffmpeg(video_path, sr=16000)
            audio, sr = _read_wav_to_np(wav_path)
            segments, _ = model.transcribe(audio, sampling_rate=sr)
            text = " ".join(seg.text.strip() for seg in segments)
            return text
        except Exception as e2:
            warnings.warn(f"Audio decode/transcription failed ({e2!r}); continuing with empty transcript.")
            return ""
        finally:
            if wav_path and os.path.exists(wav_path):
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass


def _chunk_text(text: str, max_tokens: int = 77) -> List[str]:
    """Split text into chunks that fit within CLIP's context length.

    This implementation tokenizes the entire transcript once to obtain token
    IDs and then slices those IDs into chunks of at most ``max_tokens``
    elements (including CLIP's special start and end tokens).  Each token slice
    is decoded back to a text string so it can be re-tokenized by CLIP without
    exceeding the context length.  This removes the previous per-word
    tokenization loop and runs in linear time with respect to the transcript
    length.
    """

    text = text.strip()
    if not text:
        return []

    try:
        tokenizer = clip._tokenizer
    except AttributeError:
        from clip.simple_tokenizer import SimpleTokenizer  # type: ignore
        warnings.warn(
            "Installed 'clip' package lacks '_tokenizer'; using fallback SimpleTokenizer. "
            "Install OpenAI CLIP via 'pip install git+https://github.com/openai/CLIP.git'",
            RuntimeWarning,
        )
        tokenizer = SimpleTokenizer()
    token_ids = tokenizer.encode(text)
    tokens_per_chunk = max_tokens - 2  # account for SOT and EOT tokens

    chunks: List[str] = []
    for i in range(0, len(token_ids), tokens_per_chunk):
        chunk_ids = token_ids[i : i + tokens_per_chunk]
        chunk_text = tokenizer.decode(chunk_ids).strip()
        if chunk_text:
            chunks.append(chunk_text)

    return chunks


def score_transcript_with_clip(
    transcript: str,
    categories: List[str],
    prompt_template: str,
    model_name: str = "ViT-B/32",
    label_emb: Optional[torch.Tensor] = None,
) -> Dict:
    device = "cpu"
    model, _ = get_clip_model(model_name, device=device)

    if label_emb is None:
        # Preserve exact label prompts if provided (e.g., from mastercategories).
        if _labels_look_like_prompts(categories):
            prompts = categories
        else:
            tmpl = prompt_template or "a video about {}"
            prompts = [tmpl.format(c) for c in categories]
        # Truncate any over-long label strings instead of raising an error
        label_tokens = clip.tokenize(prompts, truncate=True).to(device)
        with torch.no_grad():
            label_emb = normalize_tensor(model.encode_text(label_tokens).float())
    else:
        label_emb = normalize_tensor(label_emb.to(device).float())

    chunks = _chunk_text(transcript)
    if not chunks:
        return {
            "categories": categories,
            "scores": np.zeros(len(categories)),
            "chunk_count": 0,
            "model": model,
            "device": device,
        }

    # Ensure each transcript chunk fits CLIP's context length
    chunk_tokens = clip.tokenize(chunks, truncate=True).to(device)
    with torch.no_grad():
        chunk_emb = normalize_tensor(model.encode_text(chunk_tokens).float())
        sims = (chunk_emb @ label_emb.T).cpu().numpy()
    scores = sims.mean(axis=0)

    return {
        "categories": categories,
        "scores": scores,
        "chunk_count": len(chunks),
        "model": model,
        "device": device,
    }
