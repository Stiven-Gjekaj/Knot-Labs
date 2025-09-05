# Veil Manual

This manual walks through setting up and running the Veil zero-shot audio+video classifier.

 ## 1. Setup
Ensure you have Python 3.10+ and the system `ffmpeg` binary installed.

Veil now runs **CPU-only** using int8 inference; GPUs are not used.

```bash
bash setup.sh
```
This script creates a virtual environment in `.venv`, installs PyTorch, CLIP, Faster-Whisper, and other dependencies, then verifies imports.

If you install dependencies manually, ensure CLIP comes from OpenAI's repo:

```bash
pip install git+https://github.com/openai/CLIP.git
```

Avoid `pip install clip`, which installs an unrelated package.

 ## 2. Classify a Video
Invoke the CLI with a video path and labels (comma-separated or file path):

```bash
veil path/to/video.mp4 --labels "sports,cars,cooking,news,cat,dog,music,gaming"
```

Using a labels file:
```bash
veil path/to/video.mp4 --labels ../Knot-Mesh/data/categories/mastercategories.txt
```

## 3. Classify an Image
You can run Veil in image-only mode (no audio). By default, image mode uses a visual-only configuration (video_weight=1.0, audio_weight=0.0) and an image-friendly prompt template.

```bash
veil path/to/image.jpg --labels "cat,dog,car,person"
```
Using a labels file:
```bash
veil path/to/image.jpg --labels ../Knot-Mesh/data/categories/mastercategories.txt
```

 ### Master Labels File (two-column)
 You can maintain a single labels file with both variants per line, separated by `|`:
 ```text
 video-label | photo-label
 ```
 The CLI automatically picks the video column for videos and the photo column for images.
```bash
veil path/to/video.mp4 --labels ../Knot-Mesh/data/categories/mastercategories.txt
veil path/to/image.jpg  --labels ../Knot-Mesh/data/categories/mastercategories.txt
```

 Deprecated:
 - `phcategories.txt` and `vdcategories.txt` are deprecated. Prefer `../Knot-Mesh/data/categories/mastercategories.txt` or your own two-column file.

 ## 4. Adjust Options
 - `--frames`: number of frames to sample (default 16)
 - `--audio_weight` / `--video_weight`: fusion weights. Defaults depend on modality:
   - Video: audio_weight=0.5, video_weight=0.5
   - Image: audio_weight=0.0, video_weight=1.0
 - `--threshold`: minimum fused score before returning `unknown`
- `--whisper_model`: Whisper model size (tiny, base, small, medium, large-v2)
- `--template`: CLIP prompt template. Defaults to "a video of {}" for videos and "a photo of {}" for images.
 
 Notes:
 - In image mode, audio is skipped entirely (no transcription).
 - `--frames` is ignored for images.

 ## 5. Expected Output
 The CLI prints ranked predictions for video, audio, and fused scores. If `--threshold` is set and the top fused score falls below it, `unknown` is reported.

 ## 6. CI & Publishing
 - CI workflow `.github/workflows/ci.yml` installs dependencies, compiles sources, and runs the CLI help
 - `publish.yml` builds and uploads the package to PyPI when a GitHub Release is published
