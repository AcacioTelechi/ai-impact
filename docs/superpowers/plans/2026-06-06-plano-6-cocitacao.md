# Plano 6 — Análise bibliométrica (acoplamento + co-citação) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir, de forma exploratória e isolada do build do TCC, duas redes bibliométricas — acoplamento bibliográfico (clusteriza os artigos do corpus) e co-citação (clusteriza a base intelectual citada) — a partir de referências obtidas em híbrido (WoS local + OpenAlex), clusterizá-las com Louvain e caracterizar os clusters.

**Architecture:** Novo pacote `scripts/biblio/` espelhando `scripts/analysis/` (funções puras testáveis + fronteira de I/O de rede isolada/injetável). Pipeline em 4 etapas: aquisição de referências → `08_paper_refs.csv`; construção das redes (networkx) → GraphML; clusterização Louvain + caracterização; renderização das saídas em `reports/biblio/`. Driver próprio `make biblio`, sem tocar `make analysis` nem `text/`.

**Tech Stack:** Python 3.12, `networkx` (Louvain nativo), `scikit-learn` (TF-IDF), `requests` (OpenAlex, polite pool via `mailto`), `pandas`, `matplotlib`. Todas já em `pyproject.toml` — nenhuma dependência nova. `uv run` para executar; `pytest` para testes.

**Convenções do repo (seguir):** cada módulo tem docstring, `from __future__ import annotations`, funções puras no topo, um `run(...)` orquestrador e `_cli(argv)` com `argparse` + `if __name__ == "__main__": sys.exit(_cli(sys.argv[1:]))`. Testes em `tests/biblio/test_*.py`, rodados com `uv run pytest`. Identidade de referência = **DOI normalizado**; refs sem DOI são descartadas do matching e contadas.

---

## File Structure

- `scripts/biblio/__init__.py` — pacote vazio (marca módulo).
- `scripts/biblio/dois.py` — normalização/extração de DOI (puro). **Task 1**
- `scripts/biblio/wos_refs.py` — parser do `.bib` da WoS → `{paper_doi: [ref_doi]}` (puro). **Task 2**
- `scripts/biblio/openalex.py` — cliente OpenAlex (HTTP injetável) + cache em disco. **Task 3**
- `scripts/biblio/refs_acquire.py` — orquestra híbrido WoS+OpenAlex → `08_paper_refs.csv`. **Task 4**
- `scripts/biblio/networks.py` — `build_coupling` + `build_cocitation` → GraphML (puro). **Task 5**
- `scripts/biblio/cluster.py` — Louvain + caracterização (tamanhos, top termos, crosstabs). **Task 6**
- `scripts/biblio/report.py` — figuras + `RESUMO.md`/CSVs + orquestrador `run`. **Task 7**
- `Makefile` — alvo `make biblio`. **Task 8**
- Testes: `tests/biblio/{__init__.py,test_dois.py,test_wos_refs.py,test_openalex.py,test_refs_acquire.py,test_networks.py,test_cluster.py}`

Artefatos gerados (gitignored como os demais build outputs): `data/processed/08_paper_refs.csv`, `data/processed/08_refs_cache.json`, `data/processed/08_openalex_idmap.json`, `reports/biblio/*`.

---

## Task 0: Scaffolding do pacote

**Files:**
- Create: `scripts/biblio/__init__.py`
- Create: `tests/biblio/__init__.py`

- [ ] **Step 1: Criar os arquivos de pacote vazios**

```bash
mkdir -p scripts/biblio tests/biblio reports/biblio
touch scripts/biblio/__init__.py tests/biblio/__init__.py
```

- [ ] **Step 2: Commit**

```bash
git add scripts/biblio/__init__.py tests/biblio/__init__.py
git commit -m "chore(plano-6): scaffold do pacote scripts/biblio"
```

---

## Task 1: Normalização de DOI (`dois.py`)

**Files:**
- Create: `scripts/biblio/dois.py`
- Test: `tests/biblio/test_dois.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/biblio/test_dois.py
from scripts.biblio.dois import norm_doi


def test_bare_doi_lowercased():
    assert norm_doi("10.1257/AER.20160696") == "10.1257/aer.20160696"


def test_strips_url_prefix():
    assert norm_doi("https://doi.org/10.3982/ECTA19815") == "10.3982/ecta19815"


def test_extracts_doi_from_wos_ref_string():
    ref = "Acemoglu D, 2022, ECONOMETRICA, V90, P1973, DOI 10.3982/ECTA19815."
    assert norm_doi(ref) == "10.3982/ecta19815"


def test_strips_trailing_punctuation():
    assert norm_doi("10.1016/j.frl.2025.109145.") == "10.1016/j.frl.2025.109145"


def test_no_doi_returns_empty():
    assert norm_doi("Acemoglu D, 2019, J ECON PERSPECT, V33, P3") == ""
    assert norm_doi("") == ""
    assert norm_doi("nan") == ""
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `uv run pytest tests/biblio/test_dois.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.biblio.dois'`

- [ ] **Step 3: Implementar o mínimo**

