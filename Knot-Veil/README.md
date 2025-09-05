# Knot!Veil — Zero-shot Audio+Video Classifier

Part of the Knot!Labs.

Veil fuses **visual frames** and **audio** to classify videos with **no task-specific training**. It samples frames, scores them with CLIP, transcribes speech with Faster-Whisper, encodes the transcript with CLIP’s text encoder, and **fuses** scores (video + speech + low-level audio events via YAMNet). YAMNet is enabled by default but can be disabled. It can also classify **standalone images** (visual-only).

## Features

- **Image classification** mode alongside video.
- **Two-column master labels**: one file for both video and photo labels.
- **Configurable fusion** weights for video frames, speech text, and YAMNet audio events (enabled by default but optional).
- **Deterministic runs** (seed=42) and improved CLI help.
- **CPU-only** execution with int8 inference.

## Installation

Install from source:

```bash
# from source (editable)
pip install -e .

# or build a wheel/sdist
python -m pip install --upgrade build
python -m build
```

### CLIP dependency

Veil requires OpenAI's CLIP implementation. Install it with:

```bash
pip install git+https://github.com/openai/CLIP.git
```

Avoid `pip install clip`, which installs a different package lacking the needed features.

## Usage

Videos (inline labels):

```bash
veil path/to/video.mp4 --labels "sports,cars,cooking,news,cat,dog,music,gaming"
```

Videos (default labels):

```bash
veil path/to/video.mp4
```

Images:

```bash
veil path/to/image.jpg --labels "cat,dog,car,person"
```

Images (default labels):

```bash
veil path/to/image.jpg
```

Master labels file (two-column):

```text
video-label | photo-label
```

Use the same file for both tasks; the CLI auto-selects the right column:

```bash
veil path/to/video.mp4 --labels examples/mastercategories.txt
veil path/to/image.jpg  --labels examples/mastercategories.txt
```

Deprecated:

- `examples/phcategories.txt` and `examples/vdcategories.txt` are deprecated. Use `examples/mastercategories.txt` or a two-column labels file you maintain.

Key options:

- `--frames`: frames to sample (default 16)
- `--audio_weight` / `--video_weight`: fusion weights (defaults: video 0.5/0.5, image 0/1)
- `--threshold`: if top fused score is below this, prints `unknown`
- `--whisper_model`: Whisper size (tiny, base, small, medium, large-v2)
- `--template`: CLIP prompt template. Defaults to "a video of {}" for videos and "a photo of {}" for images when omitted.

## Requirements

- Python 3.10+
- ffmpeg system binary

## Development Setup

Optional helper script (Linux/macOS):

```bash
bash setup.sh
```

## How It Works

CLIP understands images and text in a shared embedding space. Faster-Whisper transcribes speech. By encoding both video frames and transcript with CLIP and fusing scores, Veil performs zero-shot classification.

## CI & Publishing

- CI builds and verifies the package and CLI help
- Publishing workflow uploads to PyPI on GitHub Release

### Build and validate 1000-category label set

```bash
python tools/build_mastercategories.py
python tools/validate_mastercategories.py
```

Classify with fusion

```bash
export OPENAI_API_KEY=sk-...
python -m veil.run \
  --mode video \
  --video path/to/video.mp4 \
  --master_labels_file examples/mastercategories.txt \
  --use_whisper true --whisper_model base \
  --w_video 0.5 --w_speech 0.3 --w_audio 0.2 \
  --threshold 0.25 \
  --print_event_matches
```

YAMNet runs automatically. To disable it, append `--use_yamnet false`.

QUALITY

- Deterministic output (seed=42)
- Type hints, docstrings, inline comments
- Global coverage across domains, culturally inclusive
- The fusion pipeline uses the exact label strings as prompts
