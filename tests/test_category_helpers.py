from __future__ import annotations

from Mesh.category import make_category_from_micro, ensure_category, category_texts


def test_make_and_ensure_category_from_micro():
    cat = make_category_from_micro(["animals", "pets", "cats", "kittens"])
    assert isinstance(cat["macro"], list)
    assert cat["macro"][:2] == ["animals", "pets"]
    assert isinstance(cat["meso"], list) and cat["meso"] == ["cats", "kittens"]
    assert isinstance(cat["micro"], list)
    # ensure_category should be idempotent for dict Category
    post = {"Category": cat}
    out = ensure_category(post)
    assert out == cat


def test_ensure_category_from_legacy_list():
    post = {"Categories": ["animals", "pets", "cats"]}
    out = ensure_category(post)
    assert isinstance(out["macro"], list) and out["macro"][:2] == ["animals", "pets"]
    # meso will contain the remaining label since only 3 inputs
    assert isinstance(out["meso"], list)


def test_category_texts_order():
    cat = make_category_from_micro(["macrox", "mesoy", "m1", "m2"])  # keep simple tokens
    toks = category_texts(cat)
    assert toks[0] == "macrox" and toks[1] == "mesoy"
    # Remaining tokens are the rest of macro + all meso + micro
    assert toks[2:] == ["m1", "m2"]
