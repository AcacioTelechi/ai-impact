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
    assert "2.104" in text  # após dedup interna; separador de milhar pt-BR
    assert "openalex" in text
    assert "Web of Science" in text
    # coluna Total (2104 + 162 + 1820 = 4086)
    assert "4.086" in text and "Total" in text
    # sem dedup/extração, só a linha de volume
    assert "Incluídos na síntese" not in text


def test_summary_enriquecida_com_csv_dedup_e_extracao(tmp_path: Path) -> None:
    import pandas as pd

    sdir = tmp_path / "searches"
    sdir.mkdir()
    dados = {
        "scopus": [("10.1/a", "A", "2013", "en"), ("10.1/b", "B", "2020", "en"),
                   ("", "Sem DOI", "2021", "es")],
        "wos": [("10.1/B", "B", "2020", "en"), ("10.1/c", "C", "2015", "en")],
    }
    for base, regs in dados.items():
        (sdir / f"{base}_2026-05-15.meta.json").write_text(
            json.dumps(_meta(base, None, len(regs), len(regs))))
        pd.DataFrame(regs, columns=["doi", "title", "year", "language"]).assign(
            abstract="x").to_csv(sdir / f"{base}_2026-05-15.csv", index=False)
    dedup = tmp_path / "dedup.csv"
    pd.DataFrame([{"removed_doi": "10.1/b", "kept_doi": "10.1/b"}]).to_csv(dedup, index=False)
    ext = tmp_path / "ext.csv"
    pd.DataFrame([
        {"doi": "10.1/b", "titulo": "B", "elegivel": "incluir", "nota_extracao": "ok"},
        {"doi": "10.1/c", "titulo": "C", "elegivel": "incluir", "nota_extracao": "ok"},
        {"doi": "", "titulo": "sem doi", "elegivel": "incluir", "nota_extracao": "ok"},
        {"doi": "10.1/a", "titulo": "A", "elegivel": "excluir", "nota_extracao": "ok"},
    ]).to_csv(ext, index=False)
    out = tmp_path / "summary.tex"
    run(searches_dir=sdir, output_table=out, dedup_decisions=dedup, extraction=ext)
    linhas = {l.split(" & ")[0]: [c.strip(" \\") for c in l.split(" & ")[1:]]
              for l in out.read_text().splitlines() if " & " in l}
    assert linhas["Registros recuperados"] == ["3", "2", "5"]
    assert linhas["Presentes em mais de uma base"] == ["1", "1", "1"]
    assert linhas["Registros únicos após deduplicação"][-1] == "4"
    # B está nas duas (DOI casa sem diferenciar caixa); "Sem DOI" casa pelo título
    assert linhas["Incluídos na síntese"] == ["2", "2", "3"]
    assert linhas["\\quad dos quais exclusivos da base"] == ["1", "1", "2"]
