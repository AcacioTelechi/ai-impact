# Plano 2 — Execução da Busca (F3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar os scripts de busca (OpenAlex via API + BibTeX importer + snowballing + summary), executar as buscas em todas as bases (4 idiomas em OpenAlex + imports manuais de WoS/Scopus/SciELO), e produzir o `data/processed/02_corpus_dedup.csv` pronto para o screening (Plano 3).

**Architecture:**
- Quatro scripts independentes em `scripts/search/`: `openalex_search.py`, `import_bibtex.py`, `snowball.py`, `summary.py`.
- Cada script é um módulo Python com função `run()` pura + CLI via `_cli()`; testes pytest com mocks para chamadas HTTP.
- Outputs em `data/raw/searches/{base}_{YYYY-MM-DD}.csv` + `.meta.json` (não versionados; `.gitignore` cobre).
- Pipeline alimenta `scripts.screening.consolidate` (Plano 1) sem mudanças.

**Tech Stack:**
- Python 3.12 com `.venv` ativado: `source /home/acacio/dev/pessoal/ai-impact/.venv/bin/activate`.
- Novas deps: `bibtexparser>=2.0`, `langdetect>=1.0.9`.
- Existentes em uso: `requests`, `tenacity`, `pandas`, `pytest`.

**Convenções aplicadas:**
- Working directory: `/home/acacio/dev/pessoal/ai-impact/`.
- Sempre rodar com venv ativado: `pytest`, `python -m ...` direto (sem prefixo `uv run`).
- Cada tarefa de código segue TDD: teste falha → implementação → teste passa → commit.
- Cada execução de busca produz CSV + .meta.json sibling.

---

## Task 1: Adicionar dependências `bibtexparser` e `langdetect`

**Files:**
- Modify: `pyproject.toml` (auto via `uv add`)
- Modify: `uv.lock` (auto)

- [ ] **Step 1: Adicionar deps via uv**

```bash
uv add "bibtexparser>=2.0" "langdetect>=1.0.9"
```

Expected: pyproject.toml atualizado, uv.lock atualizado, ambas as libs instaladas no venv.

- [ ] **Step 2: Verificar imports**

```bash
source /home/acacio/dev/pessoal/ai-impact/.venv/bin/activate
python -c "import bibtexparser, langdetect; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add bibtexparser and langdetect deps for search workflow"
```

---

## Task 2: Atualizar `.gitignore` para área de exports manuais

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Adicionar ao final de `.gitignore`**

```gitignore

# Plan 2: manual export staging area
data/raw/searches/manual/
```

> Nota: `data/raw/**/*.csv` e `data/raw/**/*.json` já estão ignorados (Plano 1, Task 2). Estamos adicionando a área `manual/` separadamente porque contém `.bib` (não coberto pela linha do `.csv`).

- [ ] **Step 2: Criar estrutura de diretórios para staging manual**

```bash
mkdir -p data/raw/searches/manual/wos
mkdir -p data/raw/searches/manual/scopus
mkdir -p data/raw/searches/manual/scielo
```

Esses diretórios não são versionados (cobertos pela linha nova do .gitignore). Eles existem só na sua máquina como pastas onde você vai dropar os `.bib` exportados.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore manual bibtex staging area"
```

---

## Task 3: Pacote `scripts/search/` com `__init__.py`

**Files:**
- Create: `scripts/search/__init__.py`
- Create: `tests/search/__init__.py`

- [ ] **Step 1: Criar __init__ vazios**

```bash
touch scripts/search/__init__.py tests/search/__init__.py
```

Esses arquivos já existem como diretórios desde o Plano 1 Task 2; só faltam os `__init__.py`.

- [ ] **Step 2: Verificar import**

```bash
source /home/acacio/dev/pessoal/ai-impact/.venv/bin/activate
python -c "import scripts.search; import tests.search; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add scripts/search/__init__.py tests/search/__init__.py
git commit -m "chore(search): scaffold scripts/search package"
```

---

## Task 4: Helper para reconstruir abstract a partir do `abstract_inverted_index` da OpenAlex

**Files:**
- Create: `scripts/search/openalex_utils.py`
- Create: `tests/search/test_openalex_utils.py`

A reconstrução do abstract da OpenAlex é não-trivial e merece isolamento. O índice invertido mapeia cada palavra para suas posições no texto; reconstruir = inverter o mapeamento e juntar.

- [ ] **Step 1: Escrever teste em `tests/search/test_openalex_utils.py`**

```python
from scripts.search.openalex_utils import reconstruct_abstract


def test_reconstruct_abstract_simple() -> None:
    idx = {"AI": [0], "and": [1], "labor": [2], "markets": [3]}
    assert reconstruct_abstract(idx) == "AI and labor markets"


def test_reconstruct_abstract_repeated_words() -> None:
    idx = {"the": [0, 4], "AI": [1], "affects": [2], "labor": [3]}
    # positions: 0=the, 1=AI, 2=affects, 3=labor, 4=the
    assert reconstruct_abstract(idx) == "the AI affects labor the"


def test_reconstruct_abstract_empty() -> None:
    assert reconstruct_abstract({}) == ""
    assert reconstruct_abstract(None) == ""


def test_reconstruct_abstract_handles_gaps() -> None:
    # Position 2 missing — should still produce a string
    idx = {"a": [0], "c": [3]}
    result = reconstruct_abstract(idx)
    assert "a" in result and "c" in result
```

- [ ] **Step 2: Rodar teste, confirmar FAIL**

```bash
source /home/acacio/dev/pessoal/ai-impact/.venv/bin/activate
pytest tests/search/test_openalex_utils.py -v
```

Expected: ImportError de `scripts.search.openalex_utils`.

- [ ] **Step 3: Implementar `scripts/search/openalex_utils.py`**

```python
"""Utilities for parsing OpenAlex API responses."""
from __future__ import annotations


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """Rebuild a text abstract from OpenAlex's `abstract_inverted_index`.

    OpenAlex stores abstracts as `{word: [positions]}`. This function inverts
    the mapping to a position-ordered list of words and joins them.

    Missing positions (gaps in the indices) are silently skipped — only words
    that have an explicit position are rendered.
    """
    if not inverted_index:
        return ""
    by_position: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            by_position[pos] = word
    ordered = [by_position[p] for p in sorted(by_position)]
    return " ".join(ordered)
