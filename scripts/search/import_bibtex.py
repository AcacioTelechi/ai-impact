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

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import bibtexparser
import pandas as pd
from langdetect import detect, DetectorFactory, LangDetectException

from scripts.utils.io import sha256_file, write_corpus_csv
from scripts.utils.normalization import normalize_doi, dedup_key

DetectorFactory.seed = 42  # deterministic langdetect


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
    """Parse one or more .bib files, returning a flat list of entry dicts.

    Field keys are lowercased so callers can rely on canonical names (`author`,
    `title`, ...) regardless of how the source database capitalizes them.
    WoS exports use Title Case (`Author`, `Title`); Scopus uses lowercase.
    """
    all_entries: list[dict] = []
    for f in files:
        library = bibtexparser.parse_file(str(f))
        for entry in library.entries:
            d = {}
            for field_key, field in entry.fields_dict.items():
                value = field.value if hasattr(field, "value") else field
                d[field_key.lower()] = value
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


def _detect_lang(title: str, abstract: str) -> str:
    text = f"{title} {abstract}".strip()
    if not text:
        return "en"
    try:
        code = detect(text)
    except LangDetectException:
        return "en"
    return LANG_MAP.get(code, "en")


def map_scopus(entry: dict) -> dict:
    row = map_wos(entry)
    row["source"] = "scopus"
    if not entry.get("language"):
        row["language"] = _detect_lang(row["title"], row["abstract"])
    return row


def map_scielo(entry: dict) -> dict:
    row = map_wos(entry)
    row["source"] = "scielo"
    if not entry.get("language"):
        row["language"] = _detect_lang(row["title"], row["abstract"])
    return row


_MAPPERS = {"wos": map_wos, "scopus": map_scopus, "scielo": map_scielo}


def _intra_source_dedup(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for r in rows:
        if r["doi"]:
            key = r["doi"]
        else:
            key = dedup_key(authors=r["authors"], year=r["year"], title=r["title"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def run(
    bibtex_files: list[Path],
    source: str,
    output: Path,
    meta_output: Path,
    query_string: str | None = None,
) -> None:
    if source not in _MAPPERS:
        raise ValueError(f"Unknown source: {source}. Expected one of {list(_MAPPERS)}")
    mapper = _MAPPERS[source]
    entries = parse_bib_files(bibtex_files)
    rows = [mapper(e) for e in entries]
    n_raw = len(rows)
    rows = _intra_source_dedup(rows)

    output.parent.mkdir(parents=True, exist_ok=True)
    write_corpus_csv(pd.DataFrame(rows), output)

    meta = {
        "base": source,
        "lang": None,
        "query_used": query_string or "",
        "query_string_version": "1.0",
        "date_from": "",
        "date_to": "",
        "executed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "n_files": len(bibtex_files),
        "n_entries_raw": n_raw,
        "n_after_intra_dedup": len(rows),
        "n_hits_raw": n_raw,
        "n_after_filters": len(rows),
        "csv_sha256": sha256_file(output),
        "tool_version": "ai-impact 0.2.0",
        "notes": "",
    }
    meta_output.parent.mkdir(parents=True, exist_ok=True)
    meta_output.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"BibTeX {source}: {n_raw} entries → {len(rows)} after intra-dedup → {output}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, choices=["wos", "scopus", "scielo"])
    p.add_argument("--files", type=Path, nargs="+", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--meta-output", type=Path, required=True)
    p.add_argument("--query-string", default="")
    a = p.parse_args(argv)
    run(
        bibtex_files=a.files, source=a.source,
        output=a.output, meta_output=a.meta_output,
        query_string=a.query_string,
    )
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