```python
# scripts/biblio/dois.py
"""Normalização e extração de DOI (Plano 6).

Identidade canônica de referência em toda a linha bibliométrica. Um DOI é
reduzido à forma "bare" minúscula (sem prefixo de URL, sem 'doi:'/'DOI ',
sem pontuação final). Strings sem DOI retornam "".
"""
from __future__ import annotations

import re

# DOI: 10.<registrant>/<suffix>; o sufixo vai até espaço/fim (refs WoS têm vírgulas
# antes do 'DOI ', então o token de DOI em si não contém espaço).
_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s]+")
_TRAILING = ".,;:)]}'\"<>"


def norm_doi(raw: str) -> str:
    if not raw:
        return ""
    s = str(raw).strip().lower()
    for pref in ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:", "doi "):
        if s.startswith(pref):
            s = s[len(pref):]
    m = _DOI_RE.search(s)
    if not m:
        return ""
    return m.group(0).rstrip(_TRAILING)
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `uv run pytest tests/biblio/test_dois.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/biblio/dois.py tests/biblio/test_dois.py
git commit -m "feat(plano-6): norm_doi — normalização/extração canônica de DOI"
```

---

## Task 2: Parser de referências da WoS (`wos_refs.py`)

**Files:**
- Create: `scripts/biblio/wos_refs.py`
- Test: `tests/biblio/test_wos_refs.py`

**Contrato:** `parse_wos_bib(paths) -> dict[str, list[str]]` mapeia `paper_doi`
normalizado → lista de DOIs de referências (normalizados, sem vazios, sem
duplicatas, preservando ordem). Registros sem DOI de paper são ignorados.
`_extract_field(entry, name) -> str` faz varredura de chaves balanceadas (o
campo `Cited-References` tem múltiplas linhas e vírgulas internas).

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/biblio/test_wos_refs.py
from scripts.biblio.wos_refs import parse_wos_bib, _extract_field

ENTRY = """@article{ WOS:000123,
Author = {Silva, J},
Title = {A paper},
DOI = {10.1111/AAA.111},
Cited-References = {Acemoglu D, 2022, ECONOMETRICA, V90, P1973, DOI 10.3982/ECTA19815.
   Autor X, 2019, J SEM DOI, V1, P1.
   Author B, 2018, AM ECON REV, V108, P1488, DOI 10.1257/AER.20160696.},
Number-of-Cited-References = {3},
Year = {2024},
}"""


def test_extract_field_balanced():
    cr = _extract_field(ENTRY, "cited-references")
    assert "ECTA19815" in cr and "AER.20160696" in cr
    # não vaza para o campo seguinte
    assert "Number-of-Cited-References" not in cr


def test_parse_maps_paper_doi_to_ref_dois(tmp_path):
    p = tmp_path / "wos.bib"
    p.write_text(ENTRY, encoding="utf-8")
    out = parse_wos_bib([p])
    assert "10.1111/aaa.111" in out
    refs = out["10.1111/aaa.111"]
    # refs sem DOI descartadas → ficam 2
    assert refs == ["10.3982/ecta19815", "10.1257/aer.20160696"]


def test_entry_without_doi_skipped(tmp_path):
    p = tmp_path / "wos.bib"
    p.write_text("@article{X,\nTitle = {No DOI},\nYear = {2020},\n}", encoding="utf-8")
    assert parse_wos_bib([p]) == {}
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `uv run pytest tests/biblio/test_wos_refs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.biblio.wos_refs'`

- [ ] **Step 3: Implementar o mínimo**

