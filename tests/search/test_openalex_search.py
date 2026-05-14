from unittest.mock import patch, MagicMock

from scripts.search.openalex_search import flatten_record, fetch_all


def test_flatten_record_maps_basic_fields() -> None:
    rec = {
        "doi": "https://doi.org/10.1234/abc",
        "title": "AI and the Labor Market",
        "publication_year": 2023,
        "language": "en",
        "authorships": [
            {"author": {"display_name": "Acemoglu, Daron"}},
            {"author": {"display_name": "Restrepo, Pascual"}},
        ],
        "primary_location": {"source": {"display_name": "American Economic Review"}},
        "abstract_inverted_index": {"AI": [0], "affects": [1], "jobs": [2]},
    }
    row = flatten_record(rec, default_lang="en")
    assert row["source"] == "openalex"
    assert row["doi"] == "10.1234/abc"
    assert row["title"] == "AI and the Labor Market"
    assert row["year"] == 2023
    assert row["language"] == "en"
    assert row["authors"] == "Acemoglu, Daron; Restrepo, Pascual"
    assert row["venue"] == "American Economic Review"
    assert row["abstract"] == "AI affects jobs"


def test_flatten_record_missing_optional_fields() -> None:
    rec = {
        "doi": None,
        "title": "Untitled",
        "publication_year": 2020,
        "authorships": [],
        "primary_location": None,
        "abstract_inverted_index": None,
        "language": None,
    }
    row = flatten_record(rec, default_lang="pt")
    assert row["doi"] == ""
    assert row["authors"] == ""
    assert row["venue"] == ""
    assert row["abstract"] == ""
    assert row["language"] == "pt"


def test_flatten_record_strips_doi_prefix() -> None:
    rec = {"doi": "https://doi.org/10.X/Y", "title": "T", "publication_year": 2020,
           "authorships": [], "primary_location": None,
           "abstract_inverted_index": None, "language": "en"}
    row = flatten_record(rec, default_lang="en")
    assert row["doi"] == "10.x/y"


def _mock_response(status_code: int, json_data: dict | None = None) -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data or {}
    r.raise_for_status = MagicMock()
    return r


def test_fetch_all_handles_single_page() -> None:
    page = {
        "results": [
            {"doi": "10.1/a", "title": "A", "publication_year": 2020,
             "authorships": [], "primary_location": None,
             "abstract_inverted_index": None, "language": "en"}
        ],
        "meta": {"next_cursor": None, "count": 1},
    }
    with patch("scripts.search.openalex_search.requests.get",
               return_value=_mock_response(200, page)):
        rows, total = fetch_all(
            search="ai jobs",
            date_from="2013-01-01", date_to="2025-12-31",
            lang="en", email="x@y.com",
        )
    assert total == 1
    assert len(rows) == 1
    assert rows[0]["doi"] == "10.1/a"


def test_fetch_all_paginates() -> None:
    page1 = {
        "results": [
            {"doi": f"10.1/{i}", "title": f"T{i}", "publication_year": 2020,
             "authorships": [], "primary_location": None,
             "abstract_inverted_index": None, "language": "en"}
            for i in range(3)
        ],
        "meta": {"next_cursor": "cursor-abc", "count": 5},
    }
    page2 = {
        "results": [
            {"doi": f"10.1/{i}", "title": f"T{i}", "publication_year": 2020,
             "authorships": [], "primary_location": None,
             "abstract_inverted_index": None, "language": "en"}
            for i in range(3, 5)
        ],
        "meta": {"next_cursor": None, "count": 5},
    }
    responses = [_mock_response(200, page1), _mock_response(200, page2)]
    with patch("scripts.search.openalex_search.requests.get", side_effect=responses):
        rows, total = fetch_all(
            search="ai jobs",
            date_from="2013-01-01", date_to="2025-12-31",
            lang="en", email="x@y.com",
        )
    assert total == 5
    assert len(rows) == 5
