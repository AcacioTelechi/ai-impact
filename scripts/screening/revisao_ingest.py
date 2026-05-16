"""Ingere a planilha de revisão preenchida e produz o corpus revisado.

Funde as decisões humanas (soft-includes) com as decisões LLM concordantes
(ambos-incluir / ambos-excluir) e emite 03_screening_revisado.csv (2605) e
03_incluidos_final.csv (entrada do Plano 4).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from scripts.screening.llm.batch_client import cache_key, custom_id

_INCLUIR = {"i", "incluir"}
_EXCLUIR = {"e", "excluir"}


def normalize_decisao(raw) -> str:
    """i/e/incluir/excluir (case-insensitive) → canônico; vazio → pendente.

    Valor não reconhecido levanta ValueError.
    """
    if pd.isna(raw):
        return "pendente"
    s = str(raw).strip().lower()
    if s == "":
        return "pendente"
    if s in _INCLUIR:
        return "incluir"
    if s in _EXCLUIR:
        return "excluir"
    raise ValueError(f"decisao_humana inválida: {raw!r}")


def apply_decisions(screening: pd.DataFrame, sheet: pd.DataFrame) -> pd.DataFrame:
    """Produz decisao_final_revisada + origem_decisao + nota_humana (2605 linhas).

    Regra:
      - ambos-incluir → incluir / llm_concordante
      - ambos-excluir → excluir / llm_concordante
      - soft-include com humano i/e → incluir|excluir / humano
      - soft-include sem decisão → incluir / pendente (conservador)
    Casa por review_id (robusto a reordenação da planilha).
    """
    human = {}
    notas = {}
    for _, r in sheet.iterrows():
        rid = str(r["review_id"])
        human[rid] = normalize_decisao(r.get("decisao_humana"))
        nota = r.get("nota_humana")
        notas[rid] = "" if nota is None or pd.isna(nota) else str(nota)

    out = screening.copy().reset_index(drop=True)
    finals: list[str] = []
    origens: list[str] = []
    out_notas: list[str] = []
    for _, row in out.iterrows():
        s, h = row["decisao_sonnet"], row["decisao_haiku"]
        if s == "incluir" and h == "incluir":
            finals.append("incluir")
            origens.append("llm_concordante")
            out_notas.append("")
        elif s == "excluir" and h == "excluir":
            finals.append("excluir")
            origens.append("llm_concordante")
            out_notas.append("")
        else:
            rid = custom_id(cache_key(row))
            decided = human.get(rid, "pendente")
            if decided == "pendente":
                finals.append("incluir")
                origens.append("pendente")
            else:
                finals.append(decided)
                origens.append("humano")
            out_notas.append(notas.get(rid, ""))
    out["decisao_final_revisada"] = finals
    out["origem_decisao"] = origens
    out["nota_humana"] = out_notas
    return out


def run(screening_csv: Path, sheet_csv: Path,
        revisado_csv: Path, incluidos_csv: Path) -> None:
    screening = pd.read_csv(screening_csv, encoding="utf-8", keep_default_na=False)
    sheet = pd.read_csv(sheet_csv, encoding="utf-8", keep_default_na=False)
    # apply_decisions levanta ValueError em valor inválido ANTES de escrever
    revisado = apply_decisions(screening, sheet)

    revisado_csv.parent.mkdir(parents=True, exist_ok=True)
    revisado.to_csv(revisado_csv, index=False, encoding="utf-8")
    incluidos = revisado[revisado["decisao_final_revisada"] == "incluir"]
    incluidos.to_csv(incluidos_csv, index=False, encoding="utf-8")

    n_pend = int((revisado["origem_decisao"] == "pendente").sum())
    n_hum = int((revisado["origem_decisao"] == "humano").sum())
    n_inc = len(incluidos)
    print(f"Revisão ingest: {len(revisado)} registros | "
          f"{n_inc} incluídos | {n_hum} decididos por humano | "
          f"{n_pend} PENDENTES")
    if n_pend:
        print(f"  ⚠ {n_pend} dúvidas ainda sem decisão (contam como incluir). "
              f"Rode PRISMA/Plano 4 só com 0 pendentes.")
    print(f"  → {revisado_csv}\n  → {incluidos_csv}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Ingere a planilha de revisão das dúvidas.")
    p.add_argument("--screening", type=Path, required=True)
    p.add_argument("--sheet", type=Path, required=True)
    p.add_argument("--revisado", type=Path, required=True)
    p.add_argument("--incluidos", type=Path, required=True)
    a = p.parse_args(argv)
    run(screening_csv=a.screening, sheet_csv=a.sheet,
        revisado_csv=a.revisado, incluidos_csv=a.incluidos)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
