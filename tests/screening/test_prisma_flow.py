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
    """Reads consolidated, dedup, screening_ta, eligibility CSVs and counts."""
    (tmp_path / "01_bruto.csv").write_text("a\n" * 121, encoding="utf-8")  # 120 records
    pd.DataFrame([{"removed_doi": "x"}] * 15).to_csv(tmp_path / "02_log.csv", index=False)
    pd.DataFrame(
        [{"decisao_llm": "incluir"}] * 30 + [{"decisao_llm": "excluir"}] * 70
        + [{"decisao_llm": "duvida"}] * 5
    ).to_csv(tmp_path / "03_screening.csv", index=False)
    pd.DataFrame(
        [{"decisao_final": "incluido"}] * 25 + [{"decisao_final": "excluido"}] * 10
    ).to_csv(tmp_path / "04_elig.csv", index=False)

    out = tmp_path / "prisma.tex"
    counts = prisma_flow.compute_counts(
        bruto=tmp_path / "01_bruto.csv",
        dedup_log=tmp_path / "02_log.csv",
        screening=tmp_path / "03_screening.csv",
        eligibility=tmp_path / "04_elig.csv",
    )
    assert counts["identified"] == 120
    assert counts["duplicates"] == 15
    assert counts["included"] == 25
