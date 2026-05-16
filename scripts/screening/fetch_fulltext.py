"""Pipeline step 04: locate full-text URLs via Unpaywall and produce a status log.

For each included record, tries Unpaywall to find an open-access PDF URL.
Does NOT actually download PDFs — the user manages PDFs in Zotero. The script
just produces `fulltext_status.csv` to drive manual acquisition.

CLI:
    python -m scripts.screening.fetch_fulltext \
        --input data/processed/03_incluidos_ta.csv \
        --output data/processed/04_fulltext_status.csv \
        --email user@example.com
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _unpaywall_lookup(doi: str, email: str = "") -> dict | None:
    """Return Unpaywall record for DOI, or None if not found / not open access."""
    url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
    r = requests.get(url, timeout=15)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    data = r.json()
    if data.get("is_oa") and data.get("best_oa_location"):
        return {"pdf_url": data["best_oa_location"].get("url_for_pdf")}
    return None


def run(input: Path, output: Path, email: str) -> None:
    df = pd.read_csv(input, encoding="utf-8")
    statuses = []
    urls = []
    for _, row in df.iterrows():
        doi = str(row.get("doi") or "").strip()
        if not doi or doi == "nan":
            statuses.append("no_doi")
            urls.append("")
            continue
        try:
            res = _unpaywall_lookup(doi, email=email)
        except Exception as e:
            statuses.append(f"error: {type(e).__name__}")
            urls.append("")
            continue
        if res and res.get("pdf_url"):
            statuses.append("oa_pdf_url")
            urls.append(res["pdf_url"])
        else:
            statuses.append("no_oa")
            urls.append("")
        time.sleep(0.1)  # polite rate limiting

    df["status"] = statuses
    df["pdf_url"] = urls
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False, encoding="utf-8")
    print(f"Full-text lookup: {sum(s == 'oa_pdf_url' for s in statuses)}/{len(statuses)} found via Unpaywall")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--email", required=True, help="Email for Unpaywall API")
    args = p.parse_args(argv)
    run(args.input, args.output, email=args.email)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
