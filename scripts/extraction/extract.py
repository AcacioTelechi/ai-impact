"""Pipeline step 06: structured data extraction (CLI form).

Loads the eligibility CSV (included papers) and presents a CLI form for each
paper not yet extracted in `06_extraction.csv`. Saves one row per paper following
the schema in `protocols/extraction_schema.md`.

CLI:
    python -m scripts.extraction.extract \
        --eligibility data/processed/04_eligibility.csv \
        --output data/processed/06_extraction.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

SCHEMA_COLUMNS = [
    # Bloco A — identificação
    "id", "doi", "titulo", "autores", "ano", "periodico", "tipo_pub",
    "pais_estudo", "periodo_dados",
    # Bloco B — temporal
    "janela", "pre_pos_chatgpt", "tecnologia_focada",
    # Bloco C — evidência
    "tipo_estudo", "metodo_empirico", "unidade_analise", "fonte_dados",
    # Bloco D — mecanismos
    "mec_deslocamento", "mec_reinstalacao", "mec_complementaridade",
    "mec_demanda_agregada", "mec_outros",
    # Bloco E — achados
    "sinal_efeito", "magnitude_reportada", "magnitude_normalizada",
    "ocupacoes_afetadas", "polarizacao", "horizonte",
    # Bloco F — qualidade
    "score_qualidade", "limitacoes_declaradas", "replicavel", "revisado_por_pares",
    # Bloco G — notas
    "nota_extracao", "citacoes_chave", "revisto_humano",
]


def next_id(extraction_path: Path) -> str:
    """Return the next sequential id (s-NNN) given existing extractions."""
    if not extraction_path.exists():
        return "s-001"
    df = pd.read_csv(extraction_path)
    if df.empty or "id" not in df.columns:
        return "s-001"
    nums = [int(i.split("-")[1]) for i in df["id"].dropna() if i.startswith("s-")]
    n = (max(nums) if nums else 0) + 1
    return f"s-{n:03d}"


def save_row(row: dict, output: Path) -> None:
    """Append a row to the extraction CSV, creating it with header if needed."""
    output.parent.mkdir(parents=True, exist_ok=True)
    df_new = pd.DataFrame([row], columns=SCHEMA_COLUMNS)
    if output.exists():
        df_new.to_csv(output, mode="a", header=False, index=False, encoding="utf-8")
    else:
        df_new.to_csv(output, index=False, encoding="utf-8")


def _prompt(label: str, default: str = "") -> str:
    val = input(f"{label} [{default}]: ").strip()
    return val or default


def _interactive_form(meta: pd.Series, id_: str) -> dict:
    print(f"\n=== Extracting: {meta['titulo']} ({meta['ano']}) ===\n")
    row = {col: "" for col in SCHEMA_COLUMNS}
    row.update(
        id=id_, doi=meta.get("doi", ""), titulo=meta["titulo"],
        autores=meta.get("autores", ""), ano=int(meta["ano"]) if pd.notna(meta["ano"]) else "",
        periodico=meta.get("venue", ""), tipo_pub=_prompt("tipo_pub (journal|working paper|book chapter)"),
    )
    row["pais_estudo"] = _prompt("pais_estudo (ou 'multipais')")
    row["periodo_dados"] = _prompt("periodo_dados (e.g., 2010-2019)")
    row["janela"] = _prompt("janela (2013-2017|2018-2022|2022-2025)")
    row["pre_pos_chatgpt"] = _prompt("pre_pos_chatgpt (pre|pos)")
    row["tecnologia_focada"] = _prompt("tecnologia_focada")
    row["tipo_estudo"] = _prompt("tipo_estudo")
    row["metodo_empirico"] = _prompt("metodo_empirico")
    row["unidade_analise"] = _prompt("unidade_analise")
    row["fonte_dados"] = _prompt("fonte_dados")
    for mec in ["mec_deslocamento", "mec_reinstalacao", "mec_complementaridade", "mec_demanda_agregada"]:
        row[mec] = _prompt(f"{mec} (sim|nao|n/a)")
    row["mec_outros"] = _prompt("mec_outros (texto livre)")
    row["sinal_efeito"] = _prompt("sinal_efeito (negativo|positivo|nulo|ambíguo|n/a)")
    row["magnitude_reportada"] = _prompt("magnitude_reportada (texto)")
    row["magnitude_normalizada"] = _prompt("magnitude_normalizada (float ou vazio)")
    row["ocupacoes_afetadas"] = _prompt("ocupacoes_afetadas")
    row["polarizacao"] = _prompt("polarizacao (alta-quali|baixa-quali|ambos|neutro|n/a)")
    row["horizonte"] = _prompt("horizonte")
    row["score_qualidade"] = _prompt("score_qualidade (1-5)")
    row["limitacoes_declaradas"] = _prompt("limitacoes_declaradas")
    row["replicavel"] = _prompt("replicavel (sim|parcial|nao|n/a)")
    row["revisado_por_pares"] = _prompt("revisado_por_pares (sim|nao)")
    row["nota_extracao"] = _prompt("nota_extracao (livre)")
    row["citacoes_chave"] = _prompt("citacoes_chave (IDs separados por ';')")
    row["revisto_humano"] = "True"
    return row


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--eligibility", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)

    elig = pd.read_csv(args.eligibility, encoding="utf-8")
    incl = elig[elig.get("decisao_final", "incluido") == "incluido"]

    already = set()
    if args.output.exists():
        already = set(pd.read_csv(args.output)["doi"].dropna().tolist())

    for _, meta in incl.iterrows():
        doi = str(meta.get("doi") or "").strip()
        if doi and doi in already:
            continue
        id_ = next_id(args.output)
        row = _interactive_form(meta, id_)
        save_row(row, args.output)
        print(f"Saved {id_}.")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
