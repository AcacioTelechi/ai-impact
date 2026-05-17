"""Plano 4b-i: elegibilidade + extração por LLM (Sonnet 4.6), 1 passada
combinada, PDF nativo onde houver / abstract no resto.

Ver docs/superpowers/specs/2026-05-17-plano-4b-i-elegibilidade-extracao-llm-design.md
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

import pandas as pd

from scripts.extraction.extract import SCHEMA_COLUMNS
from scripts.extraction.llm_extract_prompt import build_extract_system_block
from scripts.screening.llm.batch_client import (
    cache_key, custom_id, screen_with_model,
)

MODEL = "claude-sonnet-4-6"

# Bloco A bibliográfico vem do join (não do LLM); o LLM devolve B–G + A-conteúdo.
_A_BIBLIO = ["id", "doi", "titulo", "autores", "ano", "periodico"]
_LLM_FIELDS = [c for c in SCHEMA_COLUMNS if c not in _A_BIBLIO and c != "revisto_humano"]


def _meta_text(row) -> str:
    return (
        f"id: {row.get('id','')}\nTítulo: {row.get('title','')}\n"
        f"Autores: {row.get('authors','')}\nAno: {row.get('year','')}\n"
        f"Periódico: {row.get('venue','')}\nResumo: {row.get('abstract','')}"
    )


def build_user_content(row):
    """document-block do PDF quando text_source=pdf e arquivo existe; senão
    texto (abstract+metadados). Sempre retorna list[dict]."""
    if row.get("text_source") == "pdf":
        p = Path(str(row.get("pdf_path") or ""))
        if p.is_file():
            data = base64.standard_b64encode(p.read_bytes()).decode("ascii")
            return [
                {"type": "document",
                 "source": {"type": "base64",
                            "media_type": "application/pdf", "data": data}},
                {"type": "text",
                 "text": "Extraia conforme as instruções do sistema.\n"
                         + _meta_text(row)},
            ]
    return [{"type": "text",
             "text": "Fonte: apenas resumo. Extraia conforme as instruções "
                     "do sistema (use n/a/vazio onde o resumo não sustentar).\n"
                     + _meta_text(row)}]