```python
# scripts/biblio/wos_refs.py
"""Parser do campo Cited-References dos exports .bib da Web of Science (Plano 6).

O export WoS traz, por registro, `DOI = {...}` e `Cited-References = {ref. ref.
ref.}` — refs separadas por `.\\n`, cada uma no formato
`Autor AA, ANO, PERIODICO, Vvol, Ppag, DOI 10...`. Extraímos o DOI de cada ref
(quando houver) e descartamos as demais. Identidade via DOI normalizado.
"""
from __future__ import annotations

import re
from pathlib import Path

from scripts.biblio.dois import norm_doi


def _extract_field(entry: str, name: str) -> str:
    """Valor de `name = { ... }` com varredura de chaves balanceadas
    (case-insensitive). "" se ausente."""
    m = re.search(rf"(?i)\b{re.escape(name)}\s*=\s*\{{", entry)
    if not m:
        return ""
    i = m.end()
    depth = 1
    buf: list[str] = []
    while i < len(entry) and depth > 0:
        c = entry[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        buf.append(c)
        i += 1
    return "".join(buf)


def _split_refs(cited: str) -> list[str]:
    # refs separadas por ponto-final seguido de quebra de linha
    return [r.strip() for r in re.split(r"\.\s*\n", cited) if r.strip()]


def parse_wos_bib(paths) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for path in paths:
        txt = Path(path).read_text(encoding="utf-8", errors="replace")
        # entradas começam em '@'; split preservando blocos
        for chunk in re.split(r"\n@", txt):
            entry = chunk if chunk.lstrip().startswith("@") else "@" + chunk
            paper_doi = norm_doi(_extract_field(entry, "doi"))
            if not paper_doi:
                continue
            cited = _extract_field(entry, "cited-references")
            seen: set[str] = set()
            refs: list[str] = []
            for r in _split_refs(cited):
                d = norm_doi(r)
                if d and d not in seen:
                    seen.add(d)
                    refs.append(d)
            out[paper_doi] = refs
    return out
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `uv run pytest tests/biblio/test_wos_refs.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/biblio/wos_refs.py tests/biblio/test_wos_refs.py
git commit -m "feat(plano-6): parser de Cited-References da WoS"
```

---

## Task 3: Cliente OpenAlex (`openalex.py`)

**Files:**
- Create: `scripts/biblio/openalex.py`
- Test: `tests/biblio/test_openalex.py`

**Contrato:**
- `referenced_works(doi, get) -> list[str]` — IDs OpenAlex (`W...`) citados por `doi`. `get(url)->dict` é injetável (HTTP isolado).
- `resolve_ids_to_dois(ids, get, batch=50) -> dict[str, str]` — mapeia `W-id → doi` via `/works?filter=openalex_id:...&select=id,doi`, em lotes.
- `make_http_get(mailto)` — `get` real com `requests` + retry (só usado em produção).
- I/O de cache fica no `refs_acquire` (Task 4), não aqui.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/biblio/test_openalex.py
from scripts.biblio.openalex import referenced_works, resolve_ids_to_dois


def fake_get_factory(responses):
    def get(url):
        return responses[url]
    return get


def test_referenced_works_returns_ids():
    url = "https://api.openalex.org/works/https://doi.org/10.1/x?mailto=e@x"
    get = fake_get_factory({url: {"referenced_works": ["https://openalex.org/W1",
                                                        "https://openalex.org/W2"]}})
    assert referenced_works("10.1/x", get, mailto="e@x") == ["W1", "W2"]


def test_resolve_ids_to_dois_batches():
    calls = []

    def get(url):
        calls.append(url)
        return {"results": [{"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1000/A"},
                            {"id": "https://openalex.org/W2", "doi": None}]}

    out = resolve_ids_to_dois(["W1", "W2"], get, mailto="e@x", batch=50)
    assert out == {"W1": "10.1000/a"}   # W2 sem DOI é omitido; registrant >=4 dígitos
    assert len(calls) == 1            # um único lote
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `uv run pytest tests/biblio/test_openalex.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.biblio.openalex'`

- [ ] **Step 3: Implementar o mínimo**

```python
# scripts/biblio/openalex.py
"""Cliente OpenAlex para aquisição de referências (Plano 6).

Fronteira de rede isolada: as funções recebem um `get(url)->dict` injetável,
testável sem rede. `make_http_get` devolve o `get` real (requests + polite pool
via mailto + retry). Identidade de referência sempre via DOI normalizado.
"""
from __future__ import annotations

from scripts.biblio.dois import norm_doi

API = "https://api.openalex.org"


def _short_id(openalex_id: str) -> str:
    return (openalex_id or "").rstrip("/").rsplit("/", 1)[-1]


def referenced_works(doi: str, get, *, mailto: str) -> list[str]:
    url = f"{API}/works/https://doi.org/{doi}?mailto={mailto}"
    obj = get(url)
    return [_short_id(w) for w in (obj.get("referenced_works") or [])]


def resolve_ids_to_dois(ids, get, *, mailto: str, batch: int = 50) -> dict[str, str]:
    ids = list(dict.fromkeys(ids))  # únicos, ordem preservada
    out: dict[str, str] = {}
    for i in range(0, len(ids), batch):
        chunk = ids[i:i + batch]
        filt = "openalex_id:" + "|".join(chunk)
        url = (f"{API}/works?filter={filt}&select=id,doi"
               f"&per-page={batch}&mailto={mailto}")
        for r in get(url).get("results", []):
            d = norm_doi(r.get("doi") or "")
            if d:
                out[_short_id(r.get("id", ""))] = d
    return out


def make_http_get(mailto: str):
    """`get(url)->dict` real, com retry/backoff. Só usado em produção."""
    import requests
    from tenacity import retry, stop_after_attempt, wait_exponential

    @retry(stop=stop_after_attempt(4),
           wait=wait_exponential(multiplier=2, min=2, max=30))
    def get(url: str) -> dict:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()

    return get
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `uv run pytest tests/biblio/test_openalex.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/biblio/openalex.py tests/biblio/test_openalex.py
git commit -m "feat(plano-6): cliente OpenAlex (referenced_works + resolução id→doi)"
```

---

## Task 4: Orquestrador de aquisição híbrida (`refs_acquire.py`)

**Files:**
- Create: `scripts/biblio/refs_acquire.py`
- Test: `tests/biblio/test_refs_acquire.py`

**Contrato:**
- `build_paper_refs(paper_dois, wos_map, oa_fetch, oa_resolve) -> tuple[list[tuple], dict]`
  retorna (linhas `(paper_doi, ref_doi, fonte)`, estatísticas). Para cada
  `paper_doi`: se está em `wos_map` → usa refs WoS (`fonte="wos"`); senão →
  `oa_fetch(paper_doi)` (IDs) resolvidos via `oa_resolve(ids)` (`fonte="openalex"`).
  `oa_fetch(doi)->list[str]` e `oa_resolve(ids)->dict[str,str]` são injetáveis.
- `run(...)` faz I/O: lê `06_extraction.csv` (incluídos com DOI) + `.bib` WoS,
  monta os fetchers reais com cache em disco, grava `08_paper_refs.csv` e caches.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/biblio/test_refs_acquire.py
from scripts.biblio.refs_acquire import build_paper_refs


def test_prefers_wos_then_openalex():
    paper_dois = ["10.1/a", "10.2/b"]
    wos_map = {"10.1/a": ["10.9/x", "10.9/y"]}

    def oa_fetch(doi):
        assert doi == "10.2/b"      # só o que não está na WoS
        return ["W1", "W2"]

    def oa_resolve(ids):
        return {"W1": "10.9/x", "W2": "10.7/z"}

    rows, stats = build_paper_refs(paper_dois, wos_map, oa_fetch, oa_resolve)
    assert ("10.1/a", "10.9/x", "wos") in rows
    assert ("10.2/b", "10.9/x", "openalex") in rows
    assert ("10.2/b", "10.7/z", "openalex") in rows
    assert stats["papers_wos"] == 1
    assert stats["papers_openalex"] == 1


def test_counts_papers_without_refs():
    def oa_fetch(doi):
        return []

    def oa_resolve(ids):
        return {}

    rows, stats = build_paper_refs(["10.3/c"], {}, oa_fetch, oa_resolve)
    assert rows == []
    assert stats["papers_sem_refs"] == 1
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `uv run pytest tests/biblio/test_refs_acquire.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.biblio.refs_acquire'`

