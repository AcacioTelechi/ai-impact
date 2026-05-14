"""Pipeline component: search OpenAlex via REST API.

Reads search strings from `protocols/search_strings/{lang}.txt`, queries
OpenAlex, paginates, flattens results, and writes a CSV + .meta.json pair.

CLI:
    python -m scripts.search.openalex_search \\
        --query-file protocols/search_strings/en.txt \\
        --lang en \\
        --output data/raw/searches/openalex_en_2026-05-15.csv \\
        --meta-output data/raw/searches/openalex_en_2026-05-15.meta.json \\
        --email user@example.com
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from scripts.search.openalex_utils import parse_query_blocks, reconstruct_abstract
from scripts.utils.io import sha256_file, write_corpus_csv
from scripts.utils.normalization import normalize_doi


OPENALEX_BASE = "https://api.openalex.org/works"


def flatten_record(rec: dict, default_lang: str) -> dict:
    """Map an OpenAlex JSON record to our standard 8-column schema."""
    authorships = rec.get("authorships") or []
    authors = "; ".join(
        a.get("author", {}).get("display_name", "")
        for a in authorships
        if a.get("author", {}).get("display_name")
    )
    primary = rec.get("primary_location") or {}
    source_obj = primary.get("source") or {}
    venue = source_obj.get("display_name") or ""
    return {
        "source": "openalex",
        "doi": normalize_doi(rec.get("doi")),
        "title": rec.get("title") or "",
        "authors": authors,
        "year": rec.get("publication_year") or "",
        "abstract": reconstruct_abstract(rec.get("abstract_inverted_index")),
        "venue": venue,
        "language": rec.get("language") or default_lang,
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _fetch_page(params: dict, email: str) -> dict:
    headers = {"User-Agent": f"ai-impact/0.2.0 (mailto:{email})"}
    r = requests.get(OPENALEX_BASE, params=params, headers=headers, timeout=30)
    if r.status_code == 429:
        r.raise_for_status()  # triggers retry
    r.raise_for_status()
    return r.json()


def fetch_all(
    search: str,
    date_from: str,
    date_to: str,
    lang: str,
    email: str,
    per_page: int = 200,
) -> tuple[list[dict], int]:
    """Page through OpenAlex /works results and return all flattened rows.

    Returns (rows, total_count_reported_by_api).
    """
    rows: list[dict] = []
    cursor = "*"
    total = 0
    while cursor is not None:
        params = {
            "search": search,
            "filter": (
                f"from_publication_date:{date_from},"
                f"to_publication_date:{date_to},"
                f"type:article|preprint|book-chapter"
            ),
            "per_page": per_page,
            "cursor": cursor,
        }
        data = _fetch_page(params, email)
        meta = data.get("meta", {})
        total = meta.get("count", total)
        for rec in data.get("results", []):
            rows.append(flatten_record(rec, default_lang=lang))
        cursor = meta.get("next_cursor")
    return rows, total


def filter_by_keywords(rows: list[dict], blocks: list[list[str]]) -> list[dict]:
    """Keep rows that match at least one keyword from EACH block.

    Each block is a list of synonyms (OR). All blocks must match (AND).
    Matching is case-insensitive against title + abstract.
    """
    kept: list[dict] = []
    for row in rows:
        text = f"{row.get('title', '')} {row.get('abstract', '')}".lower()
        if all(any(tok.lower() in text for tok in block) for block in blocks):
            kept.append(row)
    return kept


def run(
    query_file: Path,
    lang: str,
    date_from: str,
    date_to: str,
    output: Path,
    meta_output: Path,
    email: str,
) -> None:
    """Execute an OpenAlex search end-to-end and write CSV + .meta.json."""
    query_text = Path(query_file).read_text(encoding="utf-8")
    blocks = parse_query_blocks(query_text)

    # Build a single 'search' string from the first block (IA terms)
    search_string = " OR ".join(blocks[0]) if blocks else ""

    all_rows, n_raw = fetch_all(
        search=search_string,
        date_from=date_from,
        date_to=date_to,
        lang=lang,
        email=email,
    )
    # Dedup by OpenAlex DOI within this batch
    seen = set()
    deduped = []
    for r in all_rows:
        key = r["doi"] or f"{r['title']}-{r['year']}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    filtered = filter_by_keywords(deduped, blocks) if blocks else deduped

    output.parent.mkdir(parents=True, exist_ok=True)
    write_corpus_csv(pd.DataFrame(filtered), output)

    meta = {
        "base": "openalex",
        "lang": lang,
        "query_used": query_text,
        "query_string_version": "1.0",
        "date_from": date_from,
        "date_to": date_to,
        "executed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "n_hits_raw": int(n_raw),
        "n_after_filters": int(len(filtered)),
        "csv_sha256": sha256_file(output),
        "tool_version": "ai-impact 0.2.0",
        "notes": "",
    }
    meta_output.parent.mkdir(parents=True, exist_ok=True)
    meta_output.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OpenAlex {lang}: {n_raw} hits → {len(filtered)} after filter → {output}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--query-file", type=Path, required=True)
    p.add_argument("--lang", required=True, choices=["en", "pt", "es", "fr"])
    p.add_argument("--date-from", default="2013-01-01")
    p.add_argument("--date-to", default="2025-12-31")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--meta-output", type=Path, required=True)
    p.add_argument("--email", required=True)
    a = p.parse_args(argv)
    run(
        query_file=a.query_file, lang=a.lang,
        date_from=a.date_from, date_to=a.date_to,
        output=a.output, meta_output=a.meta_output, email=a.email,
    )
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
