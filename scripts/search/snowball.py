"""Pipeline component: forward and backward citation tracking via OpenAlex.

To be executed AFTER the initial screening produces a list of central seed DOIs
(Plano 3+). Outputs CSVs in the standard schema with source values
'snowball-backward' or 'snowball-forward'.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

from scripts.search.openalex_search import flatten_record
from scripts.utils.io import write_corpus_csv

load_dotenv()

OPENALEX_BASE = "https://api.openalex.org/works"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _get(url: str, email: str, params: dict | None = None) -> dict:
    headers = {"User-Agent": f"ai-impact/0.2.0 (mailto:{email})"}
    api_key = os.environ.get("OPENALEX_API_KEY")
    if api_key:
        params = {**(params or {}), "api_key": api_key}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _fetch_work_by_id(openalex_id: str, email: str) -> dict | None:
    short = openalex_id.rsplit("/", 1)[-1]  # strip URL prefix
    url = f"{OPENALEX_BASE}/{short}"
    try:
        return _get(url, email=email)
    except requests.HTTPError:
        return None


def backward(
    seed_dois: list[str],
    email: str,
    output: Path,
    year_from: int = 2013,
    year_to: int = 2025,
) -> None:
    """Fetch backward references for each seed DOI; flatten and write CSV."""
    rows: list[dict] = []
    for doi in seed_dois:
        seed = _get(f"{OPENALEX_BASE}/doi:{doi}", email=email)
        for ref_id in seed.get("referenced_works", []):
            ref = _fetch_work_by_id(ref_id, email=email)
            if not ref:
                continue
            year = ref.get("publication_year") or 0
            if year_from <= year <= year_to:
                row = flatten_record(ref, default_lang="en")
                row["source"] = "snowball-backward"
                rows.append(row)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_corpus_csv(pd.DataFrame(rows), output)
    print(f"Snowball backward: {len(rows)} refs from {len(seed_dois)} seeds → {output}")


def forward(
    seed_dois: list[str],
    email: str,
    output: Path,
    year_from: int = 2013,
    year_to: int = 2025,
) -> None:
    """Fetch forward citations for each seed DOI; flatten and write CSV."""
    rows: list[dict] = []
    for doi in seed_dois:
        seed = _get(f"{OPENALEX_BASE}/doi:{doi}", email=email)
        seed_id = seed.get("id", "").rsplit("/", 1)[-1]
        if not seed_id:
            continue
        cursor = "*"
        while cursor is not None:
            params = {
                "filter": f"cites:{seed_id},from_publication_date:{year_from}-01-01,to_publication_date:{year_to}-12-31",
                "per_page": 200,
                "cursor": cursor,
            }
            data = _get(OPENALEX_BASE, email=email, params=params)
            for rec in data.get("results", []):
                row = flatten_record(rec, default_lang="en")
                row["source"] = "snowball-forward"
                rows.append(row)
            cursor = data.get("meta", {}).get("next_cursor")
    output.parent.mkdir(parents=True, exist_ok=True)
    write_corpus_csv(pd.DataFrame(rows), output)
    print(f"Snowball forward: {len(rows)} citing works from {len(seed_dois)} seeds → {output}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("direction", choices=["backward", "forward"])
    p.add_argument("--seeds", type=Path, required=True,
                   help="Text file with one DOI per line")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--year-from", type=int, default=2013)
    p.add_argument("--year-to", type=int, default=2025)
    a = p.parse_args(argv)
    dois = [line.strip() for line in a.seeds.read_text().splitlines() if line.strip()]
    fn = backward if a.direction == "backward" else forward
    fn(seed_dois=dois, email=a.email, output=a.output,
       year_from=a.year_from, year_to=a.year_to)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