- [ ] **Step 3: Implementar o mínimo**

```python
# scripts/biblio/refs_acquire.py
"""Aquisição híbrida de referências (Plano 6): WoS local onde houver, OpenAlex
no resto. Saída: data/processed/08_paper_refs.csv (paper_doi, ref_doi, fonte).

`build_paper_refs` é puro (fetchers injetáveis). `run` faz o I/O: carrega o
corpus + .bib, monta fetchers reais com cache em disco e grava os artefatos.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from scripts.biblio.dois import norm_doi
from scripts.biblio.openalex import (
    make_http_get, referenced_works, resolve_ids_to_dois,
)
from scripts.biblio.wos_refs import parse_wos_bib


def build_paper_refs(paper_dois, wos_map, oa_fetch, oa_resolve):
    rows: list[tuple[str, str, str]] = []
    stats = {"papers_wos": 0, "papers_openalex": 0, "papers_sem_refs": 0}
    for pd_ in paper_dois:
        if pd_ in wos_map:
            refs = wos_map[pd_]
            fonte = "wos"
            stats["papers_wos"] += 1
        else:
            ids = oa_fetch(pd_)
            idmap = oa_resolve(ids)
            refs = [idmap[i] for i in ids if i in idmap]
            fonte = "openalex"
            stats["papers_openalex"] += 1
        refs = [r for r in refs if r and r != pd_]
        if not refs:
            stats["papers_sem_refs"] += 1
        for r in refs:
            rows.append((pd_, r, fonte))
    return rows, stats


def _included_dois(extraction: Path) -> list[str]:
    df = pd.read_csv(extraction, encoding="utf-8", dtype=str).fillna("")
    inc = df[df["elegivel"] == "incluir"]
    dois = [norm_doi(d) for d in inc["doi"]]
    return list(dict.fromkeys([d for d in dois if d]))


def run(extraction: Path, wos_glob_dir: Path, out_csv: Path,
        cache_refs: Path, cache_idmap: Path, mailto: str) -> None:
    paper_dois = _included_dois(extraction)
    wos_map = parse_wos_bib(sorted(Path(wos_glob_dir).glob("*.bib")))

    get = make_http_get(mailto)
    refs_cache = json.loads(cache_refs.read_text()) if cache_refs.exists() else {}
    idmap = json.loads(cache_idmap.read_text()) if cache_idmap.exists() else {}

    def oa_fetch(doi: str):
        if doi not in refs_cache:
            refs_cache[doi] = referenced_works(doi, get, mailto=mailto)
        return refs_cache[doi]

    def oa_resolve(ids):
        missing = [i for i in ids if i not in idmap]
        if missing:
            idmap.update(resolve_ids_to_dois(missing, get, mailto=mailto))
        return idmap

    rows, stats = build_paper_refs(paper_dois, wos_map, oa_fetch, oa_resolve)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["paper_doi", "ref_doi", "fonte"]).to_csv(
        out_csv, index=False, encoding="utf-8")
    cache_refs.write_text(json.dumps(refs_cache, ensure_ascii=False))
    cache_idmap.write_text(json.dumps(idmap, ensure_ascii=False))
    print(f"Refs: {len(paper_dois)} papers c/ DOI | "
          f"{stats['papers_wos']} via WoS, {stats['papers_openalex']} via OpenAlex | "
          f"{stats['papers_sem_refs']} sem refs | {len(rows)} pares paper→ref")
    print(f"  → {out_csv}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--extraction", type=Path, required=True)
    p.add_argument("--wos-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--cache-refs", type=Path, required=True)
    p.add_argument("--cache-idmap", type=Path, required=True)
    p.add_argument("--mailto", required=True)
    a = p.parse_args(argv)
    run(a.extraction, a.wos_dir, a.out, a.cache_refs, a.cache_idmap, a.mailto)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `uv run pytest tests/biblio/test_refs_acquire.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/biblio/refs_acquire.py tests/biblio/test_refs_acquire.py
