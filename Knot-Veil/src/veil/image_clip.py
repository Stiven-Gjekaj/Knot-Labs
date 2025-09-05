from typing import Dict, List
import torch
from PIL import Image
from .utils import normalize_tensor
from .clip_utils import clip, get_clip_model


def _labels_look_like_prompts(categories: List[str]) -> bool:
    if not categories:
        return False
    first = categories[0].lower().strip()
    return first.startswith("a video ") or first.startswith("a photo ")


def classify_image_clip(
    image_path: str,
    categories: List[str],
    model_name: str = "ViT-B/32",
    prompt_template: str = "a photo of {}",
) -> Dict:
    device = "cpu"
    model, preprocess = get_clip_model(model_name, device=device)

    # Use categories directly if they already come as prompts (e.g. from
    # mastercategories.txt: "a photo of <category>") to preserve exact text.
    if _labels_look_like_prompts(categories):
        prompts = categories
    else:
        tmpl = prompt_template or "a photo of {}"
        prompts = [tmpl.format(c) for c in categories]
    text_tokens = clip.tokenize(prompts).to(device)
    with torch.no_grad():
        text_emb = normalize_tensor(model.encode_text(text_tokens).float())

    img = Image.open(image_path).convert("RGB")
    img_tensor = preprocess(img).unsqueeze(0).to(device)
    with torch.no_grad():
        img_emb = normalize_tensor(model.encode_image(img_tensor).float())
        sims = (img_emb @ text_emb.T).cpu().numpy()[0]

    return {
        "categories": categories,
        "scores": sims,
        "frame_count": 1,
        "model": model,
        "device": device,
    }
