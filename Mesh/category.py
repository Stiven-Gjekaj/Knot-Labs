from __future__ import annotations

from typing import Dict, List, Any


def make_category_from_micro(micro: List[str]) -> Dict:
    """Build a Category object with multiple levels from a list of labels.

    - macro: first 2 unique labels (list[str])
    - meso: next 4 unique labels (list[str])
    - micro: next 8 unique labels (list[str])

    Falls back to 'uncategorized' if empty.
    """
    uniq: List[str] = []
    seen = set()
    for m in micro:
        s = (m or "").strip()
        if not s:
            continue
        if s not in seen:
            uniq.append(s)
            seen.add(s)
    # slice into macro/meso/micro buckets
    macro = uniq[:2] if uniq else ["uncategorized"]
    rest_after_macro = uniq[2:]
    meso = rest_after_macro[:4] if rest_after_macro else macro
    rest_after_meso = rest_after_macro[4:]
    micro_labels = rest_after_meso[:8] if rest_after_meso else []
    return {"macro": macro, "meso": meso, "micro": micro_labels}


def make_category_with_limits(micro: List[str], macro_n: int = 2, meso_n: int = 4, micro_n: int = 8) -> Dict:
    """Build a Category object with specific bucket sizes.

    This does not affect the default behavior of make_category_from_micro used by tests.
    """
    uniq: List[str] = []
    seen = set()
    for m in micro:
        s = (m or "").strip()
        if not s:
            continue
        if s not in seen:
            uniq.append(s)
            seen.add(s)
    macro = uniq[:macro_n] if uniq else ["uncategorized"]
    rest_after_macro = uniq[macro_n:]
    meso = rest_after_macro[:meso_n] if rest_after_macro else macro
    rest_after_meso = rest_after_macro[meso_n:]
    micro_labels = rest_after_meso[:micro_n] if rest_after_meso else []
    return {"macro": macro, "meso": meso, "micro": micro_labels}


def ensure_category(post: Dict) -> Dict:
    # Return a Category object, converting legacy 'Categories' list if needed.
    raw = post.get("Category")
    if isinstance(raw, dict):
        cat: Dict[str, Any] = raw
        # normalize missing keys
        micro = cat.get("micro")
        if not isinstance(micro, list):
            micro = []
        macro = cat.get("macro")
        if isinstance(macro, str):
            macro = [macro] if macro else []
        elif not isinstance(macro, list):
            macro = []
        meso = cat.get("meso")
        if isinstance(meso, str):
            meso = [meso] if meso else []
        elif not isinstance(meso, list):
            meso = []
        # If any fields missing, rebuild from micro for consistency
        if not macro or not meso:
            rebuilt = make_category_from_micro(list(micro))
            # Merge with existing when possible
            macro = macro or rebuilt["macro"]
            meso = meso or rebuilt["meso"]
            micro = list(micro) if micro else rebuilt["micro"]
        cat_out = {"macro": macro, "meso": meso, "micro": micro}
        return cat_out
    legacy = post.get("Categories") or []
    cat = make_category_from_micro(list(legacy))
    return cat


def category_texts(category: Dict) -> List[str]:
    """Flatten category object into text tokens for indexing.

    Returns concatenated list of macros + mesos + micro labels.
    """
    out: List[str] = []
    macro = category.get("macro")
    if isinstance(macro, list):
        out.extend([m for m in macro if isinstance(m, str)])
    elif isinstance(macro, str):
        out.append(macro)
    meso = category.get("meso")
    if isinstance(meso, list):
        out.extend([m for m in meso if isinstance(m, str)])
    elif isinstance(meso, str):
        out.append(meso)
    micro = category.get("micro") or []
    if isinstance(micro, list):
        out.extend([m for m in micro if isinstance(m, str)])
    return out