git commit -m "feat(plano-6): aquisição híbrida de referências (WoS+OpenAlex)"
```

---

## Task 5: Construção das redes (`networks.py`)

**Files:**
- Create: `scripts/biblio/networks.py`
- Test: `tests/biblio/test_networks.py`

**Contrato:**
- `load_paper_refs(csv) -> dict[str, set[str]]` — `paper_doi → {ref_doi}`.
- `build_coupling(paper_refs, min_shared=2) -> nx.Graph` — nós = papers; aresta
  com `weight` = nº de refs compartilhadas (≥ `min_shared`) e `cosine` =
  `shared/sqrt(|Ru|·|Rv|)`.
- `build_cocitation(paper_refs, k=3, top_n=300) -> nx.Graph` — nós = refs citadas
  por ≥ `k` papers; aresta `weight` = nº de papers que citam ambas; mantém os
  `top_n` nós por grau ponderado.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/biblio/test_networks.py
from scripts.biblio.networks import build_coupling, build_cocitation


PR = {
    "p1": {"a", "b", "c"},
    "p2": {"a", "b", "d"},      # compartilha a,b com p1 (2)
    "p3": {"a"},                # compartilha só a com p1/p2 (1)
}


def test_coupling_edge_weight_and_filter():
    G = build_coupling(PR, min_shared=2)
    assert G.has_edge("p1", "p2")
    assert G["p1"]["p2"]["weight"] == 2
    assert not G.has_edge("p1", "p3")   # só 1 compartilhada, filtrada
    assert abs(G["p1"]["p2"]["cosine"] - 2 / (3 ** 0.5 * 3 ** 0.5)) < 1e-9


def test_cocitation_threshold_and_weight():
    # 'a' citada por p1,p2,p3 (3); 'b' por p1,p2 (2)
    G = build_cocitation(PR, k=3, top_n=300)
    assert "a" in G.nodes          # citada por >=3
    assert "b" not in G.nodes      # citada por 2 < k
    # com k=2: a&b co-citadas por p1,p2 → weight 2
    G2 = build_cocitation(PR, k=2, top_n=300)
    assert G2["a"]["b"]["weight"] == 2
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `uv run pytest tests/biblio/test_networks.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.biblio.networks'`

- [ ] **Step 3: Implementar o mínimo**

```python
# scripts/biblio/networks.py
"""Construção das redes bibliométricas (Plano 6).

A partir do par paper_doi→ref_doi (08_paper_refs.csv): acoplamento
bibliográfico (nós = papers, peso = refs compartilhadas) e co-citação (nós =
refs citadas por >=k papers, peso = co-ocorrência em listas de referência).
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from itertools import combinations
from math import sqrt
from pathlib import Path

import networkx as nx
import pandas as pd


def load_paper_refs(csv: Path) -> dict[str, set[str]]:
    df = pd.read_csv(csv, encoding="utf-8", dtype=str).fillna("")
    out: dict[str, set[str]] = defaultdict(set)
    for paper, ref in zip(df["paper_doi"], df["ref_doi"]):
        if paper and ref:
            out[paper].add(ref)
    return dict(out)


def build_coupling(paper_refs, min_shared: int = 2) -> nx.Graph:
    # índice ref → papers que a citam; pares de papers que compartilham ref
    ref_to_papers: dict[str, list[str]] = defaultdict(list)
    for paper, refs in paper_refs.items():
        for r in refs:
            ref_to_papers[r].append(paper)
    shared: dict[tuple[str, str], int] = defaultdict(int)
    for papers in ref_to_papers.values():
        for u, v in combinations(sorted(set(papers)), 2):
            shared[(u, v)] += 1
    G = nx.Graph()
    G.add_nodes_from(paper_refs.keys())
    for (u, v), w in shared.items():
        if w >= min_shared:
            cos = w / sqrt(len(paper_refs[u]) * len(paper_refs[v]))
            G.add_edge(u, v, weight=w, cosine=cos)
    return G


def build_cocitation(paper_refs, k: int = 3, top_n: int = 300) -> nx.Graph:
    ref_count: dict[str, int] = defaultdict(int)
    for refs in paper_refs.values():
        for r in refs:
            ref_count[r] += 1
    keep = {r for r, c in ref_count.items() if c >= k}
    co: dict[tuple[str, str], int] = defaultdict(int)
    for refs in paper_refs.values():
        kept = sorted(refs & keep)
        for a, b in combinations(kept, 2):
            co[(a, b)] += 1
    G = nx.Graph()
    G.add_nodes_from(keep)
    for (a, b), w in co.items():
        G.add_edge(a, b, weight=w)
    if G.number_of_nodes() > top_n:
        wdeg = dict(G.degree(weight="weight"))
        top = sorted(wdeg, key=wdeg.get, reverse=True)[:top_n]
        G = G.subgraph(top).copy()
    return G


def run(refs_csv: Path, out_dir: Path, k: int, top_n: int, min_shared: int) -> None:
    paper_refs = load_paper_refs(refs_csv)
    out_dir.mkdir(parents=True, exist_ok=True)
    Gc = build_coupling(paper_refs, min_shared=min_shared)
    Gx = build_cocitation(paper_refs, k=k, top_n=top_n)
    nx.write_graphml(Gc, out_dir / "coupling.graphml")
    nx.write_graphml(Gx, out_dir / "cocitation.graphml")
    print(f"Acoplamento: {Gc.number_of_nodes()} nós, {Gc.number_of_edges()} arestas")
    print(f"Co-citação:  {Gx.number_of_nodes()} nós, {Gx.number_of_edges()} arestas")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--refs", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--top-n", type=int, default=300)
    p.add_argument("--min-shared", type=int, default=2)
    a = p.parse_args(argv)
    run(a.refs, a.out_dir, a.k, a.top_n, a.min_shared)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `uv run pytest tests/biblio/test_networks.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/biblio/networks.py tests/biblio/test_networks.py
