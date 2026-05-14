"""Pipeline component: import BibTeX exports (WoS/Scopus/SciELO) into the standard CSV schema.

CLI:
    python -m scripts.search.import_bibtex \\
        --source wos \\
        --files data/raw/searches/manual/wos/*.bib \\
        --output data/raw/searches/wos_2026-05-15.csv \\
        --meta-output data/raw/searches/wos_2026-05-15.meta.json \\
        --query-string "$(cat protocols/search_strings/en.txt)"
"""
from __future__ import annotations

from pathlib import Path

import bibtexparser

from scripts.utils.normalization import normalize_doi


LANG_MAP = {
    "english": "en", "en": "en", "eng": "en",
    "portuguese": "pt", "pt": "pt", "por": "pt", "português": "pt",
    "spanish": "es", "es": "es", "spa": "es", "español": "es",
    "french": "fr", "fr": "fr", "fra": "fr", "français": "fr",
}


def _normalize_language(raw: str | None) -> str:
    if not raw:
        return "en"
    key = raw.strip().lower()
    return LANG_MAP.get(key, "en")


def _strip_braces(s: str) -> str:
    return s.replace("{", "").replace("}", "").strip() if s else ""


def _normalize_authors(authors_field: str | None) -> str:
    """Convert 'Smith, John and Doe, Jane' to 'Smith, J.; Doe, J.'"""
    if not authors_field:
        return ""
    parts = [a.strip() for a in authors_field.split(" and ")]
    normalized = []
    for p in parts:
        p = _strip_braces(p)
        if "," in p:
            last, _, first = p.partition(",")
            initials = ".".join(w[0].upper() for w in first.strip().split() if w)
            normalized.append(f"{last.strip()}, {initials}." if initials else last.strip())
        else:
            normalized.append(p)
    return "; ".join(normalized)


def parse_bib_files(files: list[Path]) -> list[dict]:
    """Parse one or more .bib files, returning a flat list of entry dicts."""
    all_entries: list[dict] = []
    for f in files:
        library = bibtexparser.parse_file(str(f))
        for entry in library.entries:
            d = {}
            for field_key, field in entry.fields_dict.items():
                # bibtexparser v2: Field objects have .value
                d[field_key] = field.value if hasattr(field, "value") else field
            d["entry_type"] = entry.entry_type
            d["key"] = entry.key
            all_entries.append(d)
    return all_entries


def map_wos(entry: dict) -> dict:
    """Map a WoS BibTeX entry to the standard 8-column schema."""
    year_raw = _strip_braces(entry.get("year", ""))
    return {
        "source": "wos",
        "doi": normalize_doi(_strip_braces(entry.get("doi", ""))),
        "title": _strip_braces(entry.get("title", "")),
        "authors": _normalize_authors(_strip_braces(entry.get("author", ""))),
        "year": int(year_raw) if year_raw.isdigit() else "",
        "abstract": _strip_braces(entry.get("abstract", "")),
        "venue": _strip_braces(entry.get("journal", "") or entry.get("booktitle", "")),
        "language": _normalize_language(_strip_braces(entry.get("language", ""))),
    }
