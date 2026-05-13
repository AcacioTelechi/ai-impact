from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd

from scripts.screening import fetch_fulltext


def test_fetch_fulltext_marks_unpaywall_oa(tmp_path: Path) -> None:
    inc = tmp_path / "incluidos.csv"
    pd.DataFrame(
        [
            {"doi": "10.1/oa", "title": "A", "authors": "X", "year": 2020,
             "abstract": "", "venue": "v", "language": "en", "source": "wos"},
            {"doi": "10.1/paywall", "title": "B", "authors": "Y", "year": 2020,
             "abstract": "", "venue": "v", "language": "en", "source": "wos"},
        ]
    ).to_csv(inc, index=False)

    def fake_oa(doi: str, email: str = "") -> dict | None:
        return {"pdf_url": "https://example.org/a.pdf"} if doi == "10.1/oa" else None

    with patch("scripts.screening.fetch_fulltext._unpaywall_lookup", side_effect=fake_oa):
        out = tmp_path / "fulltext_status.csv"
        fetch_fulltext.run(input=inc, output=out, email="acacio@example.com")

    df = pd.read_csv(out)
    assert (df["status"] == "oa_pdf_url").sum() == 1
    assert (df["status"] == "no_oa").sum() == 1


def test_fetch_fulltext_handles_missing_doi(tmp_path: Path) -> None:
    inc = tmp_path / "incluidos.csv"
    pd.DataFrame(
        [{"doi": "", "title": "A", "authors": "X", "year": 2020,
          "abstract": "", "venue": "v", "language": "en", "source": "scopus"}]
    ).to_csv(inc, index=False)

    out = tmp_path / "fulltext_status.csv"
    fetch_fulltext.run(input=inc, output=out, email="acacio@example.com")

    df = pd.read_csv(out)
    assert df.iloc[0]["status"] == "no_doi"