git commit -m "feat(plano-6): redes de acoplamento e co-citação"
```

---

## Task 6: Clusterização e caracterização (`cluster.py`)

**Files:**
- Create: `scripts/biblio/cluster.py`
- Test: `tests/biblio/test_cluster.py`

**Contrato:**
- `louvain_clusters(G, seed=42) -> dict[node, int]` — comunidade por nó.
- `top_terms(titles, n=8) -> list[str]` — termos TF-IDF mais salientes do conjunto de títulos (vazio se < 1 título não-vazio).
- `crosstab_cluster(part, doi_to_cluster_keyfn...)` — ver assinatura abaixo:
  `crosstab(node_cluster, df, col) -> pd.DataFrame` cruza cluster × valores de
  `col` para os papers (`df` indexado por `paper_doi`).

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/biblio/test_cluster.py
import networkx as nx
import pandas as pd
from scripts.biblio.cluster import louvain_clusters, top_terms, crosstab


def test_louvain_two_cliques():
    G = nx.Graph()
    nx.add_path(G, ["a", "b", "c", "a"])      # triângulo 1
    nx.add_path(G, ["x", "y", "z", "x"])      # triângulo 2
    part = louvain_clusters(G, seed=1)
    assert part["a"] == part["b"] == part["c"]
    assert part["x"] == part["y"] == part["z"]
    assert part["a"] != part["x"]


def test_top_terms_picks_distinctive():
    titles = ["automation labor markets", "labor automation wages",
              "automation and tasks"]
    terms = top_terms(titles, n=3)
    assert "automation" in terms


def test_crosstab_counts():
    node_cluster = {"10.1/a": 0, "10.2/b": 0, "10.3/c": 1}
    df = pd.DataFrame(
        {"paper_doi": ["10.1/a", "10.2/b", "10.3/c"],
         "pre_pos_chatgpt": ["pre", "pos", "pos"]}
    ).set_index("paper_doi")
    ct = crosstab(node_cluster, df, "pre_pos_chatgpt")
    assert ct.loc[0, "pre"] == 1
    assert ct.loc[0, "pos"] == 1
    assert ct.loc[1, "pos"] == 1
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `uv run pytest tests/biblio/test_cluster.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.biblio.cluster'`

- [ ] **Step 3: Implementar o mínimo**

