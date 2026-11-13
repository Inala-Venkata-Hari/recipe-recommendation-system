"""Shared ingredient-name normalization helpers."""
import re
import unicodedata


# Hyphen and dash variants commonly found in scraped ingredient names.
_DASHES = re.compile(r"[-\u2010-\u2015\u2212]+")
_WHITESPACE = re.compile(r"\s+")


def normalize_ingredient(value):
    """Return a stable comparison/display key without merging distinct ingredients.

    Case and whitespace are normalized, and dash variants between words become
    spaces. Other punctuation and descriptive words are preserved intentionally.
    """
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    text = _DASHES.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def normalize_ingredient_list(values):
    """Normalize an ingredient sequence and remove duplicates, preserving order."""
    if not isinstance(values, (list, tuple, set)):
        return []
    normalized = []
    seen = set()
    for value in values:
        ingredient = normalize_ingredient(value)
        if ingredient and ingredient not in seen:
            normalized.append(ingredient)
            seen.add(ingredient)
    return normalized
