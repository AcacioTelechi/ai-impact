import json
from pathlib import Path

from scripts.search.summary import run


def _meta(base: str, lang: str | None, n_raw: int, n_filt: int) -> dict:
    return {
        "base": base, "lang": lang,
        "executed_at_utc": "2026-05-15T10:00:00+00:00",
        "n_hits_raw": n_raw, "n_after_filters": n_filt,
        "csv_sha256": "x" * 64,
    }


def test_summary_aggregates_all_meta_json(tmp_path: Path) -> None:
    sdir = tmp_path / "searches"
    sdir.mkdir()
    (sdir / "openalex_en_2026-05-15.meta.json").write_text(
        json.dumps(_meta("openalex", "en", 2453, 2104))
    )
    (sdir / "openalex_pt_2026-05-15.meta.json").write_text(
        json.dumps(_meta("openalex", "pt", 184, 162))
    )
    (sdir / "wos_2026-05-15.meta.json").write_text(
        json.dumps(_meta("wos", None, 1820, 1820))
    )
    out = tmp_path / "summary.tex"
    run(searches_dir=sdir, output_table=out)
    text = out.read_text()
    assert "\\begin{tabular}" in text
    assert "2453" in text
    assert "openalex" in text
    assert "wos" in text
    # Total row (2453 + 184 + 1820 = 4457)
    assert "4457" in text or "Total" in text
