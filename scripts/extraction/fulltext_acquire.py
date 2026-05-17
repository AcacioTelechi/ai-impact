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
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from scripts.screening.llm.batch_client import cache_key, custom_id

MAX_PDF_BYTES = 32 * 1024 * 1024  # 32 MB — guard p/ limite prático da API no 4b


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _http_get_bytes(url: str) -> bytes | None:
    """GET com retry/backoff. None se status != 200 ou corpo vazio."""
    r = requests.get(url, timeout=30)
    if r.status_code != 200 or not r.content:
        return None
    return r.content


def download_pdf(url: str, dest: Path, *, get_fn=None, max_bytes: int = MAX_PDF_BYTES) -> str:
    """Baixa atômico: grava `.part`, renomeia no sucesso. Nunca deixa parcial.

    Retorna: "ok" | "download_falhou" | "oversized".
    get_fn(url)->bytes|None injetável (default: _http_get_bytes); em teste, fake.
    """
    get = get_fn if get_fn is not None else _http_get_bytes
    try:
        data = get(url)
    except Exception:
        data = None
    if not data:
        return "download_falhou"
    if len(data) > max_bytes:
        return "oversized"
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(".pdf.part")
    part.write_bytes(data)
    part.replace(dest)  # rename atômico no mesmo filesystem
    return "ok"


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
