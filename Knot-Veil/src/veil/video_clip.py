from typing import Dict, List, Optional
import numpy as np
import torch
from .utils import sample_frames_cv2, normalize_tensor
from .clip_utils import clip, get_clip_model


def _labels_look_like_prompts(categories: List[str]) -> bool:
    if not categories:
        return False
    first = categories[0].lower().strip()
    return first.startswith("a video ") or first.startswith("a photo ")


def classify_video_clip(
    video_path: str,
    categories: List[str],
    model_name: str = "ViT-B/32",
    frames: int = 16,
    prompt_template: str = "a video of {}",
    label_emb: Optional[torch.Tensor] = None,
) -> Dict:
    device = "cpu"
    model, preprocess = get_clip_model(model_name, device=device)

    if label_emb is None:
        # Use categories directly if they already come as prompts (e.g. from
        # mastercategories.txt: "a video about <category>") to preserve exact text.
        if _labels_look_like_prompts(categories):
            prompts = categories
        else:
            tmpl = prompt_template or "a video of {}"
            prompts = [tmpl.format(c) for c in categories]
        text_tokens = clip.tokenize(prompts).to(device)
        with torch.no_grad():
            text_emb = normalize_tensor(model.encode_text(text_tokens).float())
    else:
        text_emb = normalize_tensor(label_emb.to(device).float())

    imgs = sample_frames_cv2(video_path, max_frames=frames)
    if not imgs:
        raise RuntimeError("No frames sampled from video")
    img_tensors = torch.stack([preprocess(im) for im in imgs]).to(device)
    with torch.no_grad():
        img_emb = normalize_tensor(model.encode_image(img_tensors).float())
        sims = (img_emb @ text_emb.T).cpu().numpy()
    scores = sims.mean(axis=0)

    return {
        "categories": categories,
        "scores": scores,
        "frame_count": len(imgs),
        "model": model,
        "device": device,
    }
