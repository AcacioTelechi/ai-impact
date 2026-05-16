# Revisão Manual das Dúvidas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir o round-trip de planilha (`revisao_export.py` → humano preenche → `revisao_ingest.py`) que adjudica manualmente os ~865 soft-includes do screening dual-LLM, produzindo o corpus revisado para o Plano 4.

**Architecture:** Dois scripts pequenos e simétricos em `scripts/screening/`. `export` seleciona os soft-includes e gera uma planilha CSV de forma idempotente e **não-destrutiva** (preserva decisões humanas já preenchidas via merge por `review_id`). `ingest` valida a planilha preenchida, funde as decisões humanas com as decisões LLM-concordantes (462 ambos-incluir, 1278 ambos-excluir) e emite `03_screening_revisado.csv` (2605) + `03_incluidos_final.csv` (entrada do Plano 4).

**Tech Stack:** Python 3.12, pandas, pytest. Reusa `cache_key`/`custom_id` de `scripts.screening.llm.batch_client` para o `review_id`. Sem novas dependências.

**Spec:** `docs/superpowers/specs/2026-05-16-revisao-manual-duvidas-design.md`

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `scripts/screening/revisao_export.py` | `soft_includes`, `build_sheet`, `merge_preserve`, `run`, `_cli` |
| `scripts/screening/revisao_ingest.py` | `normalize_decisao`, `apply_decisions`, `run`, `_cli` |
| `tests/screening/test_revisao_export.py` | testes do export |
| `tests/screening/test_revisao_ingest.py` | testes do ingest |
| `Makefile` | (modificar) alvos `revisao-export`, `revisao-ingest` |
| `protocols/slr_protocol.md` | (modificar) nota em §7 |

Convenções do repo (seguir à risca): `from __future__ import annotations`; CLI via `argparse` em `_cli(argv)` + `if __name__ == "__main__": sys.exit(_cli(sys.argv[1:]))`; feedback via `print`; venv local ativado (`source .venv/bin/activate`), **não** `uv run`; pytest TDD; commits convencionais terminando com `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

Schema de `03_screening_ta.csv` (17 colunas): `source, doi, title, authors, year, abstract, venue, language` (corpus) + `decisao_sonnet, justificativa_sonnet, confianca_sonnet, decisao_haiku, justificativa_haiku, confianca_haiku, decisao_final, concordancia, criterio_exclusao` (Plano 3).

---

## Task 1: `revisao_export.soft_includes` — predicado de seleção

**Files:**
- Create: `scripts/screening/revisao_export.py`
- Test: `tests/screening/test_revisao_export.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/screening/test_revisao_export.py
import pandas as pd

from scripts.screening.revisao_export import soft_includes


def _row(s, h, final):
    return {
        "source": "wos", "doi": "", "title": "T", "authors": "A",
        "year": 2020, "abstract": "x", "venue": "V", "language": "en",
        "decisao_sonnet": s, "justificativa_sonnet": "js", "confianca_sonnet": 0.5,
        "decisao_haiku": h, "justificativa_haiku": "jh", "confianca_haiku": 0.5,
        "decisao_final": final, "concordancia": "x", "criterio_exclusao": "",
    }


def test_soft_includes_excludes_both_incluir_and_both_excluir():
    df = pd.DataFrame([
        _row("incluir", "incluir", "incluir"),   # ambos-incluir → fora
        _row("excluir", "excluir", "excluir"),    # ambos-excluir → fora
        _row("incluir", "duvida", "incluir"),     # soft → dentro
        _row("duvida", "excluir", "incluir"),     # soft → dentro
        _row("incluir", "excluir", "incluir"),    # divergência → dentro
        _row("duvida", "duvida", "incluir"),      # soft → dentro
    ])
    sel = soft_includes(df)
    assert len(sel) == 4
    # nenhum ambos-incluir nem qualquer excluir-final no resultado
    assert ((sel["decisao_sonnet"] == "incluir") & (sel["decisao_haiku"] == "incluir")).sum() == 0
    assert (sel["decisao_final"] == "excluir").sum() == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_revisao_export.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.screening.revisao_export`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/screening/revisao_export.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_revisao_export.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/revisao_export.py tests/screening/test_revisao_export.py
git commit -m "feat(revisao): soft_includes — seleção do subconjunto a revisar

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `revisao_export.build_sheet` — schema da planilha

**Files:**
- Modify: `scripts/screening/revisao_export.py`
- Test: `tests/screening/test_revisao_export.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# adicionar a tests/screening/test_revisao_export.py
from scripts.screening.revisao_export import build_sheet

