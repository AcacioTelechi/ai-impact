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
