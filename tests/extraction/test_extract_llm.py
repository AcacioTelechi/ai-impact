# tests/extraction/test_extract_llm.py
import base64
from pathlib import Path

import pandas as pd

from scripts.extraction.extract_llm import build_user_content


def _row(**kw):
    base = {"id": "s-001", "review_id": "r1", "doi": "10.1/a", "title": "T",
            "authors": "A, B", "year": 2020, "venue": "AER", "abstract": "Resumo X",
            "text_source": "abstract", "pdf_path": ""}
    base.update(kw)
    return pd.Series(base)


def test_user_content_abstract_is_text_only():
    c = build_user_content(_row(text_source="abstract"))
    assert isinstance(c, list) and len(c) == 1
    assert c[0]["type"] == "text"
    assert "Resumo X" in c[0]["text"] and "T" in c[0]["text"] and "s-001" in c[0]["text"]


def test_user_content_pdf_has_document_block(tmp_path: Path):
    pdf = tmp_path / "s-002.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    c = build_user_content(_row(id="s-002", text_source="pdf", pdf_path=str(pdf)))
    assert isinstance(c, list) and len(c) == 2
    doc = c[0]
    assert doc["type"] == "document"
    assert doc["source"]["type"] == "base64"
    assert doc["source"]["media_type"] == "application/pdf"
    assert base64.b64decode(doc["source"]["data"]) == b"%PDF-1.4 fake"
    assert c[1]["type"] == "text" and "s-002" in c[1]["text"]


def test_user_content_pdf_missing_file_degrades_to_text(tmp_path: Path):
    c = build_user_content(_row(id="s-003", text_source="pdf",
                                pdf_path=str(tmp_path / "naoexiste.pdf")))
    assert len(c) == 1 and c[0]["type"] == "text"
    assert "Resumo X" in c[0]["text"]
