"""Testes da anotação interina do PRISMA (Plano 4b-ii)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def _mk_inputs(tmp_path: Path, n_parse_fail: int = 0):
    bruto = tmp_path / "bruto.csv"
    bruto.write_text("\n".join(["a"] + [str(i) for i in range(20)]),
                     encoding="utf-8")
    dedup = tmp_path / "dedup.csv"
    pd.DataFrame({"a": [1, 2]}).to_csv(dedup, index=False)
    scr = tmp_path / "scr.csv"
    pd.DataFrame({"decisao_llm": ["incluir"] * 12 + ["excluir"] * 6}).to_csv(scr, index=False)
    elig = tmp_path / "elig.csv"
    pd.DataFrame({"decisao_final": ["incluido"] * 10 + ["excluido"] * 2}).to_csv(elig, index=False)
    ext = None
    if n_parse_fail >= 0:
        ext = tmp_path / "ext.csv"
        rows = []
        for i in range(10):
            note = "parse_fail" if i < n_parse_fail else ""
            ts = "pdf" if i % 3 else "abstract"
            rows.append({"id": i, "nota_extracao": note, "text_source": ts})
        pd.DataFrame(rows).to_csv(ext, index=False)
    return bruto, dedup, scr, elig, ext


def test_retrocompat_sem_extraction(tmp_path):
    from scripts.screening import prisma_flow as P
    bruto, dedup, scr, elig, _ = _mk_inputs(tmp_path, n_parse_fail=0)
    counts = P.compute_counts(bruto, dedup, scr, elig)
    out = tmp_path / "p.tex"
    P.write_tex(counts, out)
    tex = out.read_text(encoding="utf-8")
    assert "Reextração pendente" not in tex


def test_anotacao_quando_pendentes_positivos(tmp_path):
    from scripts.screening import prisma_flow as P
    bruto, dedup, scr, elig, ext = _mk_inputs(tmp_path, n_parse_fail=3)
    counts = P.compute_counts(bruto, dedup, scr, elig, extraction=ext)
    out = tmp_path / "p.tex"
    P.write_tex(counts, out)
    tex = out.read_text(encoding="utf-8")
    assert "Reextração pendente: 3" in tex
    assert "cobertura full-text efetiva" in tex


def test_sem_anotacao_quando_zero_pendentes(tmp_path):
    from scripts.screening import prisma_flow as P
    bruto, dedup, scr, elig, ext = _mk_inputs(tmp_path, n_parse_fail=0)
    counts = P.compute_counts(bruto, dedup, scr, elig, extraction=ext)
    out = tmp_path / "p.tex"
    P.write_tex(counts, out)
    tex = out.read_text(encoding="utf-8")
    assert "Reextração pendente" not in tex
