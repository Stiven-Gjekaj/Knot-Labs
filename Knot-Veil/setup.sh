#!/usr/bin/env bash
set -euo pipefail

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

pip install --upgrade pip setuptools wheel

# Try installing torch normally; fall back to CPU wheels if needed
if ! pip install torch torchvision torchaudio; then
  echo "Default PyTorch install failed, trying CPU-only wheels..."
  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
fi

pip install -r requirements.txt

python - <<'PY'
import torch, clip, cv2
from PIL import Image
from faster_whisper import WhisperModel
print('Torch version:', torch.__version__)
print('CLIP models:', clip.available_models())
print('cv2 version:', cv2.__version__)
print('PIL ok')
print('faster-whisper ok')
PY

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Warning: ffmpeg not found. Please install ffmpeg system-wide."
fi

echo "Setup complete. Example run:"
echo "veil --video path/to/video.mp4 --labels 'sports,cars,cooking'"