```python
# scripts/biblio/cluster.py
"""Clusterização (Louvain) e caracterização dos clusters (Plano 6).

Louvain nativo do networkx (ponderado, seed fixo p/ reprodutibilidade). Para o
acoplamento, cruza clusters com atributos do corpus (pré/pós, polarização etc.)
via crosstab; rótulos de cluster vêm de termos TF-IDF dos títulos.
"""
from __future__ import annotations

import networkx as nx
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer


def louvain_clusters(G: nx.Graph, seed: int = 42) -> dict:
    comms = nx.community.louvain_communities(G, weight="weight", seed=seed)
    return {node: idx for idx, comm in enumerate(comms) for node in comm}


def top_terms(titles, n: int = 8) -> list[str]:
    docs = [t for t in titles if t and t.strip()]
    if not docs:
        return []
    vec = TfidfVectorizer(stop_words="english", min_df=1, ngram_range=(1, 1))
    X = vec.fit_transform(docs)
    scores = X.mean(axis=0).A1
    terms = vec.get_feature_names_out()
    order = scores.argsort()[::-1][:n]
    return [terms[i] for i in order]


def crosstab(node_cluster: dict, df: pd.DataFrame, col: str) -> pd.DataFrame:
    clusters, vals = [], []
    for node, cl in node_cluster.items():
        if node in df.index:
            clusters.append(cl)
            vals.append(df.loc[node, col])
    return pd.crosstab(pd.Series(clusters, name="cluster"),
                       pd.Series(vals, name=col))
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `uv run pytest tests/biblio/test_cluster.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/biblio/cluster.py tests/biblio/test_cluster.py
git commit -m "feat(plano-6): Louvain + caracterização de clusters"
```

---

## Task 7: Renderização das saídas (`report.py`)

**Files:**
- Create: `scripts/biblio/report.py`

**Nota:** renderização (figuras/markdown) não é unit-testada (I/O visual); a
corretude vem das camadas puras já testadas. Este módulo só orquestra e desenha.

- [ ] **Step 1: Implementar o módulo de relatório**

```python
# scripts/biblio/report.py
"""Saídas exploratórias da linha bibliométrica (Plano 6) em reports/biblio/.

Lê os GraphML gerados, clusteriza, e produz: figura de cada rede (cor=cluster),
perfis de cluster (.csv) e um RESUMO.md. Para o acoplamento, cruza clusters com
pré/pós e polarização (join no 06_extraction.csv). Não unit-testado (I/O visual).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import networkx as nx
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from scripts.biblio.cluster import crosstab, louvain_clusters, top_terms  # noqa: E402
from scripts.biblio.dois import norm_doi  # noqa: E402


def _draw(G: nx.Graph, part: dict, title: str, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 7))
    if G.number_of_nodes():
        pos = nx.spring_layout(G, weight="weight", seed=42)
        colors = [part.get(n, 0) for n in G.nodes]
        nx.draw_networkx_nodes(G, pos, node_size=40, node_color=colors,
                               cmap="tab20", ax=ax)
        nx.draw_networkx_edges(G, pos, alpha=0.15, ax=ax)
    ax.set_title(title)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def _corpus_indexed(extraction: Path) -> pd.DataFrame:
    df = pd.read_csv(extraction, encoding="utf-8", dtype=str).fillna("")
    df = df[df["elegivel"] == "incluir"].copy()
    df["paper_doi"] = [norm_doi(d) for d in df["doi"]]
    return df[df["paper_doi"] != ""].set_index("paper_doi")


def _coupling_report(graphml: Path, corpus: pd.DataFrame, out_dir: Path) -> str:
    G = nx.read_graphml(graphml)
    part = louvain_clusters(G)
    n_clusters = len(set(part.values()))
    rows = []
    for cl in sorted(set(part.values())):
        members = [n for n, c in part.items() if c == cl]
        titles = [corpus.loc[n, "titulo"] for n in members if n in corpus.index]
        rows.append({"cluster": cl, "n_papers": len(members),
                     "termos": ", ".join(top_terms(titles, 8))})
    pd.DataFrame(rows).to_csv(out_dir / "clusters_acoplamento.csv", index=False)
    _draw(G, part, "Acoplamento bibliográfico (cor = cluster)",
          out_dir / "coupling.png")
    lines = [f"## Acoplamento: {n_clusters} clusters, {G.number_of_nodes()} papers\n"]
    for col in ("pre_pos_chatgpt", "polarizacao"):
        if col in corpus.columns:
            ct = crosstab(part, corpus, col)
            lines.append(f"\n### cluster × {col}\n\n```\n{ct.to_string()}\n```\n")
    return "\n".join(lines)


def _cocitation_report(graphml: Path, out_dir: Path) -> str:
    G = nx.read_graphml(graphml)
    part = louvain_clusters(G)
    n_clusters = len(set(part.values()))
    wdeg = dict(G.degree(weight="weight"))
    rows = []
    for cl in sorted(set(part.values())):
        members = sorted([n for n, c in part.items() if c == cl],
                         key=lambda n: wdeg.get(n, 0), reverse=True)
        rows.append({"cluster": cl, "n_refs": len(members),
                     "refs_centrais": ", ".join(members[:5])})
    pd.DataFrame(rows).to_csv(out_dir / "clusters_cocitacao.csv", index=False)
    _draw(G, part, "Co-citação da base intelectual (cor = cluster)",
          out_dir / "cocitation.png")
    return f"## Co-citação: {n_clusters} clusters, {G.number_of_nodes()} refs\n"


def run(net_dir: Path, extraction: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    corpus = _corpus_indexed(extraction)
    md = ["# Plano 6 — Resumo exploratório (acoplamento + co-citação)\n",
          "> Exploratório/descritivo; cobertura híbrida WoS+OpenAlex; refs sem DOI fora.\n"]
    md.append(_coupling_report(net_dir / "coupling.graphml", corpus, out_dir))
    md.append(_cocitation_report(net_dir / "cocitation.graphml", out_dir))
    (out_dir / "RESUMO.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Relatório: {out_dir}/RESUMO.md + figuras + clusters_*.csv")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--net-dir", type=Path, required=True)
    p.add_argument("--extraction", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    a = p.parse_args(argv)
    run(a.net_dir, a.extraction, a.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 2: Verificar import e smoke (sem rede)**

Run: `uv run python -c "import scripts.biblio.report"`
Expected: sem erro (módulo importa).

- [ ] **Step 3: Commit**

```bash
git add scripts/biblio/report.py
git commit -m "feat(plano-6): renderização das saídas (figuras + RESUMO.md + CSVs)"
```

---

## Task 8: Wiring no Makefile + execução end-to-end

**Files:**
- Modify: `Makefile` (adicionar alvo `biblio` perto dos alvos de análise)

- [ ] **Step 1: Adicionar o alvo `biblio` ao Makefile**

Adicionar após o bloco `analysis` (usar TAB de indentação, como o resto do Makefile):

```makefile
.PHONY: biblio biblio-refs biblio-networks biblio-report
biblio: biblio-refs biblio-networks biblio-report

biblio-refs:
	$(PYTHON) -m scripts.biblio.refs_acquire \
	    --extraction $(DATA_PROC)/06_extraction.csv \
	    --wos-dir $(DATA_RAW)/manual/wos \
	    --out $(DATA_PROC)/08_paper_refs.csv \
	    --cache-refs $(DATA_PROC)/08_refs_cache.json \
	    --cache-idmap $(DATA_PROC)/08_openalex_idmap.json \
	    --mailto zeca@nexxasolucoes.com.br

biblio-networks:
	$(PYTHON) -m scripts.biblio.networks \
	    --refs $(DATA_PROC)/08_paper_refs.csv \
	    --out-dir reports/biblio \
	    --k 3 --top-n 300 --min-shared 2

biblio-report:
	$(PYTHON) -m scripts.biblio.report \
	    --net-dir reports/biblio \
	    --extraction $(DATA_PROC)/06_extraction.csv \
	    --out-dir reports/biblio
```

- [ ] **Step 2: Rodar a suíte de testes completa do pacote**

Run: `uv run pytest tests/biblio/ -v`
Expected: PASS (todos os testes das Tasks 1–6).

- [ ] **Step 3: Executar a aquisição de referências (faz rede; cacheia)**

Run: `make biblio-refs`
Expected: linha de resumo tipo `Refs: 785 papers c/ DOI | ~455 via WoS, ~330 via OpenAlex | N sem refs | M pares paper→ref` e `data/processed/08_paper_refs.csv` criado. (Pode levar minutos pelas chamadas OpenAlex; é idempotente — re-rodar usa cache.)

- [ ] **Step 4: Construir redes e relatório**

Run: `make biblio-networks && make biblio-report`
Expected: `reports/biblio/{coupling,cocitation}.graphml`, `*.png`, `clusters_*.csv`, `RESUMO.md`. Sem exceções.

- [ ] **Step 5: Inspeção rápida do resultado**

Run: `cat reports/biblio/RESUMO.md`
Expected: nº de clusters de cada rede + crosstabs cluster × pré/pós e × polarização legíveis. (Revisão substantiva fica para a discussão com o autor.)

- [ ] **Step 6: Commit**

```bash
git add Makefile
git commit -m "feat(plano-6): make biblio — pipeline bibliométrico end-to-end"
```

---

## Self-Review

**Spec coverage:**
- Camada 1 (aquisição WoS+OpenAlex, identidade DOI, caches, 08_paper_refs.csv) → Tasks 2,3,4. ✔
- Camada 2 (acoplamento + co-citação, GraphML, K/top-N/min-shared) → Task 5. ✔
- Camada 3 (Louvain, top termos, crosstab pré/pós × polarização) → Tasks 6,7. ✔
- Camada 4 (figuras, perfis .csv, RESUMO.md em reports/biblio/) → Task 7. ✔
- Driver `make biblio` separado de `make analysis` → Task 8. ✔
- Testes TDD das funções puras (parsing, doi, redes, cluster, crosstab) → Tasks 1–6. ✔
- Caveats documentados nas saídas (cabeçalho do RESUMO.md) → Task 7. ✔
- Sem dependência nova (networkx/sklearn/requests já presentes). ✔

**Placeholder scan:** sem TBD/TODO; todo passo de código tem o código completo. ✔

**Type/assinatura consistency:** `norm_doi` (Task 1) usado em 2,3,4,7. `parse_wos_bib` retorna `dict[str,list[str]]`, consumido por `build_paper_refs` como `wos_map` (Task 4). `build_paper_refs` retorna `(rows, stats)`; `run` grava `rows`. `load_paper_refs`→`dict[str,set]` alimenta `build_coupling`/`build_cocitation` (Task 5). `louvain_clusters`/`top_terms`/`crosstab` (Task 6) usados em `report.py` (Task 7) com as mesmas assinaturas. ✔

**Decisões ajustáveis pós-exploração:** `k=3`, `top_n=300`, `min_shared=2` (flags do Makefile/CLI); refs sem DOI descartadas (documentado).
