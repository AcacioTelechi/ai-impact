import json
from pathlib import Path

import pandas as pd

from scripts.search.import_bibtex import map_wos, parse_bib_files, map_scopus, map_scielo, run


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


def test_parse_bib_files_normalizes_titlecase_keys() -> None:
    """Real WoS exports use Title Case field keys (Author, Title, ...).

    Regression test: ensure keys are lowercased so map_wos finds them.
    """
    entries = parse_bib_files([FIXTURES / "wos_titlecase_sample.bib"])
    assert len(entries) == 2
    for e in entries:
        # No Title Case keys should leak through
        assert "Author" not in e
        assert "Title" not in e
        assert "DOI" not in e
        # All canonical lowercase keys should be present
        assert e["author"]
        assert e["title"]
        assert e["doi"]
        assert e["year"]
    # And map_wos must produce non-empty rows
    rows = [map_wos(e) for e in entries]
    assert all(r["doi"] for r in rows)
    assert all(r["title"] for r in rows)
    assert all(r["year"] for r in rows)


def test_map_scopus_preserves_spanish() -> None:
    entry = {
        "author": "García, Luis",
        "title": "Inteligencia artificial",
        "journal": "Trimestre Económico",
        "year": "2023",
        "abstract": "Estudio descriptivo.",
        "language": "Spanish",
    }
    row = map_scopus(entry)
    assert row["source"] == "scopus"
    assert row["language"] == "es"
    assert "García" in row["authors"]


def test_map_scielo_detects_language_when_missing() -> None:
    entry = {
        "author": "Silva, R. and Costa, M.",
        "title": "IA generativa e o mercado de trabalho brasileiro",
        "journal": "RBE",
        "year": "2024",
        "doi": "10.5678/rbe.2024.100",
        "abstract": "Análise dos efeitos da IA generativa sobre o emprego.",
        # No 'language' field
    }
    row = map_scielo(entry)
    assert row["source"] == "scielo"
    assert row["language"] == "pt"  # detected via langdetect


def test_run_end_to_end_with_wos_fixture(tmp_path: Path) -> None:
    out = tmp_path / "wos.csv"
    meta = tmp_path / "wos.meta.json"
    run(
        bibtex_files=[FIXTURES / "wos_sample.bib"],
        source="wos",
        output=out,
        meta_output=meta,
        query_string="test query",
    )
    df = pd.read_csv(out)
    assert len(df) == 2
    m = json.loads(meta.read_text())
    assert m["base"] == "wos"
    assert m["n_entries_raw"] == 2
    assert "csv_sha256" in m


def test_run_dedups_intra_source(tmp_path: Path) -> None:
    """Two .bib files with overlapping DOI should dedup to 2 unique."""
    f1 = tmp_path / "lote1.bib"
    f2 = tmp_path / "lote2.bib"
    f1.write_text(
        '@article{A,doi={10.1/A},title={T},author={X, Y},year={2020}}\n',
        encoding="utf-8",
    )
    f2.write_text(
        '@article{A2,doi={10.1/A},title={T},author={X, Y},year={2020}}\n'
        '@article{B,doi={10.1/B},title={U},author={Z, W},year={2021}}\n',
        encoding="utf-8",
    )
    out = tmp_path / "out.csv"
    run(
        bibtex_files=[f1, f2],
        source="wos",
        output=out,
        meta_output=tmp_path / "out.meta.json",
        query_string="q",
    )
    df = pd.read_csv(out)
    assert len(df) == 2  # the two doi=10.1/A duplicate is removed