SHEET_COLS = [
    "review_id", "decisao_humana", "nota_humana",
    "year", "title", "venue", "authors", "abstract",
    "decisao_sonnet", "confianca_sonnet", "justificativa_sonnet",
    "decisao_haiku", "confianca_haiku", "justificativa_haiku", "doi",
]


def test_build_sheet_schema_and_empty_human_cols():
    df = pd.DataFrame([_row("incluir", "duvida", "incluir"),
                       _row("duvida", "duvida", "incluir")])
    sheet = build_sheet(df)
    assert list(sheet.columns) == SHEET_COLS
    assert len(sheet) == 2
    assert (sheet["decisao_humana"] == "").all()
    assert (sheet["nota_humana"] == "").all()
    # review_id estável e consistente com batch_client
    from scripts.screening.llm.batch_client import cache_key, custom_id
    assert sheet.iloc[0]["review_id"] == custom_id(cache_key(df.iloc[0]))


def test_build_sheet_review_id_unique_per_row():
    df = pd.DataFrame([
        {**_row("duvida", "duvida", "incluir"), "doi": "10.1/a"},
        {**_row("duvida", "duvida", "incluir"), "doi": "10.1/b"},
    ])
    sheet = build_sheet(df)
    assert sheet["review_id"].nunique() == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_revisao_export.py -k build_sheet -v`
Expected: FAIL — `ImportError: cannot import name 'build_sheet'`

- [ ] **Step 3: Write minimal implementation (append; add the batch_client import at top with the others)**

```python
# topo de scripts/screening/revisao_export.py, junto aos imports
from scripts.screening.llm.batch_client import cache_key, custom_id

SHEET_COLS = [
    "review_id", "decisao_humana", "nota_humana",
    "year", "title", "venue", "authors", "abstract",
    "decisao_sonnet", "confianca_sonnet", "justificativa_sonnet",
    "decisao_haiku", "confianca_haiku", "justificativa_haiku", "doi",
]


