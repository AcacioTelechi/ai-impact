"""Text normalization helpers used in deduplication and matching."""
from __future__ import annotations

import re
import unicodedata


def normalize_doi(doi: str | None) -> str:
    """Normalize a DOI: strip URL prefix, lowercase, strip whitespace."""
    if doi is None or not str(doi).strip():
        return ""
    s = str(doi).strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "https://dx.doi.org/"):
        if s.lower().startswith(prefix):
            s = s[len(prefix):]
            break
    return s.lower()


def normalize_title(title: str | None) -> str:
    """Lowercase, strip punctuation, collapse whitespace, NFKD normalize."""
    if title is None or not str(title).strip():
        return ""
    s = unicodedata.normalize("NFKD", str(title))
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _first_author_surname(authors: str | None) -> str:
    if not authors:
        return ""
    first = authors.split(";")[0].strip()
    surname = first.split(",")[0].strip() if "," in first else first.split(" ")[0].strip()
    return surname.lower()


def dedup_key(authors: str | None, year: int | str | None, title: str | None) -> str:
    """Build a stable dedup key from (first author surname, year, normalized title)."""
    surname = _first_author_surname(authors)
    year_s = str(year) if year is not None else ""
    title_n = normalize_title(title)
    return f"{surname}|{year_s}|{title_n}".strip("|")
