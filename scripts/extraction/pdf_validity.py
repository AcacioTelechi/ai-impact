"""RC3: um PDF baixado (Plano 4a) só vale como bloco `document` se o pypdf
conseguir abri-lo e ele não estiver cifrado. Senão → cai para abstract.
Ver docs/superpowers/specs/2026-05-17-fix-extract-llm-cache-pdf-robustez-design.md
"""
from __future__ import annotations

from pathlib import Path


def pdf_is_extractable(path) -> bool:
    """True se `path` é um PDF que o pypdf abre, parseia e não está cifrado.

    Conservador: qualquer falha (arquivo ausente, bytes não-PDF, corrompido,
    cifrado, pypdf indisponível) → False, e o chamador cai para abstract.
    """
    p = Path(path)
    if not p.is_file():
        return False
    try:
        from pypdf import PdfReader
    except ImportError:
        return False
    try:
        reader = PdfReader(str(p))
        if reader.is_encrypted:
            return False
        _ = len(reader.pages)  # força parse do catálogo (lança se corrompido)
        return True
    except Exception:
        return False
