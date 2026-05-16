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


def soft_includes(df: pd.DataFrame) -> pd.DataFrame:
    """Subconjunto a revisar: incluir final que não é ambos-incluir."""
    is_incluir = df["decisao_final"] == "incluir"
    both_incluir = (df["decisao_sonnet"] == "incluir") & (df["decisao_haiku"] == "incluir")
    return df[is_incluir & ~both_incluir].reset_index(drop=True)
