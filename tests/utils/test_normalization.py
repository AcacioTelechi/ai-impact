import pytest

from scripts.utils.normalization import normalize_doi, normalize_title, dedup_key


def test_normalize_doi_strips_url_prefix() -> None:
    assert normalize_doi("https://doi.org/10.1234/abc") == "10.1234/abc"
    assert normalize_doi("http://dx.doi.org/10.1234/ABC") == "10.1234/abc"


def test_normalize_doi_lowercases() -> None:
    assert normalize_doi("10.1234/ABCdef") == "10.1234/abcdef"


def test_normalize_doi_strips_whitespace() -> None:
    assert normalize_doi("  10.1234/abc  ") == "10.1234/abc"


def test_normalize_doi_handles_none() -> None:
    assert normalize_doi(None) == ""
    assert normalize_doi("") == ""


def test_normalize_title_lowercases_and_strips_punctuation() -> None:
    assert (
        normalize_title("Artificial Intelligence: A Survey!")
        == "artificial intelligence a survey"
    )


def test_normalize_title_collapses_whitespace() -> None:
    assert normalize_title("AI   and\tlabor\nmarkets") == "ai and labor markets"


def test_dedup_key_uses_first_author_year_title() -> None:
    key = dedup_key(authors="Smith, J.; Jones, K.", year=2020, title="AI Effects")
    assert "smith" in key
    assert "2020" in key
    assert "ai effects" in key


def test_dedup_key_handles_empty_authors() -> None:
    key = dedup_key(authors="", year=2020, title="AI Effects")
    assert "2020" in key
    assert "ai effects" in key
