from pathlib import Path

import pandas as pd

from scripts.screening import prisma_flow


def test_prisma_flow_generates_tex(tmp_path: Path) -> None:
    out = tmp_path / "prisma.tex"
    counts = dict(
        identified=120, duplicates=15, screened=105, excluded_ta=70,
        eligibility=35, excluded_ft=10, included=25,
    )
    prisma_flow.write_tex(counts=counts, output=out)
    text = out.read_text()
    assert "\\begin{tikzpicture}" in text
    assert "120" in text
    assert "25" in text


def test_prisma_flow_reads_pipeline_logs(tmp_path: Path) -> None:
    """Reads bruto, dedup log, dual-LLM screening, post-arbitration corpus and
    extraction CSVs, mapping each to a PRISMA stage under the current schema."""
    # 120 identified — counted via pandas (robust to multiline abstract fields)
    pd.DataFrame({"doi": [f"10/{i}" for i in range(120)]}).to_csv(
        tmp_path / "01_bruto.csv", index=False)
    # 15 duplicates removed → 105 screened
    pd.DataFrame([{"removed_doi": "x"}] * 15).to_csv(
        tmp_path / "02_log.csv", index=False)
    # dual-LLM screening schema: decisao_final (not decisao_llm); 105 rows
    pd.DataFrame(
        {"decisao_final": ["incluir"] * 60 + ["excluir"] * 45}
    ).to_csv(tmp_path / "03_screening.csv", index=False)
    # post-arbitration corpus sent to full text: 40 studies
    pd.DataFrame({"id": range(40)}).to_csv(
        tmp_path / "03_incluidos_final.csv", index=False)
    # extraction: 40 rows → 30 elegivel=incluir (5 parse_fail) + 10 elegivel=excluir
    rows = (
        [{"elegivel": "incluir", "nota_extracao": "", "text_source": "pdf"}] * 25
        + [{"elegivel": "incluir", "nota_extracao": "parse_fail", "text_source": "abstract"}] * 5
        + [{"elegivel": "excluir", "nota_extracao": "", "text_source": "abstract"}] * 10
    )
    pd.DataFrame(rows).to_csv(tmp_path / "06_extraction.csv", index=False)

    counts = prisma_flow.compute_counts(
        bruto=tmp_path / "01_bruto.csv",
        dedup_log=tmp_path / "02_log.csv",
        screening=tmp_path / "03_screening.csv",
        incluidos_final=tmp_path / "03_incluidos_final.csv",
        extraction=tmp_path / "06_extraction.csv",
    )
    assert counts["identified"] == 120
    assert counts["duplicates"] == 15
    assert counts["screened"] == 105
    assert counts["eligibility"] == 40          # full-text candidates (post-arbitration)
    assert counts["excluded_ta"] == 65          # 105 screened − 40 candidates (screening+arbitration)
    assert counts["excluded_ft"] == 10          # elegivel == excluir
    assert counts["included"] == 25             # 30 eligible − 5 parse_fail
    assert counts["pendentes_reextract"] == 5


def test_prisma_coverage_prefers_manifest(tmp_path: Path) -> None:
    """When a manifest is supplied, coverage is computed from its (corrected)
    text_source, not from the extraction CSV."""
    pd.DataFrame({"doi": [f"10/{i}" for i in range(10)]}).to_csv(
        tmp_path / "bruto.csv", index=False)
    pd.DataFrame([{"removed_doi": "x"}] * 2).to_csv(tmp_path / "log.csv", index=False)
    pd.DataFrame({"decisao_final": ["incluir"] * 8}).to_csv(
        tmp_path / "scr.csv", index=False)
    pd.DataFrame({"id": range(8)}).to_csv(tmp_path / "incl.csv", index=False)
    # extraction says 4/8 pdf (50%); manifest corrects to 2/8 pdf (25%)
    pd.DataFrame(
        [{"elegivel": "incluir", "nota_extracao": "", "text_source": "pdf"}] * 4
        + [{"elegivel": "incluir", "nota_extracao": "", "text_source": "abstract"}] * 4
    ).to_csv(tmp_path / "ext.csv", index=False)
    pd.DataFrame(
        [{"text_source": "pdf"}] * 2 + [{"text_source": "abstract"}] * 6
    ).to_csv(tmp_path / "manifest.csv", index=False)

    counts = prisma_flow.compute_counts(
        bruto=tmp_path / "bruto.csv", dedup_log=tmp_path / "log.csv",
        screening=tmp_path / "scr.csv", incluidos_final=tmp_path / "incl.csv",
        extraction=tmp_path / "ext.csv", manifest=tmp_path / "manifest.csv",
    )
    assert round(counts["cobertura_pct"], 1) == 25.0
