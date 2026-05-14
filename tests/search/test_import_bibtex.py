from pathlib import Path

import pandas as pd

from scripts.search.import_bibtex import map_wos, parse_bib_files


FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_map_wos_normalizes_authors_and_doi() -> None:
    entry = {
        "author": "Smith, John and Doe, Jane",
        "title": "Title T",
        "journal": "AER",
        "year": "2020",
        "doi": "https://doi.org/10.1234/ABC",
        "abstract": "abs",
        "language": "English",
    }
    row = map_wos(entry)
    assert row["source"] == "wos"
    assert row["doi"] == "10.1234/abc"
    assert row["authors"] == "Smith, J.; Doe, J."
    assert row["year"] == 2020
    assert row["venue"] == "AER"
    assert row["language"] == "en"


def test_map_wos_handles_missing_optional_fields() -> None:
    entry = {"title": "T", "year": "2020"}
    row = map_wos(entry)
    assert row["doi"] == ""
    assert row["authors"] == ""
    assert row["abstract"] == ""
    assert row["venue"] == ""
    assert row["language"] == "en"  # default


def test_parse_bib_files_loads_fixture() -> None:
    entries = parse_bib_files([FIXTURES / "wos_sample.bib"])
    assert len(entries) == 2
    titles = {e["title"] for e in entries}
    assert "Artificial Intelligence and Employment in the US" in titles
    assert "Robots and Manufacturing Jobs in Europe" in titles


def test_parse_bib_files_preserves_diacritics() -> None:
    entries = parse_bib_files([FIXTURES / "wos_sample.bib"])
    authors_all = " | ".join(e.get("author", "") for e in entries)
    assert "Müller" in authors_all
