"""Plano 4a: aquisição de texto completo dos estudos pós-arbitragem.

Resolve PDFs via drop-in manual (prioridade) → Unpaywall OA → senão
abstract. Armazena o PDF nativo (o 4b o envia direto ao Claude; sem
extração de texto aqui). Emite um manifesto de cobertura.

Ver docs/superpowers/specs/2026-05-17-plano-4a-aquisicao-texto-design.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from scripts.screening.llm.batch_client import cache_key, custom_id

MAX_PDF_BYTES = 32 * 1024 * 1024  # 32 MB — guard p/ limite prático da API no 4b


def assign_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona `review_id` e `id` (s-NNN) estáveis, ordenados por review_id.

    Determinístico e estável sob reordenação do CSV — `id` é a chave que
    liga 4a → 4b → extração.
    """
    out = df.copy()
    out["review_id"] = [custom_id(cache_key(r)) for _, r in out.iterrows()]
    out = out.sort_values("review_id", kind="stable").reset_index(drop=True)
    out["id"] = [f"s-{i:03d}" for i in range(1, len(out) + 1)]
    return out
