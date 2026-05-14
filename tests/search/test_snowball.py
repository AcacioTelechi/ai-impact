from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd

from scripts.search.snowball import backward, forward


def _mock_get(url: str, **kwargs):
    """Route mock responses based on URL pattern."""
    r = MagicMock()
    r.raise_for_status = MagicMock()
    if "/works/doi:" in url:
        r.status_code = 200
        r.json.return_value = {
            "id": "https://openalex.org/W123",
            "referenced_works": ["https://openalex.org/W500", "https://openalex.org/W501"],
        }
    elif "filter=cites" in url:
        r.status_code = 200
        r.json.return_value = {
            "results": [
                {"doi": "10.5/citing1", "title": "Citing paper 1",
                 "publication_year": 2024, "authorships": [],
                 "primary_location": None, "abstract_inverted_index": None,
                 "language": "en"}
            ],
            "meta": {"next_cursor": None, "count": 1},
        }
    elif "/works/W" in url:
        r.status_code = 200
        r.json.return_value = {
            "doi": "10.4/ref1", "title": "Referenced", "publication_year": 2018,
            "authorships": [], "primary_location": None,
            "abstract_inverted_index": None, "language": "en",
        }
    else:
        r.status_code = 404
    return r


def test_backward_extracts_referenced_works(tmp_path: Path) -> None:
    out = tmp_path / "back.csv"
    with patch("scripts.search.snowball.requests.get", side_effect=_mock_get):
        backward(seed_dois=["10.1/seed"], email="x@y.com", output=out)
    df = pd.read_csv(out)
    assert df["source"].iloc[0] == "snowball-backward"
    assert len(df) >= 1


def test_forward_extracts_citing_works(tmp_path: Path) -> None:
    out = tmp_path / "fwd.csv"
    # Mock that handles both the seed lookup AND the cites filter
    def routed_mock(url, **kwargs):
        params = kwargs.get("params", {}) or {}
        filter_val = params.get("filter", "")
        # Check if it's a cites filter call (request.get passes params, not in URL)
        if "cites:" in str(filter_val):
            r = MagicMock()
            r.raise_for_status = MagicMock()
            r.status_code = 200
            r.json.return_value = {
                "results": [
                    {"doi": "10.5/citing1", "title": "Citing paper 1",
                     "publication_year": 2024, "authorships": [],
                     "primary_location": None, "abstract_inverted_index": None,
                     "language": "en"}
                ],
                "meta": {"next_cursor": None, "count": 1},
            }
            return r
        return _mock_get(url, **kwargs)

    with patch("scripts.search.snowball.requests.get", side_effect=routed_mock):
        forward(seed_dois=["10.1/seed"], email="x@y.com", output=out)
    df = pd.read_csv(out)
    assert df["source"].iloc[0] == "snowball-forward"
    assert len(df) >= 1
