"""Gera a planilha de revisão manual dos soft-includes do screening.

Soft-include = decisao_final == "incluir" mas NÃO (ambos os modelos == "incluir").
São os casos que a união conservadora passou por causa de "duvida"/divergência
e que precisam de adjudicação humana. Os ambos-incluir e ambos-excluir não
entram na planilha (decisão LLM concordante já basta).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

from scripts.screening.llm.batch_client import cache_key, custom_id

SHEET_COLS = [
    "review_id", "decisao_humana", "nota_humana",
    "year", "title", "venue", "authors", "abstract",
    "decisao_sonnet", "confianca_sonnet", "justificativa_sonnet",
    "decisao_haiku", "confianca_haiku", "justificativa_haiku", "doi",
]


def soft_includes(df: pd.DataFrame) -> pd.DataFrame:
    """Subconjunto a revisar: incluir final que não é ambos-incluir."""
    is_incluir = df["decisao_final"] == "incluir"
    both_incluir = (df["decisao_sonnet"] == "incluir") & (df["decisao_haiku"] == "incluir")
    return df[is_incluir & ~both_incluir].reset_index(drop=True)


def build_sheet(soft_df: pd.DataFrame) -> pd.DataFrame:
    """Constrói a planilha de trabalho a partir dos soft-includes."""
    soft_df = soft_df.reset_index(drop=True)
    out = pd.DataFrame()
    out["review_id"] = soft_df.apply(lambda r: custom_id(cache_key(r)), axis=1)
    out["decisao_humana"] = ""
    out["nota_humana"] = ""
    for col in ("year", "title", "venue", "authors", "abstract",
                "decisao_sonnet", "confianca_sonnet", "justificativa_sonnet",
                "decisao_haiku", "confianca_haiku", "justificativa_haiku", "doi"):
        out[col] = soft_df[col].values
    return out[SHEET_COLS].reset_index(drop=True)


def merge_preserve(fresh: pd.DataFrame, existing: pd.DataFrame | None) -> pd.DataFrame:
    """Funde a planilha recém-computada com a já preenchida, sem perder trabalho.

    - Preserva decisao_humana/nota_humana de `existing` por review_id.
    - Linhas novas em `fresh` entram vazias.
    - Linhas de `existing` ausentes em `fresh` mas COM decisao_humana
      preenchida são mantidas (anexadas ao fim) — nunca descartadas.
    """
    if existing is None or existing.empty:
        return fresh.reset_index(drop=True)

    _ids = existing["review_id"].astype(str).str.strip()
    _dups = sorted(_ids[(_ids != "") & _ids.duplicated()].unique())
    if _dups:
        raise ValueError(
            "review_id duplicado na planilha editada — corrija no LibreOffice "
            f"(cada linha deve ter um review_id único): {_dups}"
        )

    prev = existing.set_index("review_id")
    out = fresh.copy()

    def _prev(rid: str, col: str) -> str:
        if rid in prev.index:
            val = prev.loc[rid, col]
            return "" if pd.isna(val) else str(val)
        return ""

    out["decisao_humana"] = out["review_id"].map(lambda r: _prev(r, "decisao_humana"))
    out["nota_humana"] = out["review_id"].map(lambda r: _prev(r, "nota_humana"))

    fresh_ids = set(fresh["review_id"])
    orphan_decided = existing[
        (~existing["review_id"].isin(fresh_ids))
        & (existing["decisao_humana"].fillna("").astype(str).str.strip() != "")
    ]
    if not orphan_decided.empty:
        orphan_decided = orphan_decided.reindex(columns=out.columns)
        out = pd.concat([out, orphan_decided], ignore_index=True)
    return out.reset_index(drop=True)


def _state_path(sheet_csv: Path) -> Path:
    return sheet_csv.with_suffix(".state.json")


def run(screening_csv: Path, sheet_csv: Path) -> None:
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")

    # 1. Read screening, build fresh.
    df = pd.read_csv(screening_csv, encoding="utf-8", keep_default_na=False)
    soft = soft_includes(df)
    fresh = build_sheet(soft)

    # 2. existing = None; prior_decided = set()
    existing = None
    prior_decided: set[str] = set()
    lost: list[str] = []

    # 3. If sheet exists: read existing, backup, load prior state, compute lost.
    if sheet_csv.exists():
        existing = pd.read_csv(sheet_csv, encoding="utf-8", keep_default_na=False)
        backup = sheet_csv.with_suffix(f".bak-{ts}.csv")
        backup.write_bytes(sheet_csv.read_bytes())
        if _state_path(sheet_csv).exists():
            prior_decided = set(
                json.loads(_state_path(sheet_csv).read_text(encoding="utf-8"))
                .get("decided_review_ids", [])
            )
        cur_decided = set(
            existing.loc[
                existing["decisao_humana"].astype(str).str.strip() != "",
                "review_id",
            ].astype(str)
        )
        lost = sorted(prior_decided - cur_decided)

    # 4. Merge and write sheet.
    merged = merge_preserve(fresh, existing)
    sheet_csv.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(sheet_csv, index=False, encoding="utf-8")

    # 5. Compute decided count.
    n_dec = int((merged["decisao_humana"].astype(str).str.strip() != "").sum())

    # 6. Write new state file.
    decided_ids = (
        merged.loc[
            merged["decisao_humana"].astype(str).str.strip() != "",
            "review_id",
        ]
        .astype(str)
        .tolist()
    )
    _state_path(sheet_csv).write_text(
        json.dumps(
            {
                "decided_review_ids": decided_ids,
                "n_decididas": len(decided_ids),
                "exportado_em": ts,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # 7. Print standard summary.
    print(f"Revisão export: {len(merged)} a revisar | {n_dec} já decididas | "
          f"{len(merged) - n_dec} pendentes → {sheet_csv}")

    # 8. Warn accurately only when previously-decided ids are truly missing.
    if lost:
        print(f"  ⚠ ATENÇÃO: {len(lost)} decisão(ões) registradas no último export "
              f"sumiram da planilha (review_id: {lost[:5]}{' ...' if len(lost) > 5 else ''}). "
              f"Provável linha apagada/limpa no LibreOffice. Há backups em "
              f"{sheet_csv.parent}/{sheet_csv.stem}.bak-*.csv — recupere de um anterior "
              f"ao sumiço e re-exporte.")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Gera planilha de revisão das dúvidas.")
    p.add_argument("--screening", type=Path, required=True)
    p.add_argument("--sheet", type=Path, required=True)
    a = p.parse_args(argv)
    run(screening_csv=a.screening, sheet_csv=a.sheet)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
