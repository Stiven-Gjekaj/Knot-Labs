# Scribe

Part of Knot!Labs.
Child System of Veil.
A lightweight environment for category experimentation.

## Managing Categories

The repository ships with a `data/mastercategories.txt` file containing
ready‑made social-media categories.

Generate a fresh `mastercategories.txt` in the default `data/`
directory:

```
python scripts/generate_categories.py --count 1000
```

If the file already exists the generator does nothing.  Random generation
pulls from two word lists stored in `data/word_lists.json`. This file
contains `adjectives` and `nouns` arrays geared toward social-media
content. Add new terms to either list to expand the possible category
combinations and cover broader social-media niches.



Run an interactive demo that can generate categories, create random videos
and search those videos:

```
python scripts/demo.py
```

At the prompt you can enter commands such as:

```
generate categories 5
generate videos 3
search "funny cats"
```

The search command uses a small sentence-transformer model to compare the
semantic meaning of your query with each video's categories. This allows
it to return relevant matches even when the query does not share exact
keywords with the categories.