```

- [ ] **Step 4: Rodar teste, confirmar PASS**

```bash
pytest tests/search/test_openalex_utils.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/search/openalex_utils.py tests/search/test_openalex_utils.py
git commit -m "feat(search): add OpenAlex abstract inverted-index reconstructor"
```

---

## Task 5: Helper para extrair tokens da string de busca

**Files:**
- Modify: `scripts/search/openalex_utils.py`
- Modify: `tests/search/test_openalex_utils.py`

As strings de busca em `protocols/search_strings/*.txt` estão no formato:
```
(
  "termo1" OR "termo2" OR ...
)
AND
(
  "termo3" OR ...
)
AND
(
  "termo4" OR ...
)
```

Precisamos extrair os tokens de cada bloco para construir queries OpenAlex (que não tem booleano nativo).

- [ ] **Step 1: Adicionar testes**

Adicionar ao final de `tests/search/test_openalex_utils.py`:

```python
from scripts.search.openalex_utils import parse_query_blocks


def test_parse_query_blocks_extracts_three_groups() -> None:
    query = '''
    (
      "artificial intelligence" OR "machine learning"
    )
    AND
    (
      "employment" OR "labor market"
    )
    AND
    (
      "impact" OR "effect"
    )
    '''
    blocks = parse_query_blocks(query)
    assert len(blocks) == 3
    assert "artificial intelligence" in blocks[0]
    assert "machine learning" in blocks[0]
    assert "employment" in blocks[1]
    assert "impact" in blocks[2]


def test_parse_query_blocks_strips_wildcards() -> None:
    query = '("ai") AND ("employment*")'
    blocks = parse_query_blocks(query)
    # wildcards stripped — OpenAlex doesn't use them
    assert blocks[1] == ["employment"]


def test_parse_query_blocks_ignores_comments_and_blank_lines() -> None:
    query = '''
    # English search string
    # Version 1.0

    ("ai") AND ("jobs")
    '''
    blocks = parse_query_blocks(query)
    assert blocks == [["ai"], ["jobs"]]
```

- [ ] **Step 2: Rodar testes, confirmar 3 FAIL novos**

```bash
pytest tests/search/test_openalex_utils.py -v
```

Expected: 4 passed (anteriores) + 3 FAIL.

- [ ] **Step 3: Adicionar `parse_query_blocks` a `scripts/search/openalex_utils.py`**

Adicionar ao final do arquivo:

```python
import re


def parse_query_blocks(query: str) -> list[list[str]]:
    """Extract token lists from a WoS-style boolean query.

    Input format (lines starting with `#` are ignored):
        ( "a" OR "b" ) AND ( "c" OR "d" ) AND ( "e" )

    Returns a list of blocks, each block a list of quoted tokens (without
    quotes, without trailing wildcards).
    """
    # Strip comments
    cleaned = "\n".join(
        line for line in query.splitlines() if not line.strip().startswith("#")
    )
    # Find every quoted token
    # Split by AND first, then extract quoted terms per block
    parts = re.split(r"\bAND\b", cleaned, flags=re.IGNORECASE)
    blocks: list[list[str]] = []
    for part in parts:
        tokens = re.findall(r'"([^"]+)"', part)
        # strip trailing wildcards (OpenAlex doesn't use *)
        tokens = [t.rstrip("*").strip() for t in tokens if t.strip()]
        if tokens:
            blocks.append(tokens)
    return blocks
```

- [ ] **Step 4: Rodar testes, confirmar 7 passed**

```bash
pytest tests/search/test_openalex_utils.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/search/openalex_utils.py tests/search/test_openalex_utils.py
git commit -m "feat(search): add boolean query parser for OpenAlex adaptation"
```

---

## Task 6: Núcleo do `openalex_search.py` — flatten de record único

**Files:**
- Create: `scripts/search/openalex_search.py`
- Create: `tests/search/test_openalex_search.py`

Antes de implementar a chamada à API real, isolamos a função pura que converte um JSON record da OpenAlex para uma linha do nosso schema.

- [ ] **Step 1: Escrever teste em `tests/search/test_openalex_search.py`**

```python
from scripts.search.openalex_search import flatten_record


def test_flatten_record_maps_basic_fields() -> None:
    rec = {
        "doi": "https://doi.org/10.1234/abc",
        "title": "AI and the Labor Market",
        "publication_year": 2023,
        "language": "en",
        "authorships": [
            {"author": {"display_name": "Acemoglu, Daron"}},
            {"author": {"display_name": "Restrepo, Pascual"}},
        ],
        "primary_location": {"source": {"display_name": "American Economic Review"}},
        "abstract_inverted_index": {"AI": [0], "affects": [1], "jobs": [2]},
    }
    row = flatten_record(rec, default_lang="en")
    assert row["source"] == "openalex"
    assert row["doi"] == "10.1234/abc"
    assert row["title"] == "AI and the Labor Market"
    assert row["year"] == 2023
    assert row["language"] == "en"
    assert row["authors"] == "Acemoglu, Daron; Restrepo, Pascual"
    assert row["venue"] == "American Economic Review"
    assert row["abstract"] == "AI affects jobs"


def test_flatten_record_missing_optional_fields() -> None:
    rec = {
        "doi": None,
        "title": "Untitled",
        "publication_year": 2020,
        "authorships": [],
        "primary_location": None,
        "abstract_inverted_index": None,
        "language": None,
    }
    row = flatten_record(rec, default_lang="pt")
    assert row["doi"] == ""
    assert row["authors"] == ""
    assert row["venue"] == ""
    assert row["abstract"] == ""
    assert row["language"] == "pt"  # falls back to default_lang


def test_flatten_record_strips_doi_prefix() -> None:
    rec = {"doi": "https://doi.org/10.X/Y", "title": "T", "publication_year": 2020,
           "authorships": [], "primary_location": None,
           "abstract_inverted_index": None, "language": "en"}
    row = flatten_record(rec, default_lang="en")
    assert row["doi"] == "10.x/y"
```

- [ ] **Step 2: Rodar teste, confirmar FAIL**

```bash
pytest tests/search/test_openalex_search.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar primeira versão de `scripts/search/openalex_search.py`**

```python
"""Pipeline component: search OpenAlex via REST API.

Reads search strings from `protocols/search_strings/{lang}.txt`, queries
OpenAlex, paginates, flattens results, and writes a CSV + .meta.json pair.

CLI:
    python -m scripts.search.openalex_search \\
        --query-file protocols/search_strings/en.txt \\
        --lang en \\
        --output data/raw/searches/openalex_en_2026-05-15.csv \\
        --meta-output data/raw/searches/openalex_en_2026-05-15.meta.json \\
        --email user@example.com
"""
from __future__ import annotations

from scripts.search.openalex_utils import reconstruct_abstract
from scripts.utils.normalization import normalize_doi


def flatten_record(rec: dict, default_lang: str) -> dict:
    """Map an OpenAlex JSON record to our standard 8-column schema."""
    authorships = rec.get("authorships") or []
    authors = "; ".join(
        a.get("author", {}).get("display_name", "")
        for a in authorships
        if a.get("author", {}).get("display_name")
    )
    primary = rec.get("primary_location") or {}
    source_obj = primary.get("source") or {}
    venue = source_obj.get("display_name") or ""
    return {
        "source": "openalex",
        "doi": normalize_doi(rec.get("doi")),
        "title": rec.get("title") or "",
        "authors": authors,
        "year": rec.get("publication_year") or "",
        "abstract": reconstruct_abstract(rec.get("abstract_inverted_index")),
        "venue": venue,
        "language": rec.get("language") or default_lang,
    }
```

- [ ] **Step 4: Rodar teste, confirmar 3 passed**

```bash
pytest tests/search/test_openalex_search.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/search/openalex_search.py tests/search/test_openalex_search.py
git commit -m "feat(search): add OpenAlex record flattener"
```

---

## Task 7: `openalex_search.py` — fetch paginado com retry

**Files:**
- Modify: `scripts/search/openalex_search.py`
- Modify: `tests/search/test_openalex_search.py`

Agora a função que executa a chamada à API. Vamos isolar `_fetch_page` para facilitar mock.

- [ ] **Step 1: Adicionar testes**

Adicionar ao final de `tests/search/test_openalex_search.py`:

```python
from unittest.mock import patch, MagicMock

from scripts.search.openalex_search import fetch_all


def _mock_response(status_code: int, json_data: dict | None = None) -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data or {}
    r.raise_for_status = MagicMock()
    return r


def test_fetch_all_handles_single_page() -> None:
    page = {
        "results": [
            {"doi": "10.1/a", "title": "A", "publication_year": 2020,
             "authorships": [], "primary_location": None,
             "abstract_inverted_index": None, "language": "en"}
        ],
        "meta": {"next_cursor": None, "count": 1},
    }
    with patch("scripts.search.openalex_search.requests.get",
               return_value=_mock_response(200, page)):
        rows, total = fetch_all(
            search="ai jobs",
            date_from="2013-01-01", date_to="2025-12-31",
            lang="en", email="x@y.com",
        )
    assert total == 1
    assert len(rows) == 1
    assert rows[0]["doi"] == "10.1/a"


def test_fetch_all_paginates() -> None:
    page1 = {
        "results": [
            {"doi": f"10.1/{i}", "title": f"T{i}", "publication_year": 2020,
             "authorships": [], "primary_location": None,
             "abstract_inverted_index": None, "language": "en"}
            for i in range(3)
        ],
        "meta": {"next_cursor": "cursor-abc", "count": 5},
    }
    page2 = {
        "results": [
            {"doi": f"10.1/{i}", "title": f"T{i}", "publication_year": 2020,
             "authorships": [], "primary_location": None,
             "abstract_inverted_index": None, "language": "en"}
            for i in range(3, 5)
        ],
        "meta": {"next_cursor": None, "count": 5},
    }
    responses = [_mock_response(200, page1), _mock_response(200, page2)]
    with patch("scripts.search.openalex_search.requests.get", side_effect=responses):
        rows, total = fetch_all(
            search="ai jobs",
            date_from="2013-01-01", date_to="2025-12-31",
            lang="en", email="x@y.com",
        )
    assert total == 5
    assert len(rows) == 5
```

- [ ] **Step 2: Rodar testes, confirmar 2 FAIL novos**

```bash
pytest tests/search/test_openalex_search.py -v
```

Expected: 3 passed + 2 FAIL (fetch_all not defined).

- [ ] **Step 3: Adicionar `fetch_all` a `scripts/search/openalex_search.py`**

Adicionar ao final do arquivo:

```python
import requests
from tenacity import retry, stop_after_attempt, wait_exponential


OPENALEX_BASE = "https://api.openalex.org/works"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _fetch_page(params: dict, email: str) -> dict:
    headers = {"User-Agent": f"ai-impact/0.2.0 (mailto:{email})"}
    r = requests.get(OPENALEX_BASE, params=params, headers=headers, timeout=30)
    if r.status_code == 429:
        r.raise_for_status()  # triggers retry
    r.raise_for_status()
    return r.json()


def fetch_all(
    search: str,
    date_from: str,
    date_to: str,
    lang: str,
    email: str,
    per_page: int = 200,
) -> tuple[list[dict], int]:
    """Page through OpenAlex /works results and return all flattened rows.

    Returns (rows, total_count_reported_by_api).
    """
    rows: list[dict] = []
    cursor = "*"
    total = 0
    while cursor is not None:
        params = {
            "search": search,
            "filter": (
                f"from_publication_date:{date_from},"
                f"to_publication_date:{date_to},"
                f"type:article|preprint|book-chapter"
            ),
            "per_page": per_page,
            "cursor": cursor,
        }
        data = _fetch_page(params, email)
        meta = data.get("meta", {})
        total = meta.get("count", total)
        for rec in data.get("results", []):
            rows.append(flatten_record(rec, default_lang=lang))
        cursor = meta.get("next_cursor")
    return rows, total
```

- [ ] **Step 4: Rodar testes, confirmar 5 passed**

```bash
pytest tests/search/test_openalex_search.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/search/openalex_search.py tests/search/test_openalex_search.py
git commit -m "feat(search): add OpenAlex paginated fetch with retry"
```

---

## Task 8: `openalex_search.py` — pós-filtro e orquestração `run()` com CLI

**Files:**
- Modify: `scripts/search/openalex_search.py`
- Modify: `tests/search/test_openalex_search.py`

A função `run()` orquestra: parse_query_blocks → executa fetch_all uma vez por (token_ia, token_trabalho) → união → pós-filtro local por keywords → CSV + .meta.json.

Para tornar testável, isolamos o pós-filtro como função separada.

- [ ] **Step 1: Adicionar testes**

```python
import json
from pathlib import Path

from scripts.search.openalex_search import filter_by_keywords, run


def test_filter_by_keywords_keeps_matches() -> None:
    rows = [
        {"title": "AI and labor markets", "abstract": ""},
        {"title": "Cooking with AI", "abstract": ""},
        {"title": "Random topic", "abstract": "discusses employment"},
        {"title": "Just random", "abstract": "no keywords"},
    ]
    blocks = [["AI"], ["labor", "employment"]]
    kept = filter_by_keywords(rows, blocks)
    titles = {r["title"] for r in kept}
    assert "AI and labor markets" in titles
    assert "Random topic" in titles
    assert "Cooking with AI" not in titles
    assert "Just random" not in titles


def test_run_end_to_end_with_mock(tmp_path: Path) -> None:
    """Mock the network call, verify CSV + .meta.json produced."""
    query_file = tmp_path / "q.txt"
    query_file.write_text('("ai") AND ("jobs")', encoding="utf-8")

    fake_response = {
        "results": [
            {"doi": "10.1/a", "title": "AI and jobs", "publication_year": 2020,
             "authorships": [], "primary_location": None,
             "abstract_inverted_index": None, "language": "en"}
        ],
        "meta": {"next_cursor": None, "count": 1},
    }

    with patch("scripts.search.openalex_search.requests.get",
               return_value=_mock_response(200, fake_response)):
        run(
            query_file=query_file,
            lang="en",
            date_from="2013-01-01",
            date_to="2025-12-31",
            output=tmp_path / "out.csv",
            meta_output=tmp_path / "out.meta.json",
            email="x@y.com",
        )

    import pandas as pd
    df = pd.read_csv(tmp_path / "out.csv")
    assert len(df) >= 1
    assert "AI and jobs" in df["title"].tolist()

    meta = json.loads((tmp_path / "out.meta.json").read_text())
    assert meta["base"] == "openalex"
    assert meta["lang"] == "en"
    assert meta["n_after_filters"] >= 1
    assert "csv_sha256" in meta
    assert len(meta["csv_sha256"]) == 64  # SHA-256 hex
```

- [ ] **Step 2: Rodar testes, confirmar 2 FAIL novos**

```bash
pytest tests/search/test_openalex_search.py -v
```

Expected: 5 passed + 2 FAIL.

- [ ] **Step 3: Adicionar ao final de `scripts/search/openalex_search.py`**

```python
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

from scripts.search.openalex_utils import parse_query_blocks
from scripts.utils.io import sha256_file, write_corpus_csv


def filter_by_keywords(rows: list[dict], blocks: list[list[str]]) -> list[dict]:
    """Keep rows that match at least one keyword from EACH block.

    Each block is a list of synonyms (OR). All blocks must match (AND).
    Matching is case-insensitive against title + abstract.
    """
    kept: list[dict] = []
    for row in rows:
        text = f"{row.get('title', '')} {row.get('abstract', '')}".lower()
        if all(any(tok.lower() in text for tok in block) for block in blocks):
            kept.append(row)
    return kept


def run(
    query_file: Path,
    lang: str,
    date_from: str,
    date_to: str,
    output: Path,
    meta_output: Path,
    email: str,
) -> None:
    """Execute an OpenAlex search end-to-end and write CSV + .meta.json."""
    query_text = Path(query_file).read_text(encoding="utf-8")
    blocks = parse_query_blocks(query_text)

    # Build a single 'search' string from the first block (IA terms) — OpenAlex
    # full-text matcher handles the rest via the post-filter.
    search_string = " OR ".join(blocks[0]) if blocks else ""

    all_rows, n_raw = fetch_all(
        search=search_string,
        date_from=date_from,
        date_to=date_to,
        lang=lang,
        email=email,
    )
    # Dedup by openalex-side DOI within this batch
    seen = set()
    deduped = []
    for r in all_rows:
        key = r["doi"] or f"{r['title']}-{r['year']}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    filtered = filter_by_keywords(deduped, blocks) if blocks else deduped

    output.parent.mkdir(parents=True, exist_ok=True)
    write_corpus_csv(pd.DataFrame(filtered), output)

    meta = {
        "base": "openalex",
        "lang": lang,
        "query_used": query_text,
        "query_string_version": "1.0",
        "date_from": date_from,
        "date_to": date_to,
        "executed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "n_hits_raw": int(n_raw),
        "n_after_filters": int(len(filtered)),
        "csv_sha256": sha256_file(output),
        "tool_version": "ai-impact 0.2.0",
        "notes": "",
    }
    meta_output.parent.mkdir(parents=True, exist_ok=True)
    meta_output.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OpenAlex {lang}: {n_raw} hits → {len(filtered)} after filter → {output}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--query-file", type=Path, required=True)
    p.add_argument("--lang", required=True, choices=["en", "pt", "es", "fr"])
    p.add_argument("--date-from", default="2013-01-01")
    p.add_argument("--date-to", default="2025-12-31")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--meta-output", type=Path, required=True)
    p.add_argument("--email", required=True)
    a = p.parse_args(argv)
    run(
        query_file=a.query_file, lang=a.lang,
        date_from=a.date_from, date_to=a.date_to,
        output=a.output, meta_output=a.meta_output, email=a.email,
    )
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Rodar todos os testes do openalex_search**

```bash
pytest tests/search/test_openalex_search.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/search/openalex_search.py tests/search/test_openalex_search.py
git commit -m "feat(search): add OpenAlex search runner with post-filter and metadata"
```

---

## Task 9: `import_bibtex.py` — parser + mapper para WoS

**Files:**
- Create: `scripts/search/import_bibtex.py`
- Create: `tests/search/test_import_bibtex.py`
- Create: `tests/fixtures/wos_sample.bib`

- [ ] **Step 1: Criar fixture `tests/fixtures/wos_sample.bib`**

```bibtex
@article{Smith2020,
   author = {Smith, John and Doe, Jane},
   title = {Artificial Intelligence and Employment in the US},
   journal = {American Economic Review},
   year = {2020},
   doi = {10.1234/aer.2020.001},
   abstract = {We study AI exposure across US occupations.},
   language = {English},
}

@article{Muller2022,
   author = {Müller, Hans and Dupont, Claire},
   title = {Robots and Manufacturing Jobs in Europe},
   journal = {Labour Economics},
   year = {2022},
   doi = {10.1234/lab.2022.077},
   abstract = {DiD analysis of industrial robot adoption.},
   language = {English},
}
```

- [ ] **Step 2: Escrever testes em `tests/search/test_import_bibtex.py`**

```python
from pathlib import Path

import pandas as pd

from scripts.search.import_bibtex import map_wos, parse_bib_files


FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_map_wos_normalizes_authors_and_doi() -> None:
    entry = {
        "author": "Smith, John and Doe, Jane",
        "title": "Title T",
        "journal": "AER",
        "year": "2020",
        "doi": "https://doi.org/10.1234/ABC",
        "abstract": "abs",
        "language": "English",
    }
    row = map_wos(entry)
    assert row["source"] == "wos"
    assert row["doi"] == "10.1234/abc"
    assert row["authors"] == "Smith, J.; Doe, J."
    assert row["year"] == 2020
    assert row["venue"] == "AER"
    assert row["language"] == "en"


def test_map_wos_handles_missing_optional_fields() -> None:
    entry = {"title": "T", "year": "2020"}
    row = map_wos(entry)
    assert row["doi"] == ""
    assert row["authors"] == ""
    assert row["abstract"] == ""
    assert row["venue"] == ""
    assert row["language"] == "en"  # default


def test_parse_bib_files_loads_fixture() -> None:
    entries = parse_bib_files([FIXTURES / "wos_sample.bib"])
    assert len(entries) == 2
    titles = {e["title"] for e in entries}
    assert "Artificial Intelligence and Employment in the US" in titles
    assert "Robots and Manufacturing Jobs in Europe" in titles


def test_parse_bib_files_preserves_diacritics() -> None:
    entries = parse_bib_files([FIXTURES / "wos_sample.bib"])
    authors_all = " | ".join(e.get("author", "") for e in entries)
    assert "Müller" in authors_all
```

- [ ] **Step 3: Rodar testes, confirmar FAIL**

```bash
pytest tests/search/test_import_bibtex.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implementar primeira parte de `scripts/search/import_bibtex.py`**

```python
"""Pipeline component: import BibTeX exports (WoS/Scopus/SciELO) into the standard CSV schema.

CLI:
    python -m scripts.search.import_bibtex \\
        --source wos \\
        --files data/raw/searches/manual/wos/*.bib \\
        --output data/raw/searches/wos_2026-05-15.csv \\
        --meta-output data/raw/searches/wos_2026-05-15.meta.json \\
        --query-string "$(cat protocols/search_strings/en.txt)"
"""
from __future__ import annotations

from pathlib import Path

import bibtexparser

from scripts.utils.normalization import normalize_doi


LANG_MAP = {
    "english": "en", "en": "en", "eng": "en",
    "portuguese": "pt", "pt": "pt", "por": "pt", "português": "pt",
    "spanish": "es", "es": "es", "spa": "es", "español": "es",
    "french": "fr", "fr": "fr", "fra": "fr", "français": "fr",
}


def _normalize_language(raw: str | None) -> str:
    if not raw:
        return "en"
    key = raw.strip().lower()
    return LANG_MAP.get(key, "en")


def _strip_braces(s: str) -> str:
    return s.replace("{", "").replace("}", "").strip() if s else ""


def _normalize_authors(authors_field: str | None) -> str:
    """Convert 'Smith, John and Doe, Jane' to 'Smith, J.; Doe, J.'"""
    if not authors_field:
        return ""
    parts = [a.strip() for a in authors_field.split(" and ")]
    normalized = []
    for p in parts:
        p = _strip_braces(p)
        if "," in p:
            last, _, first = p.partition(",")
            initials = ".".join(w[0].upper() for w in first.strip().split() if w)
            normalized.append(f"{last.strip()}, {initials}." if initials else last.strip())
        else:
            normalized.append(p)
    return "; ".join(normalized)


def parse_bib_files(files: list[Path]) -> list[dict]:
    """Parse one or more .bib files, returning a flat list of entry dicts."""
    all_entries: list[dict] = []
    for f in files:
        library = bibtexparser.parse_file(str(f))
        for entry in library.entries:
            d = {k: v for k, v in entry.fields_dict.items()}
            # bibtexparser v2 returns Field objects; extract value strings
            d = {k: (v.value if hasattr(v, "value") else v) for k, v in d.items()}
            d["entry_type"] = entry.entry_type
            d["key"] = entry.key
            all_entries.append(d)
    return all_entries


def map_wos(entry: dict) -> dict:
    """Map a WoS BibTeX entry to the standard 8-column schema."""
    year_raw = _strip_braces(entry.get("year", ""))
    return {
        "source": "wos",
        "doi": normalize_doi(_strip_braces(entry.get("doi", ""))),
        "title": _strip_braces(entry.get("title", "")),
        "authors": _normalize_authors(_strip_braces(entry.get("author", ""))),
        "year": int(year_raw) if year_raw.isdigit() else "",
        "abstract": _strip_braces(entry.get("abstract", "")),
        "venue": _strip_braces(entry.get("journal", "") or entry.get("booktitle", "")),
        "language": _normalize_language(_strip_braces(entry.get("language", ""))),
    }
```

- [ ] **Step 5: Rodar testes, confirmar 4 passed**

```bash
pytest tests/search/test_import_bibtex.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/search/import_bibtex.py tests/search/test_import_bibtex.py tests/fixtures/wos_sample.bib
git commit -m "feat(search): add BibTeX parser and WoS field mapper"
```

---

## Task 10: `import_bibtex.py` — mappers para Scopus e SciELO + langdetect fallback

**Files:**
- Modify: `scripts/search/import_bibtex.py`
- Modify: `tests/search/test_import_bibtex.py`
- Create: `tests/fixtures/scopus_sample.bib`
- Create: `tests/fixtures/scielo_sample.bib`

- [ ] **Step 1: Criar fixture `tests/fixtures/scopus_sample.bib`**

```bibtex
@ARTICLE{García2023,
author = {García, Luis},
title = {Inteligencia artificial y mercado laboral en América Latina},
journal = {Trimestre Económico},
year = {2023},
doi = {},
abstract = {Estudio descriptivo del impacto de la IA en el empleo.},
language = {Spanish},
}
```

- [ ] **Step 2: Criar fixture `tests/fixtures/scielo_sample.bib`**

```bibtex
@article{Silva2024,
author = {Silva, R. and Costa, M.},
title = {IA generativa e o mercado de trabalho brasileiro},
journal = {Revista Brasileira de Economia},
year = {2024},
doi = {10.5678/rbe.2024.100},
abstract = {Análise dos efeitos da IA generativa sobre o emprego no Brasil.},
}
```

> Nota: a entry SciELO **não tem `language`** — força o fallback via `langdetect`.

- [ ] **Step 3: Adicionar testes em `tests/search/test_import_bibtex.py`**

```python
from scripts.search.import_bibtex import map_scopus, map_scielo, run


def test_map_scopus_preserves_spanish() -> None:
    entry = {
        "author": "García, Luis",
        "title": "Inteligencia artificial",
        "journal": "Trimestre Económico",
        "year": "2023",
        "abstract": "Estudio descriptivo.",
        "language": "Spanish",
    }
    row = map_scopus(entry)
    assert row["source"] == "scopus"
    assert row["language"] == "es"
    assert "García" in row["authors"]


def test_map_scielo_detects_language_when_missing() -> None:
    entry = {
        "author": "Silva, R. and Costa, M.",
        "title": "IA generativa e o mercado de trabalho brasileiro",
        "journal": "RBE",
        "year": "2024",
        "doi": "10.5678/rbe.2024.100",
        "abstract": "Análise dos efeitos da IA generativa sobre o emprego.",
        # No 'language' field
    }
    row = map_scielo(entry)
    assert row["source"] == "scielo"
    assert row["language"] == "pt"  # detected via langdetect


def test_run_end_to_end_with_wos_fixture(tmp_path: Path) -> None:
    out = tmp_path / "wos.csv"
    meta = tmp_path / "wos.meta.json"
    run(
        bibtex_files=[FIXTURES / "wos_sample.bib"],
        source="wos",
        output=out,
        meta_output=meta,
        query_string="test query",
    )
    df = pd.read_csv(out)
    assert len(df) == 2
    import json
    m = json.loads(meta.read_text())
    assert m["base"] == "wos"
    assert m["n_entries_raw"] == 2
    assert "csv_sha256" in m


def test_run_dedups_intra_source(tmp_path: Path) -> None:
    """Two .bib files with overlapping DOI should dedup to 2 unique."""
    f1 = tmp_path / "lote1.bib"
    f2 = tmp_path / "lote2.bib"
    f1.write_text(
        '@article{A,doi={10.1/A},title={T},author={X, Y},year={2020}}\n',
        encoding="utf-8",
    )
    f2.write_text(
        '@article{A2,doi={10.1/A},title={T},author={X, Y},year={2020}}\n'
        '@article{B,doi={10.1/B},title={U},author={Z, W},year={2021}}\n',
        encoding="utf-8",
    )
    out = tmp_path / "out.csv"
    run(
        bibtex_files=[f1, f2],
        source="wos",
        output=out,
        meta_output=tmp_path / "out.meta.json",
        query_string="q",
    )
    df = pd.read_csv(out)
    assert len(df) == 2  # the two doi=10.1/A duplicate is removed
```

- [ ] **Step 4: Rodar testes, confirmar 4 FAIL novos**

```bash
pytest tests/search/test_import_bibtex.py -v
```

Expected: 4 passed + 4 FAIL.

- [ ] **Step 5: Adicionar ao `scripts/search/import_bibtex.py`**

Adicionar ao final do arquivo:

```python
import argparse
import datetime as dt
import json
import sys

import pandas as pd
from langdetect import detect, DetectorFactory, LangDetectException

from scripts.utils.io import sha256_file, write_corpus_csv
from scripts.utils.normalization import normalize_title, dedup_key

DetectorFactory.seed = 42  # deterministic langdetect


def _detect_lang(title: str, abstract: str) -> str:
    text = f"{title} {abstract}".strip()
    if not text:
        return "en"
    try:
        code = detect(text)
    except LangDetectException:
        return "en"
    return LANG_MAP.get(code, "en")


def map_scopus(entry: dict) -> dict:
    row = map_wos(entry)
    row["source"] = "scopus"
    if not entry.get("language"):
        row["language"] = _detect_lang(row["title"], row["abstract"])
    return row


def map_scielo(entry: dict) -> dict:
    row = map_wos(entry)
    row["source"] = "scielo"
    if not entry.get("language"):
        row["language"] = _detect_lang(row["title"], row["abstract"])
    return row


_MAPPERS = {"wos": map_wos, "scopus": map_scopus, "scielo": map_scielo}


def _intra_source_dedup(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for r in rows:
        if r["doi"]:
            key = r["doi"]
        else:
            key = dedup_key(authors=r["authors"], year=r["year"], title=r["title"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def run(
    bibtex_files: list[Path],
    source: str,
    output: Path,
    meta_output: Path,
    query_string: str | None = None,
) -> None:
    if source not in _MAPPERS:
        raise ValueError(f"Unknown source: {source}. Expected one of {list(_MAPPERS)}")
    mapper = _MAPPERS[source]
    entries = parse_bib_files(bibtex_files)
    rows = [mapper(e) for e in entries]
    n_raw = len(rows)
    rows = _intra_source_dedup(rows)

    output.parent.mkdir(parents=True, exist_ok=True)
    write_corpus_csv(pd.DataFrame(rows), output)

    meta = {
        "base": source,
        "lang": None,
        "query_used": query_string or "",
        "query_string_version": "1.0",
        "date_from": "",
        "date_to": "",
        "executed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "n_files": len(bibtex_files),
        "n_entries_raw": n_raw,
        "n_after_intra_dedup": len(rows),
        "n_hits_raw": n_raw,
        "n_after_filters": len(rows),
        "csv_sha256": sha256_file(output),
        "tool_version": "ai-impact 0.2.0",
        "notes": "",
    }
    meta_output.parent.mkdir(parents=True, exist_ok=True)
    meta_output.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"BibTeX {source}: {n_raw} entries → {len(rows)} after intra-dedup → {output}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, choices=["wos", "scopus", "scielo"])
    p.add_argument("--files", type=Path, nargs="+", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--meta-output", type=Path, required=True)
    p.add_argument("--query-string", default="")
    a = p.parse_args(argv)
    run(
        bibtex_files=a.files, source=a.source,
        output=a.output, meta_output=a.meta_output,
        query_string=a.query_string,
    )
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 6: Rodar testes, confirmar 8 passed**

```bash
pytest tests/search/test_import_bibtex.py -v
```

Expected: 8 passed.

- [ ] **Step 7: Commit**

```bash
git add scripts/search/import_bibtex.py tests/search/test_import_bibtex.py tests/fixtures/scopus_sample.bib tests/fixtures/scielo_sample.bib
git commit -m "feat(search): add Scopus/SciELO mappers, langdetect fallback, intra-source dedup"
```

---

## Task 11: `snowball.py` — backward e forward citations via OpenAlex

**Files:**
- Create: `scripts/search/snowball.py`
- Create: `tests/search/test_snowball.py`

- [ ] **Step 1: Escrever testes em `tests/search/test_snowball.py`**

```python
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd

from scripts.search.snowball import backward, forward


def _mock_get(url: str, **kwargs):
    """Route mock responses based on URL pattern."""
    r = MagicMock()
    r.raise_for_status = MagicMock()
    if "/works/doi:" in url:
        r.status_code = 200
        r.json.return_value = {
            "id": "https://openalex.org/W123",
            "referenced_works": ["https://openalex.org/W500", "https://openalex.org/W501"],
        }
    elif "filter=cites" in url:
        r.status_code = 200
        r.json.return_value = {
            "results": [
                {"doi": "10.5/citing1", "title": "Citing paper 1",
                 "publication_year": 2024, "authorships": [],
                 "primary_location": None, "abstract_inverted_index": None,
                 "language": "en"}
            ],
            "meta": {"next_cursor": None, "count": 1},
        }
    elif "openalex.org/works/W" in url or "/works/W" in url:
        r.status_code = 200
        r.json.return_value = {
            "doi": "10.4/ref1", "title": "Referenced", "publication_year": 2018,
            "authorships": [], "primary_location": None,
            "abstract_inverted_index": None, "language": "en",
        }
    else:
        r.status_code = 404
    return r


def test_backward_extracts_referenced_works(tmp_path: Path) -> None:
    out = tmp_path / "back.csv"
    with patch("scripts.search.snowball.requests.get", side_effect=_mock_get):
        backward(seed_dois=["10.1/seed"], email="x@y.com", output=out)
    df = pd.read_csv(out)
    assert df["source"].iloc[0] == "snowball-backward"
    assert len(df) >= 1


def test_forward_extracts_citing_works(tmp_path: Path) -> None:
    out = tmp_path / "fwd.csv"
    with patch("scripts.search.snowball.requests.get", side_effect=_mock_get):
        forward(seed_dois=["10.1/seed"], email="x@y.com", output=out)
    df = pd.read_csv(out)
    assert df["source"].iloc[0] == "snowball-forward"
    assert len(df) >= 1
```

- [ ] **Step 2: Rodar testes, confirmar FAIL**

```bash
pytest tests/search/test_snowball.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar `scripts/search/snowball.py`**

```python
"""Pipeline component: forward and backward citation tracking via OpenAlex.

To be executed AFTER the initial screening produces a list of central seed DOIs
(Plano 3+). Outputs CSVs in the standard schema with source values
'snowball-backward' or 'snowball-forward'.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from scripts.search.openalex_search import flatten_record
from scripts.utils.io import write_corpus_csv


OPENALEX_BASE = "https://api.openalex.org/works"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _get(url: str, email: str, params: dict | None = None) -> dict:
    headers = {"User-Agent": f"ai-impact/0.2.0 (mailto:{email})"}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _fetch_work_by_id(openalex_id: str, email: str) -> dict | None:
    short = openalex_id.rsplit("/", 1)[-1]  # strip URL prefix
    url = f"{OPENALEX_BASE}/{short}"
    try:
        return _get(url, email=email)
    except requests.HTTPError:
        return None


def backward(
    seed_dois: list[str],
    email: str,
    output: Path,
    year_from: int = 2013,
    year_to: int = 2025,
) -> None:
    """Fetch backward references for each seed DOI; flatten and write CSV."""
    rows: list[dict] = []
    for doi in seed_dois:
        seed = _get(f"{OPENALEX_BASE}/doi:{doi}", email=email)
        for ref_id in seed.get("referenced_works", []):
            ref = _fetch_work_by_id(ref_id, email=email)
            if not ref:
                continue
            year = ref.get("publication_year") or 0
            if year_from <= year <= year_to:
                row = flatten_record(ref, default_lang="en")
                row["source"] = "snowball-backward"
                rows.append(row)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_corpus_csv(pd.DataFrame(rows), output)
    print(f"Snowball backward: {len(rows)} refs from {len(seed_dois)} seeds → {output}")


def forward(
    seed_dois: list[str],
    email: str,
    output: Path,
    year_from: int = 2013,
    year_to: int = 2025,
) -> None:
    """Fetch forward citations for each seed DOI; flatten and write CSV."""
    rows: list[dict] = []
    for doi in seed_dois:
        seed = _get(f"{OPENALEX_BASE}/doi:{doi}", email=email)
        seed_id = seed.get("id", "").rsplit("/", 1)[-1]
        if not seed_id:
            continue
        cursor = "*"
        while cursor is not None:
            params = {
                "filter": f"cites:{seed_id},from_publication_date:{year_from}-01-01,to_publication_date:{year_to}-12-31",
                "per_page": 200,
                "cursor": cursor,
            }
            data = _get(OPENALEX_BASE, email=email, params=params)
            for rec in data.get("results", []):
                row = flatten_record(rec, default_lang="en")
                row["source"] = "snowball-forward"
                rows.append(row)
            cursor = data.get("meta", {}).get("next_cursor")
    output.parent.mkdir(parents=True, exist_ok=True)
    write_corpus_csv(pd.DataFrame(rows), output)
    print(f"Snowball forward: {len(rows)} citing works from {len(seed_dois)} seeds → {output}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("direction", choices=["backward", "forward"])
    p.add_argument("--seeds", type=Path, required=True,
                   help="Text file with one DOI per line")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--year-from", type=int, default=2013)
    p.add_argument("--year-to", type=int, default=2025)
    a = p.parse_args(argv)
    dois = [line.strip() for line in a.seeds.read_text().splitlines() if line.strip()]
    fn = backward if a.direction == "backward" else forward
    fn(seed_dois=dois, email=a.email, output=a.output,
       year_from=a.year_from, year_to=a.year_to)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Rodar testes, confirmar 2 passed**

```bash
pytest tests/search/test_snowball.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/search/snowball.py tests/search/test_snowball.py
git commit -m "feat(search): add backward/forward snowballing via OpenAlex"
```

---

## Task 12: `summary.py` — relatório LaTeX a partir dos `.meta.json`

**Files:**
- Create: `scripts/search/summary.py`
- Create: `tests/search/test_summary.py`

- [ ] **Step 1: Escrever testes em `tests/search/test_summary.py`**

```python
import json
from pathlib import Path

from scripts.search.summary import run


def _meta(base: str, lang: str | None, n_raw: int, n_filt: int) -> dict:
    return {
        "base": base, "lang": lang,
        "executed_at_utc": "2026-05-15T10:00:00+00:00",
        "n_hits_raw": n_raw, "n_after_filters": n_filt,
        "csv_sha256": "x" * 64,
    }


def test_summary_aggregates_all_meta_json(tmp_path: Path) -> None:
    sdir = tmp_path / "searches"
    sdir.mkdir()
    (sdir / "openalex_en_2026-05-15.meta.json").write_text(
        json.dumps(_meta("openalex", "en", 2453, 2104))
    )
    (sdir / "openalex_pt_2026-05-15.meta.json").write_text(
        json.dumps(_meta("openalex", "pt", 184, 162))
    )
    (sdir / "wos_2026-05-15.meta.json").write_text(
        json.dumps(_meta("wos", None, 1820, 1820))
    )
    out = tmp_path / "summary.tex"
    run(searches_dir=sdir, output_table=out)
    text = out.read_text()
    assert "\\begin{tabular}" in text
    assert "2453" in text
    assert "openalex" in text
    assert "wos" in text
    # Total row
    assert "4457" in text or "4,457" in text or "Total" in text
```

- [ ] **Step 2: Rodar teste, confirmar FAIL**

```bash
pytest tests/search/test_summary.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar `scripts/search/summary.py`**

```python
"""Pipeline component: build summary table of all search executions.

Reads every `*.meta.json` in `data/raw/searches/` and produces a LaTeX table
for the methodology chapter (`text/tables/searches_summary.tex`).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def run(searches_dir: Path, output_table: Path) -> None:
    meta_files = sorted(searches_dir.glob("*.meta.json"))
    records: list[dict] = []
    for mf in meta_files:
        data = json.loads(mf.read_text(encoding="utf-8"))
        records.append({
            "Base": data.get("base", ""),
            "Data": data.get("executed_at_utc", "")[:10],
            "Idioma": data.get("lang") or "—",
            "n_brutos": int(data.get("n_hits_raw", 0)),
            "n_filtrados": int(data.get("n_after_filters", 0)),
        })
    df = pd.DataFrame(records)
    if df.empty:
        output_table.parent.mkdir(parents=True, exist_ok=True)
        output_table.write_text(
            r"\begin{tabular}{l}\toprule Nenhuma execução registrada \\ \bottomrule \end{tabular}",
            encoding="utf-8",
        )
        return

    total_raw = int(df["n_brutos"].sum())
    total_filt = int(df["n_filtrados"].sum())

    lines = [
        r"\begin{tabular}{lllrr}",
        r"\toprule",
        r"Base & Data & Idioma & n\_brutos & n\_filtrados \\",
        r"\midrule",
    ]
    for _, row in df.iterrows():
        lines.append(
            f"{row['Base']} & {row['Data']} & {row['Idioma']} & "
            f"{int(row['n_brutos'])} & {int(row['n_filtrados'])} \\\\"
        )
    lines.append(r"\midrule")
    lines.append(
        rf"\textbf{{Total}} & & & \textbf{{{total_raw}}} & \textbf{{{total_filt}}} \\"
    )
    lines.extend([r"\bottomrule", r"\end{tabular}"])

    output_table.parent.mkdir(parents=True, exist_ok=True)
    output_table.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Summary table written to {output_table} ({len(records)} executions)")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--searches-dir", type=Path, required=True)
    p.add_argument("--output-table", type=Path, required=True)
    a = p.parse_args(argv)
    run(searches_dir=a.searches_dir, output_table=a.output_table)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Rodar teste**

```bash
pytest tests/search/test_summary.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/search/summary.py tests/search/test_summary.py
git commit -m "feat(search): add searches summary LaTeX table generator"
```

---

## Task 13: Atualizar Makefile com targets de busca

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Adicionar bloco de targets de busca ao Makefile**

Edite `Makefile` substituindo o target existente `search` (linhas 24-26 do arquivo atual) pelos targets abaixo. Identifique o bloco atual:

```makefile
.PHONY: search
search:
	@echo "F3 — buscas: implementadas no Plano 2. Por enquanto, popular manualmente $(DATA_RAW)/"
```

E substitua por:

```makefile
TODAY := $(shell date +%Y-%m-%d)
EMAIL ?= acacio@example.com

# ============ Plano 2 — Busca ============

.PHONY: search-openalex
search-openalex:
	@for LANG in en pt es fr; do \
	    echo "→ OpenAlex $$LANG"; \
	    $(PYTHON) -m scripts.search.openalex_search \
	        --query-file protocols/search_strings/$$LANG.txt \
	        --lang $$LANG \
	        --output $(DATA_RAW)/openalex_$${LANG}_$(TODAY).csv \
	        --meta-output $(DATA_RAW)/openalex_$${LANG}_$(TODAY).meta.json \
	        --email $(EMAIL); \
	done

.PHONY: import-wos
import-wos:
	$(PYTHON) -m scripts.search.import_bibtex \
	    --source wos \
	    --files $(DATA_RAW)/manual/wos/*.bib \
	    --output $(DATA_RAW)/wos_$(TODAY).csv \
	    --meta-output $(DATA_RAW)/wos_$(TODAY).meta.json \
	    --query-string "$$(cat protocols/search_strings/en.txt)"

.PHONY: import-scopus
import-scopus:
	$(PYTHON) -m scripts.search.import_bibtex \
	    --source scopus \
	    --files $(DATA_RAW)/manual/scopus/*.bib \
	    --output $(DATA_RAW)/scopus_$(TODAY).csv \
	    --meta-output $(DATA_RAW)/scopus_$(TODAY).meta.json \
	    --query-string "$$(cat protocols/search_strings/en.txt)"

.PHONY: import-scielo
import-scielo:
	$(PYTHON) -m scripts.search.import_bibtex \
	    --source scielo \
	    --files $(DATA_RAW)/manual/scielo/*.bib \
	    --output $(DATA_RAW)/scielo_$(TODAY).csv \
	    --meta-output $(DATA_RAW)/scielo_$(TODAY).meta.json \
	    --query-string "$$(cat protocols/search_strings/pt.txt)"

.PHONY: search-summary
search-summary:
	$(PYTHON) -m scripts.search.summary \
	    --searches-dir $(DATA_RAW) \
	    --output-table $(TAB_DIR)/searches_summary.tex

.PHONY: search-all
search-all: search-openalex import-wos import-scopus import-scielo search-summary
	@echo "✓ Busca completa. Próximo: make consolidate && make dedup"
```

> Nota: `EMAIL` deve ser overridable na linha de comando: `make search-openalex EMAIL=acacio@nexxasolucoes.com.br`.

- [ ] **Step 2: Verificar sintaxe do Makefile**

```bash
make -n search-openalex
```

Expected: imprime o comando expandido sem erro de sintaxe.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "feat: add Plan 2 search targets to Makefile (openalex, import-*, summary)"
```

---

## Task 14: Suite de testes completa do Plano 2

**Files:**
- Nenhum (verificação)

- [ ] **Step 1: Rodar toda a suite**

```bash
source /home/acacio/dev/pessoal/ai-impact/.venv/bin/activate
pytest -q
```

Expected: 35 testes do Plano 1 + ~16 testes novos do Plano 2 = **≥ 51 testes**, todos passando.

- [ ] **Step 2: Se algum teste falhar**

Anotar qual e investigar. Não prosseguir para a Task 15 (execução real) até todos passarem.

> Se for um teste do Plano 1 que regrediu por causa de mudanças neste plano (deveria ser raro — não tocamos no Plano 1), reverter a mudança que causou e ajustar.

---

## Task 15: Executar OpenAlex em todos os idiomas

**Files:**
- Nenhum (execução). Output em `data/raw/searches/openalex_*.csv` (não versionado).

> Esta tarefa **chama API externa**. Requer rede. Pode demorar **30-60 minutos** dependendo do volume.

- [ ] **Step 1: Definir email para polite pool**

Decidir o email a usar (recomendado: `acacio@nexxasolucoes.com.br` ou um pessoal). Exportar como variável:

```bash
export EMAIL=acacio@nexxasolucoes.com.br
```

- [ ] **Step 2: Rodar OpenAlex em todos os idiomas**

```bash
source /home/acacio/dev/pessoal/ai-impact/.venv/bin/activate
make search-openalex EMAIL=$EMAIL
```

Expected: 4 pares CSV+meta.json criados em `data/raw/searches/`:
- `openalex_en_YYYY-MM-DD.csv` + `.meta.json`
- `openalex_pt_YYYY-MM-DD.csv` + `.meta.json`
- `openalex_es_YYYY-MM-DD.csv` + `.meta.json`
- `openalex_fr_YYYY-MM-DD.csv` + `.meta.json`

- [ ] **Step 3: Verificar contagens**

```bash
for f in data/raw/searches/openalex_*.meta.json; do
  python -c "import json; d=json.load(open('$f')); print(d['lang'], d['n_hits_raw'], d['n_after_filters'])"
done
```

Expected: 4 linhas, total `n_after_filters` entre 500-5000 (mais en, menos fr/es/pt).

- [ ] **Step 4: Spot-check qualitativo**

```bash
python -c "
import pandas as pd
df = pd.read_csv('data/raw/searches/openalex_en_$(date +%Y-%m-%d).csv')
print('Total:', len(df))
print('Sample titles:')
print(df.sample(min(10, len(df)))['title'].to_list())
"
```

Verificar que os títulos parecem relacionados a IA + trabalho. Se a maioria for ruído (e.g., medicina, química), revisar a query e refazer.

- [ ] **Step 5: Marcar conclusão**

Esta task não tem commit — os outputs são não-versionados. Avançar para Task 16.

---

## Task 16: Exportar manualmente do WoS e importar

**Files:**
- Created (manual, não versionado): `data/raw/searches/manual/wos/*.bib`
- Output (não versionado): `data/raw/searches/wos_YYYY-MM-DD.csv` + `.meta.json`

> Esta task **requer ação humana** no navegador. Estimativa: 30 min - 2h, dependendo do volume.

- [ ] **Step 1: Acessar Web of Science**

Login via acesso institucional. Acessar Web of Science Core Collection.

- [ ] **Step 2: Construir a query no WoS Advanced Search**

Colar o conteúdo de `protocols/search_strings/en.txt` adaptado para sintaxe WoS (`TS=` em vez do bloco). Exemplo:

```
TS=("artificial intelligence" OR "machine learning" OR "deep learning" OR "neural network*" OR "natural language processing" OR "NLP" OR "large language model*" OR "LLM" OR "generative AI" OR "ChatGPT" OR "GPT" OR "foundation model*" OR "automation") AND TS=("employment" OR "labor market*" OR "labour market*" OR "jobs" OR "workforce" OR "occupation*" OR "wages" OR "labor demand" OR "task displacement" OR "job creation" OR "job destruction") AND TS=("impact*" OR "effect*" OR "exposure" OR "displacement" OR "automation risk" OR "substitution" OR "complementarity")
```

Restringir Document Types: `Article`, `Review`, `Proceedings Paper`. Período: `2013-2025`.

- [ ] **Step 3: Exportar em BibTeX em lotes de 500**

Marcar todos os resultados. Selecionar `Export` → `BibTeX`. Baixar lote 1-500, depois 501-1000, etc. Renomear cada arquivo (e.g., `wos_lote1.bib`, `wos_lote2.bib`).

Mover para `data/raw/searches/manual/wos/`.

- [ ] **Step 4: Importar via Makefile**

```bash
source /home/acacio/dev/pessoal/ai-impact/.venv/bin/activate
make import-wos
```

Expected: `data/raw/searches/wos_YYYY-MM-DD.csv` + `.meta.json` criados.

- [ ] **Step 5: Verificar contagem e qualidade**

```bash
python -c "
import json, pandas as pd
m = json.load(open('data/raw/searches/wos_$(date +%Y-%m-%d).meta.json'))
df = pd.read_csv('data/raw/searches/wos_$(date +%Y-%m-%d).csv')
print('n_entries_raw:', m['n_entries_raw'])
print('n_after_intra_dedup:', m['n_after_intra_dedup'])
print('Sample:'); print(df.sample(min(5, len(df)))[['title','year']])
"
```

Expected: contagem coerente com o que o WoS reportou; sample faz sentido.

---

## Task 17: Exportar manualmente do Scopus e importar

**Files:**
- Manual: `data/raw/searches/manual/scopus/*.bib`
- Output: `data/raw/searches/scopus_YYYY-MM-DD.csv` + `.meta.json`

> Análogo à Task 16. ~30 min - 2h.

- [ ] **Step 1: Acessar Scopus**

Login institucional. Acessar busca avançada.

- [ ] **Step 2: Construir a query**

Sintaxe Scopus para a string EN:

```
TITLE-ABS-KEY(("artificial intelligence" OR "machine learning" OR "deep learning" OR "neural network*" OR "natural language processing" OR "NLP" OR "large language model*" OR "LLM" OR "generative AI" OR "ChatGPT" OR "GPT" OR "foundation model*" OR "automation") AND ("employment" OR "labor market*" OR "labour market*" OR "jobs" OR "workforce" OR "occupation*" OR "wages" OR "labor demand" OR "task displacement" OR "job creation" OR "job destruction") AND ("impact*" OR "effect*" OR "exposure" OR "displacement" OR "automation risk" OR "substitution" OR "complementarity")) AND PUBYEAR > 2012 AND PUBYEAR < 2026 AND ( LIMIT-TO ( DOCTYPE,"ar" ) OR LIMIT-TO ( DOCTYPE,"cp" ) OR LIMIT-TO ( DOCTYPE,"re" ) )
```

- [ ] **Step 3: Exportar em BibTeX em lotes**

Scopus permite exportar até 2000 por lote. Selecionar tudo, `Export` → `BibTeX`. Mover para `data/raw/searches/manual/scopus/`.

- [ ] **Step 4: Importar**

```bash
make import-scopus
```

- [ ] **Step 5: Verificar**

```bash
python -c "
import json, pandas as pd
m = json.load(open('data/raw/searches/scopus_$(date +%Y-%m-%d).meta.json'))
df = pd.read_csv('data/raw/searches/scopus_$(date +%Y-%m-%d).csv')
print('n_entries_raw:', m['n_entries_raw'], '| n_after_intra_dedup:', m['n_after_intra_dedup'])
print(df.sample(min(5, len(df)))[['title','year','language']])
"
```

---

## Task 18: Exportar manualmente do SciELO e importar

**Files:**
- Manual: `data/raw/searches/manual/scielo/*.bib`
- Output: `data/raw/searches/scielo_YYYY-MM-DD.csv` + `.meta.json`

> ~30 min. Volume tipicamente menor (50-300 registros).

- [ ] **Step 1: Acessar SciELO**

`https://search.scielo.org/`.

- [ ] **Step 2: Buscar em pt/es**

Usar a query do `protocols/search_strings/pt.txt` (e/ou `es.txt`) adaptada à interface da SciELO. Restringir `ano: 2013-2025`.

- [ ] **Step 3: Exportar em BibTeX**

Marcar todos, `Citações exportadas` → `BibTeX`. Salvar como `data/raw/searches/manual/scielo/scielo_export.bib`.

- [ ] **Step 4: Importar**

```bash
make import-scielo
```

- [ ] **Step 5: Verificar**

```bash
python -c "
import json, pandas as pd
m = json.load(open('data/raw/searches/scielo_$(date +%Y-%m-%d).meta.json'))
df = pd.read_csv('data/raw/searches/scielo_$(date +%Y-%m-%d).csv')
print('n_entries_raw:', m['n_entries_raw'])
print('language distribution:'); print(df['language'].value_counts())
"
```

Expected: maioria `pt` e `es`.

---

## Task 19: Gerar summary table e validar volume total

**Files:**
- Created (versionado): `text/tables/searches_summary.tex`

- [ ] **Step 1: Rodar summary**

```bash
source /home/acacio/dev/pessoal/ai-impact/.venv/bin/activate
make search-summary
```

Expected: `text/tables/searches_summary.tex` criado.

- [ ] **Step 2: Inspecionar a tabela**

```bash
cat text/tables/searches_summary.tex
```

Expected: tabela LaTeX bem formada listando todas as execuções, com linha de total.

- [ ] **Step 3: Validar volume total**

```bash
python -c "
import json, glob
total_raw = total_filt = 0
for f in glob.glob('data/raw/searches/*.meta.json'):
    d = json.load(open(f))
    total_raw += d.get('n_hits_raw', 0)
    total_filt += d.get('n_after_filters', 0)
print(f'Total raw: {total_raw}'); print(f'Total filtered: {total_filt}')
"
```

Expected: `total_filt` entre 1500 e 10000. Se fora desse intervalo, considerar:
- < 1500 → query muito restritiva, revisar termos
- > 10000 → query muito ampla, adicionar filtros (e.g., periódicos de economia)

Para revisar:
- Não comitar o summary ainda
- Iterar nas queries / refazer busca de uma ou mais bases
- Voltar para Task 15-18 do componente afetado

- [ ] **Step 4: Commit summary table**

> A tabela é versionada porque entra no PDF do TCC.

```bash
git add text/tables/searches_summary.tex
git commit -m "feat(text): generate searches summary table from .meta.json logs"
```

---

## Task 20: Consolidar e deduplicar o corpus completo

**Files:**
- Output (não versionado): `data/processed/01_corpus_bruto.csv`, `02_corpus_dedup.csv`, `02_dedup_decisions.csv`

- [ ] **Step 1: Consolidar**

```bash
source /home/acacio/dev/pessoal/ai-impact/.venv/bin/activate
make consolidate
```

Expected: `data/processed/01_corpus_bruto.csv` contendo todas as linhas das 7 CSVs (4 openalex + wos + scopus + scielo).

- [ ] **Step 2: Verificar contagem**

```bash
python -c "
import pandas as pd
df = pd.read_csv('data/processed/01_corpus_bruto.csv')
print('Total bruto:', len(df))
print('Por source:'); print(df['source'].value_counts())
"
```

- [ ] **Step 3: Deduplicar**

Usar `--no-embeddings` na primeira passagem (mais rápido). Embeddings depois se necessário.

```bash
python -m scripts.screening.dedup \
    --input data/processed/01_corpus_bruto.csv \
    --output data/processed/02_corpus_dedup.csv \
    --log data/processed/02_dedup_decisions.csv \
    --no-embeddings
```

Expected: redução de ≥10% (papers indexados em múltiplas bases).

- [ ] **Step 4: Verificar dedup**

```bash
python -c "
import pandas as pd
bruto = pd.read_csv('data/processed/01_corpus_bruto.csv')
dedup = pd.read_csv('data/processed/02_corpus_dedup.csv')
log = pd.read_csv('data/processed/02_dedup_decisions.csv')
print(f'Bruto: {len(bruto)}'); print(f'Dedup: {len(dedup)}')
print(f'Removidos: {len(log)} ({len(log)/len(bruto)*100:.1f}%)')
print('Por regra:'); print(log['rule'].value_counts())
"
```

Expected:
- Total bruto ≈ soma dos meta.json (≈ total_filt da Task 19)
- Dedup: ≥10% removidos
- Por regra: maioria `doi` (papers em múltiplas bases têm DOI), alguns `dedup_key`

- [ ] **Step 5: Nenhum commit aqui**

Os outputs (`data/processed/*.csv`) são ignorados pelo git. Se quiser preservar um snapshot, pode forçar o commit do `02_corpus_dedup.csv` (já que esse passa a ser o "corpus oficial"). Por padrão, não.

---

## Task 21: Sanity check final e tag

**Files:**
- Nenhum (verificação + tag)

- [ ] **Step 1: Rodar suite completa de testes**

```bash
source /home/acacio/dev/pessoal/ai-impact/.venv/bin/activate
pytest -q
```

Expected: todos os testes passam (≥ 51).

- [ ] **Step 2: Verificar working tree limpo**

```bash
git status
```

Expected: clean.

- [ ] **Step 3: Checklist de critérios de sucesso (spec § 9)**

Confirmar visualmente cada item:

```bash
# 1. OpenAlex em 4 idiomas
ls data/raw/searches/openalex_*.csv | wc -l  # esperado: 4
ls data/raw/searches/openalex_*.meta.json | wc -l  # esperado: 4

# 2. WoS, Scopus, SciELO
ls data/raw/searches/{wos,scopus,scielo}_*.csv 2>/dev/null | wc -l  # esperado: 3

# 3. Consolidate funcionou
test -f data/processed/01_corpus_bruto.csv && echo "✓ consolidate"

# 4. Dedup funcionou
test -f data/processed/02_corpus_dedup.csv && echo "✓ dedup"

# 5. Volume
python -c "
import pandas as pd
d = pd.read_csv('data/processed/02_corpus_dedup.csv')
b = pd.read_csv('data/processed/01_corpus_bruto.csv')
n = len(d); raw = len(b)
ok = 1500 <= raw <= 10000 and (raw - n) / raw >= 0.10
print(f'Corpus bruto: {raw}, dedup: {n}, removidos: {(raw-n)/raw*100:.1f}%')
print('✓ volume' if ok else '✗ VOLUME FORA DO ESPERADO')
"

# 6. Summary table
test -f text/tables/searches_summary.tex && echo "✓ summary"

# 7. Testes
pytest -q | tail -1
```

- [ ] **Step 4: Criar tag**

```bash
git tag -a v0.2.0-busca -m "Plano 2 completo: execução da busca em todas as bases"
git log --oneline | head -25
git tag -l
```

---

## Resumo dos artefatos entregues pelo Plano 2

**Código novo (testado):**
- `scripts/search/openalex_utils.py` (reconstruct_abstract, parse_query_blocks)
- `scripts/search/openalex_search.py` (flatten_record, fetch_all, filter_by_keywords, run, CLI)
- `scripts/search/import_bibtex.py` (parse_bib_files, map_wos, map_scopus, map_scielo, run, CLI)
- `scripts/search/snowball.py` (backward, forward, CLI)
- `scripts/search/summary.py` (run, CLI)

**Outputs operacionais:**
- 7+ pares `data/raw/searches/{base}_{lang}_{date}.csv` + `.meta.json` (não versionados)
- `data/processed/01_corpus_bruto.csv` (consolidado)
- `data/processed/02_corpus_dedup.csv` (deduplicado, ~80-150 papers após dedup intra-base do Plano 1)
- `text/tables/searches_summary.tex` (versionado, entra no capítulo de metodologia)

**Marco:** tag `v0.2.0-busca`. Próximo: Plano 3 (screening por LLM, calibração, e seleção final do corpus).

## O que NÃO está neste plano

- **Execução do snowballing** — código entregue, mas só roda depois que o screening identificar os seeds (Plano 3+).
- **Busca em periódicos individuais** (AER, JoLE, etc.) — só se OpenAlex não cobrir, decidir após inspeção qualitativa na Task 15 Step 4.
- **Calibração do LLM-as-judge** — Plano 3.
- **Atualização do capítulo de metodologia em LaTeX** com o texto narrativo da estratégia de busca — fica para o Plano 6 (redação) que escreve narrativa a partir dos artefatos.
