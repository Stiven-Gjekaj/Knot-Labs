from __future__ import annotations

from typing import Dict, List


def make_category_from_micro(micro: List[str]) -> Dict:
    uniq = []
    seen = set()
    for m in micro:
        s = (m or "").strip()
        if not s:
            continue
        if s not in seen:
            uniq.append(s)
            seen.add(s)
    macro = uniq[0] if uniq else "uncategorized"
    meso = uniq[1] if len(uniq) > 1 else macro
    return {"macro": macro, "meso": meso, "micro": uniq}


def ensure_category(post: Dict) -> Dict:
    # Return a Category object, converting legacy 'Categories' list if needed.
    if isinstance(post.get("Category"), dict):
        cat = post["Category"]
        # normalize missing keys
        if "micro" not in cat:
            cat["micro"] = []
        if "macro" not in cat:
            cat["macro"] = (cat["micro"][0] if cat["micro"] else "uncategorized")
        if "meso" not in cat:
            cat["meso"] = (cat["micro"][1] if len(cat["micro"]) > 1 else cat["macro"])
        return cat
    legacy = post.get("Categories") or []
    cat = make_category_from_micro(list(legacy))
    return cat


def category_texts(category: Dict) -> List[str]:
    micro = category.get("micro") or []
    return [category.get("macro") or "", category.get("meso") or "", *micro]