def build_sheet(soft_df: pd.DataFrame) -> pd.DataFrame:
    """Constrói a planilha de trabalho a partir dos soft-includes."""
    out = pd.DataFrame()
    out["review_id"] = soft_df.apply(lambda r: custom_id(cache_key(r)), axis=1)
    out["decisao_humana"] = ""
    out["nota_humana"] = ""
    for col in ("year", "title", "venue", "authors", "abstract",
                "decisao_sonnet", "confianca_sonnet", "justificativa_sonnet",
                "decisao_haiku", "confianca_haiku", "justificativa_haiku", "doi"):
        out[col] = soft_df[col].values
    return out[SHEET_COLS].reset_index(drop=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_revisao_export.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/revisao_export.py tests/screening/test_revisao_export.py
git commit -m "feat(revisao): build_sheet — schema da planilha + review_id estável

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `revisao_export.merge_preserve` — merge não-destrutivo (crítico)

**Files:**
- Modify: `scripts/screening/revisao_export.py`
- Test: `tests/screening/test_revisao_export.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# adicionar a tests/screening/test_revisao_export.py
from scripts.screening.revisao_export import merge_preserve


def test_merge_preserve_keeps_filled_decisions_and_adds_new():
    fresh = pd.DataFrame({
        "review_id": ["a", "b", "c"],
        "decisao_humana": ["", "", ""],
        "nota_humana": ["", "", ""],
        "title": ["TA", "TB", "TC"],
    })
    existing = pd.DataFrame({
        "review_id": ["a", "b"],
        "decisao_humana": ["i", "e"],
        "nota_humana": ["gostei", ""],
        "title": ["TA", "TB"],
    })
    merged = merge_preserve(fresh, existing)
    by = merged.set_index("review_id")
    assert by.loc["a", "decisao_humana"] == "i"      # preservado
    assert by.loc["a", "nota_humana"] == "gostei"    # preservado
    assert by.loc["b", "decisao_humana"] == "e"      # preservado
    assert by.loc["c", "decisao_humana"] == ""       # novo, vazio
    assert len(merged) == 3


def test_merge_preserve_retains_orphaned_decided_rows():
    """Linha decidida que sumiu do conjunto fresh não é descartada."""
    fresh = pd.DataFrame({
        "review_id": ["a"], "decisao_humana": [""], "nota_humana": [""],
        "title": ["TA"],
    })
    existing = pd.DataFrame({
        "review_id": ["a", "z"],
        "decisao_humana": ["", "i"],   # 'z' não está em fresh mas foi decidido
        "nota_humana": ["", "nota z"],
        "title": ["TA", "TZ"],
    })
    merged = merge_preserve(fresh, existing)
    assert "z" in set(merged["review_id"])
    z = merged.set_index("review_id").loc["z"]
    assert z["decisao_humana"] == "i"


def test_merge_preserve_no_existing_returns_fresh():
    fresh = pd.DataFrame({
        "review_id": ["a"], "decisao_humana": [""], "nota_humana": [""],
        "title": ["TA"],
    })
    out = merge_preserve(fresh, None)
    assert out.equals(fresh)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_revisao_export.py -k merge_preserve -v`
Expected: FAIL — `ImportError: cannot import name 'merge_preserve'`

- [ ] **Step 3: Write minimal implementation (append)**

```python
# adicionar a scripts/screening/revisao_export.py
def merge_preserve(fresh: pd.DataFrame, existing: pd.DataFrame | None) -> pd.DataFrame:
    """Funde a planilha recém-computada com a já preenchida, sem perder trabalho.

    - Preserva decisao_humana/nota_humana de `existing` por review_id.
    - Linhas novas em `fresh` entram vazias.
    - Linhas de `existing` ausentes em `fresh` mas COM decisao_humana
      preenchida são mantidas (anexadas ao fim) — nunca descartadas.
    """
    if existing is None or existing.empty:
        return fresh.reset_index(drop=True)

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
        out = pd.concat([out, orphan_decided], ignore_index=True)
    return out.reset_index(drop=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_revisao_export.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/revisao_export.py tests/screening/test_revisao_export.py
git commit -m "feat(revisao): merge_preserve — re-export não destrói decisões humanas

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `revisao_export.run` + `_cli` — orquestração e e2e

**Files:**
- Modify: `scripts/screening/revisao_export.py`
- Test: `tests/screening/test_revisao_export.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# adicionar a tests/screening/test_revisao_export.py
from pathlib import Path

from scripts.screening import revisao_export


def _screening_csv(tmp_path: Path) -> Path:
    p = tmp_path / "03_screening_ta.csv"
    pd.DataFrame([
        {**_row("incluir", "incluir", "incluir"), "doi": "10.1/bi"},   # both-incluir
        {**_row("excluir", "excluir", "excluir"), "doi": "10.1/be"},   # both-excluir
        {**_row("incluir", "duvida", "incluir"), "doi": "10.1/s1"},    # soft
        {**_row("duvida", "excluir", "incluir"), "doi": "10.1/s2"},    # soft
    ]).to_csv(p, index=False)
    return p


def test_run_creates_sheet_with_only_soft_includes(tmp_path: Path):
    src = _screening_csv(tmp_path)
    sheet = tmp_path / "03_revisao_duvidas.csv"
    revisao_export.run(screening_csv=src, sheet_csv=sheet)
    s = pd.read_csv(sheet, keep_default_na=False)
    assert len(s) == 2  # só os 2 soft
    assert set(s["doi"]) == {"10.1/s1", "10.1/s2"}
    assert (s["decisao_humana"] == "").all()


def test_run_reexport_is_non_destructive(tmp_path: Path):
    src = _screening_csv(tmp_path)
    sheet = tmp_path / "03_revisao_duvidas.csv"
    revisao_export.run(screening_csv=src, sheet_csv=sheet)
    s = pd.read_csv(sheet, keep_default_na=False)
    s.loc[s["doi"] == "10.1/s1", "decisao_humana"] = "e"
    s.loc[s["doi"] == "10.1/s1", "nota_humana"] = "fora do escopo"
    s.to_csv(sheet, index=False)
    # re-export
    revisao_export.run(screening_csv=src, sheet_csv=sheet)
    s2 = pd.read_csv(sheet, keep_default_na=False)
    row = s2[s2["doi"] == "10.1/s1"].iloc[0]
    assert row["decisao_humana"] == "e"
    assert row["nota_humana"] == "fora do escopo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_revisao_export.py -k "run_creates or non_destructive" -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'run'`

- [ ] **Step 3: Write minimal implementation (append)**

```python
# adicionar a scripts/screening/revisao_export.py
def run(screening_csv: Path, sheet_csv: Path) -> None:
    df = pd.read_csv(screening_csv, encoding="utf-8", keep_default_na=False)
    soft = soft_includes(df)
    fresh = build_sheet(soft)
    existing = None
    if sheet_csv.exists():
        existing = pd.read_csv(sheet_csv, encoding="utf-8", keep_default_na=False)
    merged = merge_preserve(fresh, existing)
    sheet_csv.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(sheet_csv, index=False, encoding="utf-8")
    n_dec = int((merged["decisao_humana"].astype(str).str.strip() != "").sum())
    print(f"Revisão export: {len(merged)} a revisar | {n_dec} já decididas | "
          f"{len(merged) - n_dec} pendentes → {sheet_csv}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Gera planilha de revisão das dúvidas.")
    p.add_argument("--screening", type=Path, required=True)
    p.add_argument("--sheet", type=Path, required=True)
    a = p.parse_args(argv)
    run(screening_csv=a.screening, sheet_csv=a.sheet)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_revisao_export.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/revisao_export.py tests/screening/test_revisao_export.py
git commit -m "feat(revisao): revisao_export run + CLI (idempotente, não-destrutivo)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `revisao_ingest.normalize_decisao` — validação de valores

**Files:**
- Create: `scripts/screening/revisao_ingest.py`
- Test: `tests/screening/test_revisao_ingest.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/screening/test_revisao_ingest.py
import pandas as pd
import pytest

from scripts.screening.revisao_ingest import normalize_decisao


@pytest.mark.parametrize("raw,exp", [
    ("i", "incluir"), ("I", "incluir"), ("incluir", "incluir"),
    ("INCLUIR", "incluir"), (" e ", "excluir"), ("excluir", "excluir"),
    ("", "pendente"), ("   ", "pendente"), (None, "pendente"),
])
def test_normalize_valid_and_empty(raw, exp):
    assert normalize_decisao(raw) == exp


@pytest.mark.parametrize("bad", ["x", "talvez", "1", "sim", "yes"])
def test_normalize_invalid_raises(bad):
    with pytest.raises(ValueError):
        normalize_decisao(bad)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_revisao_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.screening.revisao_ingest`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/screening/revisao_ingest.py
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
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return "pendente"
    s = str(raw).strip().lower()
    if s == "":
        return "pendente"
    if s in _INCLUIR:
        return "incluir"
    if s in _EXCLUIR:
        return "excluir"
    raise ValueError(f"decisao_humana inválida: {raw!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_revisao_ingest.py -v`
Expected: PASS (12 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/revisao_ingest.py tests/screening/test_revisao_ingest.py
git commit -m "feat(revisao): normalize_decisao — validação i/e/vazio/inválido

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `revisao_ingest.apply_decisions` — fusão LLM + humano

**Files:**
- Modify: `scripts/screening/revisao_ingest.py`
- Test: `tests/screening/test_revisao_ingest.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# adicionar a tests/screening/test_revisao_ingest.py
from scripts.screening.revisao_ingest import apply_decisions


def _row(s, h, final, doi):
    return {
        "source": "wos", "doi": doi, "title": "T", "authors": "A",
        "year": 2020, "abstract": "x", "venue": "V", "language": "en",
        "decisao_sonnet": s, "justificativa_sonnet": "js", "confianca_sonnet": 0.5,
        "decisao_haiku": h, "justificativa_haiku": "jh", "confianca_haiku": 0.5,
        "decisao_final": final, "concordancia": "x", "criterio_exclusao": "",
    }


def _rid(d):
    return custom_id(cache_key(pd.Series(d)))


def test_apply_decisions_four_categories():
    screening = pd.DataFrame([
        _row("incluir", "incluir", "incluir", "10.1/bi"),   # ambos-incluir
        _row("excluir", "excluir", "excluir", "10.1/be"),    # ambos-excluir
        _row("incluir", "duvida", "incluir", "10.1/s1"),     # soft → humano i
        _row("duvida", "excluir", "incluir", "10.1/s2"),     # soft → humano e
        _row("duvida", "duvida", "incluir", "10.1/s3"),      # soft → pendente
    ])
    sheet = pd.DataFrame([
        {"review_id": _rid(screening.iloc[2].to_dict()), "decisao_humana": "i", "nota_humana": ""},
        {"review_id": _rid(screening.iloc[3].to_dict()), "decisao_humana": "e", "nota_humana": "fora"},
        {"review_id": _rid(screening.iloc[4].to_dict()), "decisao_humana": "", "nota_humana": ""},
    ])
    out = apply_decisions(screening, sheet)
    by = out.set_index("doi")
    assert by.loc["10.1/bi", "decisao_final_revisada"] == "incluir"
    assert by.loc["10.1/bi", "origem_decisao"] == "llm_concordante"
    assert by.loc["10.1/be", "decisao_final_revisada"] == "excluir"
    assert by.loc["10.1/be", "origem_decisao"] == "llm_concordante"
    assert by.loc["10.1/s1", "decisao_final_revisada"] == "incluir"
    assert by.loc["10.1/s1", "origem_decisao"] == "humano"
    assert by.loc["10.1/s2", "decisao_final_revisada"] == "excluir"
    assert by.loc["10.1/s2", "origem_decisao"] == "humano"
    assert by.loc["10.1/s2", "nota_humana"] == "fora"
    assert by.loc["10.1/s3", "decisao_final_revisada"] == "incluir"
    assert by.loc["10.1/s3", "origem_decisao"] == "pendente"
    assert len(out) == 5


def test_apply_decisions_robust_to_sheet_reordering():
    screening = pd.DataFrame([
        _row("duvida", "duvida", "incluir", "10.1/s1"),
        _row("incluir", "duvida", "incluir", "10.1/s2"),
    ])
    sheet = pd.DataFrame([
        {"review_id": _rid(screening.iloc[1].to_dict()), "decisao_humana": "e", "nota_humana": ""},
        {"review_id": _rid(screening.iloc[0].to_dict()), "decisao_humana": "i", "nota_humana": ""},
    ])  # ordem invertida de propósito
    out = apply_decisions(screening, sheet).set_index("doi")
    assert out.loc["10.1/s1", "decisao_final_revisada"] == "incluir"
    assert out.loc["10.1/s2", "decisao_final_revisada"] == "excluir"


def test_apply_decisions_invalid_value_raises_listing_rows():
    screening = pd.DataFrame([_row("duvida", "duvida", "incluir", "10.1/s1")])
    sheet = pd.DataFrame([
        {"review_id": _rid(screening.iloc[0].to_dict()), "decisao_humana": "talvez", "nota_humana": ""},
    ])
    with pytest.raises(ValueError, match="talvez"):
        apply_decisions(screening, sheet)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_revisao_ingest.py -k apply_decisions -v`
Expected: FAIL — `ImportError: cannot import name 'apply_decisions'`

- [ ] **Step 3: Write minimal implementation (append)**

```python
# adicionar a scripts/screening/revisao_ingest.py
def apply_decisions(screening: pd.DataFrame, sheet: pd.DataFrame) -> pd.DataFrame:
    """Produz decisao_final_revisada + origem_decisao + nota_humana (2605 linhas).

    Regra:
      - ambos-incluir → incluir / llm_concordante
      - ambos-excluir → excluir / llm_concordante
      - soft-include com humano i/e → incluir|excluir / humano
      - soft-include sem decisão → incluir / pendente (conservador)
    Casa por review_id (robusto a reordenação da planilha).
    """
    human = {}
    notas = {}
    for _, r in sheet.iterrows():
        rid = str(r["review_id"])
        human[rid] = normalize_decisao(r.get("decisao_humana"))
        nota = r.get("nota_humana")
        notas[rid] = "" if nota is None or pd.isna(nota) else str(nota)

    out = screening.copy().reset_index(drop=True)
    finals: list[str] = []
    origens: list[str] = []
    out_notas: list[str] = []
    for _, row in out.iterrows():
        s, h = row["decisao_sonnet"], row["decisao_haiku"]
        if s == "incluir" and h == "incluir":
            finals.append("incluir"); origens.append("llm_concordante"); out_notas.append("")
        elif s == "excluir" and h == "excluir":
            finals.append("excluir"); origens.append("llm_concordante"); out_notas.append("")
        else:
            rid = custom_id(cache_key(row))
            decided = human.get(rid, "pendente")
            if decided == "pendente":
                finals.append("incluir"); origens.append("pendente")
            else:
                finals.append(decided); origens.append("humano")
            out_notas.append(notas.get(rid, ""))
    out["decisao_final_revisada"] = finals
    out["origem_decisao"] = origens
    out["nota_humana"] = out_notas
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_revisao_ingest.py -v`
Expected: PASS (15 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/revisao_ingest.py tests/screening/test_revisao_ingest.py
git commit -m "feat(revisao): apply_decisions — fusão LLM-concordante + humano

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: `revisao_ingest.run` + `_cli` — saídas e resumo

**Files:**
- Modify: `scripts/screening/revisao_ingest.py`
- Test: `tests/screening/test_revisao_ingest.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# adicionar a tests/screening/test_revisao_ingest.py
from pathlib import Path

from scripts.screening import revisao_ingest


def test_run_writes_revisado_and_incluidos(tmp_path: Path, capsys):
    screening = pd.DataFrame([
        _row("incluir", "incluir", "incluir", "10.1/bi"),
        _row("excluir", "excluir", "excluir", "10.1/be"),
        _row("incluir", "duvida", "incluir", "10.1/s1"),
        _row("duvida", "duvida", "incluir", "10.1/s2"),
    ])
    scsv = tmp_path / "03_screening_ta.csv"
    screening.to_csv(scsv, index=False)
    sheet = pd.DataFrame([
        {"review_id": _rid(screening.iloc[2].to_dict()), "decisao_humana": "i", "nota_humana": ""},
        {"review_id": _rid(screening.iloc[3].to_dict()), "decisao_humana": "", "nota_humana": ""},
    ])
    shcsv = tmp_path / "03_revisao_duvidas.csv"
    sheet.to_csv(shcsv, index=False)

    rev = tmp_path / "03_screening_revisado.csv"
    inc = tmp_path / "03_incluidos_final.csv"
    revisao_ingest.run(screening_csv=scsv, sheet_csv=shcsv,
                        revisado_csv=rev, incluidos_csv=inc)

    r = pd.read_csv(rev, keep_default_na=False)
    assert len(r) == 4
    assert {"decisao_final_revisada", "origem_decisao", "nota_humana"} <= set(r.columns)
    i = pd.read_csv(inc, keep_default_na=False)
    # incluídos = bi (llm) + s1 (humano i) + s2 (pendente→incluir) = 3
    assert len(i) == 3
    assert "10.1/be" not in set(i["doi"])
    out = capsys.readouterr().out
    assert "pendente" in out.lower()  # avisa que há pendentes
    assert "1" in out  # 1 pendente


def test_run_invalid_sheet_aborts_without_writing(tmp_path: Path):
    screening = pd.DataFrame([_row("duvida", "duvida", "incluir", "10.1/s1")])
    scsv = tmp_path / "s.csv"; screening.to_csv(scsv, index=False)
    sheet = pd.DataFrame([
        {"review_id": _rid(screening.iloc[0].to_dict()), "decisao_humana": "talvez", "nota_humana": ""},
    ])
    shcsv = tmp_path / "sh.csv"; sheet.to_csv(shcsv, index=False)
    rev = tmp_path / "rev.csv"; inc = tmp_path / "inc.csv"
    with pytest.raises(ValueError):
        revisao_ingest.run(screening_csv=scsv, sheet_csv=shcsv,
                            revisado_csv=rev, incluidos_csv=inc)
    assert not rev.exists() and not inc.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_revisao_ingest.py -k "run_writes or invalid_sheet" -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'run'`

- [ ] **Step 3: Write minimal implementation (append)**

```python
# adicionar a scripts/screening/revisao_ingest.py
def run(screening_csv: Path, sheet_csv: Path,
        revisado_csv: Path, incluidos_csv: Path) -> None:
    screening = pd.read_csv(screening_csv, encoding="utf-8", keep_default_na=False)
    sheet = pd.read_csv(sheet_csv, encoding="utf-8", keep_default_na=False)
    # apply_decisions levanta ValueError em valor inválido ANTES de escrever
    revisado = apply_decisions(screening, sheet)

    revisado_csv.parent.mkdir(parents=True, exist_ok=True)
    revisado.to_csv(revisado_csv, index=False, encoding="utf-8")
    incluidos = revisado[revisado["decisao_final_revisada"] == "incluir"]
    incluidos.to_csv(incluidos_csv, index=False, encoding="utf-8")

    n_pend = int((revisado["origem_decisao"] == "pendente").sum())
    n_hum = int((revisao_humano := revisado["origem_decisao"] == "humano").sum())
    n_inc = len(incluidos)
    print(f"Revisão ingest: {len(revisado)} registros | "
          f"{n_inc} incluídos | {n_hum} decididos por humano | "
          f"{n_pend} PENDENTES")
    if n_pend:
        print(f"  ⚠ {n_pend} dúvidas ainda sem decisão (contam como incluir). "
              f"Rode PRISMA/Plano 4 só com 0 pendentes.")
    print(f"  → {revisado_csv}\n  → {incluidos_csv}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Ingere a planilha de revisão das dúvidas.")
    p.add_argument("--screening", type=Path, required=True)
    p.add_argument("--sheet", type=Path, required=True)
    p.add_argument("--revisado", type=Path, required=True)
    p.add_argument("--incluidos", type=Path, required=True)
    a = p.parse_args(argv)
    run(screening_csv=a.screening, sheet_csv=a.sheet,
        revisado_csv=a.revisado, incluidos_csv=a.incluidos)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_revisao_ingest.py -v`
Expected: PASS (17 passed). Run full suite: `source .venv/bin/activate && pytest -q` (expect 100 prior + novos; report actual).

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/revisao_ingest.py tests/screening/test_revisao_ingest.py
git commit -m "feat(revisao): revisao_ingest run + CLI (saídas + aviso de pendentes)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Makefile — alvos `revisao-export` e `revisao-ingest`

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Editar o Makefile**

Adicionar, após o alvo `screening-kappa` (e ANTES de `fetch`), os dois alvos abaixo. Recipe lines com TAB (não espaços), `$(PYTHON)` e `$(DATA_PROC)` já são variáveis do Makefile:

```makefile
.PHONY: revisao-export
revisao-export:
	$(PYTHON) -m scripts.screening.revisao_export \
	    --screening $(DATA_PROC)/03_screening_ta.csv \
	    --sheet $(DATA_PROC)/03_revisao_duvidas.csv

.PHONY: revisao-ingest
revisao-ingest:
	$(PYTHON) -m scripts.screening.revisao_ingest \
	    --screening $(DATA_PROC)/03_screening_ta.csv \
	    --sheet $(DATA_PROC)/03_revisao_duvidas.csv \
	    --revisado $(DATA_PROC)/03_screening_revisado.csv \
	    --incluidos $(DATA_PROC)/03_incluidos_final.csv
```

NÃO adicionar esses alvos a `screen` (exigem ação manual humana entre export e ingest).

- [ ] **Step 2: Verificar sintaxe**

Run: `make -n revisao-export && make -n revisao-ingest`
Expected: imprime os comandos sem erro de Make ("missing separator" = espaço no lugar de TAB). Rodar também `make -n screen` para confirmar que `screen` não foi afetado.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "build(revisao): alvos revisao-export e revisao-ingest

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Nota no protocolo §7 + verificação final + tag

**Files:**
- Modify: `protocols/slr_protocol.md`

- [ ] **Step 1: Atualizar `protocols/slr_protocol.md` §7**

Ler `protocols/slr_protocol.md`, localizar a Seção 7 (Processo de seleção), no item "Screening (título+resumo)". Acrescentar ao final desse item o parágrafo:

```markdown

A revisão humana do screening foi operacionalizada em 2026-05-16: o pré-filtro
dual-LLM (Sonnet 4.6 + Haiku 4.5, κ=0.602) classificou 2605 registros; os 462
"ambos-incluir" e 1278 "ambos-excluir" foram aceitos pela concordância dos dois
modelos, e os 865 casos ambíguos (decisão final "incluir" não unânime — passados
pela união conservadora por "dúvida"/divergência) foram adjudicados manualmente
pelo revisor via planilha (`scripts/screening/revisao_export.py` →
`revisao_ingest.py`), conforme `docs/superpowers/specs/2026-05-16-revisao-manual-duvidas-design.md`.
Isso concretiza o compromisso de "LLM-as-judge + revisão humana" deste protocolo.
```

- [ ] **Step 2: Verificação final**

Run: `source .venv/bin/activate && pytest -q`
Expected: todos verdes (100 prévios + novos dos testes de export/ingest).

Run (dry-run no corpus real, sem custo):
```bash
source .venv/bin/activate && python -m scripts.screening.revisao_export \
  --screening data/processed/03_screening_ta.csv \
  --sheet /tmp/03_revisao_duvidas.csv && \
  wc -l /tmp/03_revisao_duvidas.csv && \
  python -c "import pandas as pd; d=pd.read_csv('/tmp/03_revisao_duvidas.csv', keep_default_na=False); print('linhas:', len(d), '| colunas:', list(d.columns)[:3], '| decididas:', (d.decisao_humana.str.strip()!=\"\").sum())"
```
Expected: ~865 linhas, colunas iniciando em `review_id, decisao_humana, nota_humana`, 0 decididas.

Run (ingest com a planilha vazia → tudo pendente, corpus = 1327):
```bash
source .venv/bin/activate && python -m scripts.screening.revisao_ingest \
  --screening data/processed/03_screening_ta.csv \
  --sheet /tmp/03_revisao_duvidas.csv \
  --revisado /tmp/03_screening_revisado.csv \
  --incluidos /tmp/03_incluidos_final.csv
```
Expected: imprime `2605 registros | 1327 incluídos | 0 decididos por humano | 865 PENDENTES` e o aviso. Confirma coerência (1327 = 462 + 865 pendentes-como-incluir).

- [ ] **Step 3: Commit + tag**

```bash
git add protocols/slr_protocol.md
git commit -m "docs(protocol): §7 — revisão humana das dúvidas operacionalizada

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git tag -a v0.4.0-revisao-duvidas -m "Revisão manual das dúvidas: export/ingest planilha

865 soft-includes adjudicados pelo revisor via planilha CSV.
Corpus revisado → 03_incluidos_final.csv (entrada do Plano 4).
Protocolo §7 atualizado. Testes verdes."
git tag -l
```

---

## Self-Review (preenchido pelo autor do plano)

**Cobertura do spec:** §2 decisões (subconjunto soft-include, planilha) → Tasks 1,2,4; §3 arquitetura (2 scripts) → Tasks 1-7; §4 fluxo → Tasks 4,7; §5 schema planilha → Task 2 (SHEET_COLS idêntico ao spec); §6 proteção/não-destrutivo → Task 3 (merge_preserve) + Task 4 (e2e re-export); §7 validação/regra → Tasks 5,6; §8 saídas → Task 7; §9 integração (Makefile, protocolo; prisma_flow fora de escopo) → Tasks 8,9; §10 testes → todas; §12 critérios de sucesso → Task 9. Sem lacunas. `prisma_flow.py` corretamente NÃO tocado (spec §9/§11 explicita fora de escopo).

**Placeholders:** nenhum "TBD/TODO"; todo passo de código mostra o código completo. Comandos com saída esperada explícita.

**Consistência de tipos:** `soft_includes(df)->DataFrame` (Task 1) consumido por `build_sheet(soft_df)->DataFrame` (Task 2); `SHEET_COLS` definido uma vez (Task 2) e reusado; `merge_preserve(fresh, existing|None)->DataFrame` (Task 3) usado por `run` (Task 4); `normalize_decisao(raw)->str` (Task 5) usado por `apply_decisions(screening, sheet)->DataFrame` (Task 6) que adiciona `decisao_final_revisada`/`origem_decisao`/`nota_humana`, lidas por `run` (Task 7). `review_id == custom_id(cache_key(row))` consistente entre export (Task 2) e ingest (Task 6) — ambos importam de `scripts.screening.llm.batch_client`. `keep_default_na=False` usado consistentemente na leitura de CSVs para que célula vazia seja `""` e não `NaN` (coerente com `normalize_decisao` tratando `""`→pendente e com os testes que usam `keep_default_na=False`).
