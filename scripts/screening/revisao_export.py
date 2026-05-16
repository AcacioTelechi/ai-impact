"""Gera a planilha de revisão manual dos soft-includes do screening.

Soft-include = decisao_final == "incluir" mas NÃO (ambos os modelos == "incluir").
São os casos que a união conservadora passou por causa de "duvida"/divergência
e que precisam de adjudicação humana. Os ambos-incluir e ambos-excluir não
entram na planilha (decisão LLM concordante já basta).
"""
from __future__ import annotations

import argparse
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
