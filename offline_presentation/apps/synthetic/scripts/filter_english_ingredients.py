#!/usr/bin/env python3
"""Remove recipes with non-Latin characters in the original Ingredients column.

Usage:
    python scripts/filter_english_ingredients.py input.csv output.csv

Requires only Python's standard library. Keeps all original columns and
preserves Indian transliterations written in Latin script.
"""
import argparse
import csv
import unicodedata
from pathlib import Path


def has_non_latin_letters(value: str) -> bool:
    for ch in value:
        if unicodedata.category(ch).startswith("L") and "LATIN" not in unicodedata.name(ch, ""):
            return True
    return False


def filter_recipes(source: Path, destination: Path) -> tuple[int, int]:
    if source.resolve() == destination.resolve():
        raise ValueError("Input and output paths must be different.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("r", encoding="utf-8-sig", newline="") as infile, destination.open(
        "w", encoding="utf-8", newline=""
    ) as outfile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames or "Ingredients" not in reader.fieldnames:
            raise ValueError("CSV must contain an 'Ingredients' column.")
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
        writer.writeheader()
        kept = removed = 0
        for row in reader:
            if has_non_latin_letters(row.get("Ingredients") or ""):
                removed += 1
            else:
                writer.writerow(row)
                kept += 1
    return kept, removed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    kept, removed = filter_recipes(args.input, args.output)
    print(f"Kept: {kept}; removed: {removed}; total: {kept + removed}")
    print(f"Filtered CSV: {args.output}")


if __name__ == "__main__":
    main()
