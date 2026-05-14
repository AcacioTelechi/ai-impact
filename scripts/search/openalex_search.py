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

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from scripts.search.openalex_utils import reconstruct_abstract
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
