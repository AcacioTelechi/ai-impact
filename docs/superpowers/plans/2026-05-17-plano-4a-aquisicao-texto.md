# Plano 4a — Aquisição de texto completo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Para os 852 estudos do corpus pós-arbitragem, resolver e baixar PDFs (Unpaywall OA + drop-in manual institucional), armazenando-os nativos, e emitir um manifesto de cobertura (`text_source` = pdf | abstract) que liga 4a → 4b.

**Architecture:** Um script novo `scripts/extraction/fulltext_acquire.py` que reusa `_unpaywall_lookup` (de `fetch_fulltext.py`) e `cache_key`/`custom_id` (de `batch_client.py`). I/O de rede atrás de callables injetáveis (`lookup_fn`/`get_fn`) → testes determinísticos sem rede. Idempotente/retomável: PDFs já em disco não são re-baixados; drop-in tem prioridade sobre OA.

**Tech Stack:** Python 3.12, pandas, requests, tenacity (já no projeto). **Sem dependências novas** (sem lib de PDF — o 4b lê o PDF nativo).

**Spec:** `docs/superpowers/specs/2026-05-17-plano-4a-aquisicao-texto-design.md`

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `.gitignore` | (modificar) ignorar `data/raw/fulltext/` (PDFs com copyright) |
| `scripts/extraction/fulltext_acquire.py` | **novo:** `assign_ids`, `download_pdf`, `resolve`, `run`, `_cli` |
| `tests/extraction/test_fulltext_acquire.py` | **novo:** testes (fakes, sem rede) |
| `Makefile` | (modificar) alvo `fulltext-acquire` |
| `protocols/slr_protocol.md` | (modificar) nota de aquisição em §7 |

Reusos (não modificar): `scripts/screening/fetch_fulltext.py::_unpaywall_lookup(doi, email="") -> dict | None` (retorna `{"pdf_url": ...}` ou `None`); `scripts/screening/llm/batch_client.py::cache_key(row)`, `custom_id(key)`.

Convenções: `from __future__ import annotations`; `_cli(argv)` + `if __name__ == "__main__": sys.exit(_cli(sys.argv[1:]))`; `print` p/ feedback; venv local (`source .venv/bin/activate`, **não** `uv run`); pytest TDD; commits convencionais terminando com `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

`scripts/extraction/` e `tests/extraction/` já existem (têm `extract.py`/`validate.py` do esqueleto do Plano 1 — **não tocar**).

---

## Task 1: `.gitignore` — ignorar PDFs (copyright, segurança primeiro)

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Editar `.gitignore`**

O `.gitignore` já tem uma seção de dados (linhas ~228-243 com `data/raw/**/*.csv` etc.). PDFs (`.pdf`) NÃO são cobertos por esses globs. Adicionar, logo após a linha `data/raw/searches/manual/`:

```
data/raw/fulltext/
```

- [ ] **Step 2: Verificar**

Run: `mkdir -p data/raw/fulltext/oa && touch data/raw/fulltext/oa/s-001.pdf && git check-ignore data/raw/fulltext/oa/s-001.pdf && rm -rf data/raw/fulltext`
Expected: imprime `data/raw/fulltext/oa/s-001.pdf` (está ignorado), depois remove o dir de teste.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore(4a): gitignore data/raw/fulltext/ (PDFs com copyright)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `assign_ids` — id estável `s-NNN`

**Files:**
- Create: `scripts/extraction/fulltext_acquire.py`
- Test: `tests/extraction/test_fulltext_acquire.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/extraction/test_fulltext_acquire.py
import pandas as pd

from scripts.extraction.fulltext_acquire import assign_ids
from scripts.screening.llm.batch_client import cache_key, custom_id


def _row(doi, title, year=2020):
    return {"source": "wos", "doi": doi, "title": title, "authors": "A, B",
            "year": year, "abstract": "abs", "venue": "V", "language": "en"}


def test_assign_ids_deterministic_and_stable_under_reorder():
    df1 = pd.DataFrame([_row("10.1/c", "C"), _row("10.1/a", "A"), _row("10.1/b", "B")])
    df2 = df1.iloc[::-1].reset_index(drop=True)  # ordem invertida
    a1 = assign_ids(df1)
    a2 = assign_ids(df2)
    # mesma (doi → id) independentemente da ordem de entrada
    m1 = dict(zip(a1["doi"], a1["id"]))
    m2 = dict(zip(a2["doi"], a2["id"]))
    assert m1 == m2
    # formato s-NNN, único, sequencial
    assert sorted(a1["id"]) == ["s-001", "s-002", "s-003"]
    assert a1["id"].is_unique
    # review_id == custom_id(cache_key(row)) e ordenação por ele
    r0 = a1.iloc[0]
    assert r0["review_id"] == custom_id(cache_key(r0))


def test_assign_ids_width_scales_to_corpus():
    df = pd.DataFrame([_row(f"10.1/{i}", f"T{i}") for i in range(12)])
    a = assign_ids(df)
    assert set(a["id"]) == {f"s-{i:03d}" for i in range(1, 13)}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/extraction/test_fulltext_acquire.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.extraction.fulltext_acquire`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/extraction/fulltext_acquire.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/extraction/test_fulltext_acquire.py -v`
Expected: PASS (2). Full suite: `source .venv/bin/activate && pytest -q` (was 155; +2 = 157). Report actual.

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction/fulltext_acquire.py tests/extraction/test_fulltext_acquire.py
git commit -m "feat(4a): assign_ids — id s-NNN estável (chave 4a→4b)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `download_pdf` — download atômico com guard de 32 MB

**Files:**
- Modify: `scripts/extraction/fulltext_acquire.py`
- Test: `tests/extraction/test_fulltext_acquire.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# adicionar a tests/extraction/test_fulltext_acquire.py
from pathlib import Path
from scripts.extraction.fulltext_acquire import download_pdf, MAX_PDF_BYTES


def test_download_pdf_ok_atomic(tmp_path: Path):
    dest = tmp_path / "s-001.pdf"
    status = download_pdf("http://x/p.pdf", dest, get_fn=lambda u: b"%PDF-1.4 ok")
    assert status == "ok"
    assert dest.exists() and dest.read_bytes() == b"%PDF-1.4 ok"
    assert not (tmp_path / "s-001.pdf.part").exists()  # sem parcial


def test_download_pdf_failure_leaves_nothing(tmp_path: Path):
    dest = tmp_path / "s-002.pdf"
    status = download_pdf("http://x/p.pdf", dest, get_fn=lambda u: None)
    assert status == "download_falhou"
    assert not dest.exists()
    assert not (tmp_path / "s-002.pdf.part").exists()


def test_download_pdf_oversized_rejected(tmp_path: Path):
    dest = tmp_path / "s-003.pdf"
    big = b"x" * (MAX_PDF_BYTES + 1)
    status = download_pdf("http://x/big.pdf", dest, get_fn=lambda u: big)
    assert status == "oversized"
    assert not dest.exists()
    assert not (tmp_path / "s-003.pdf.part").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/extraction/test_fulltext_acquire.py -k download_pdf -v`
Expected: FAIL — `ImportError: cannot import name 'download_pdf'`

- [ ] **Step 3: Write minimal implementation (append)**

Adicionar imports no topo (junto aos existentes): `import requests` e `from tenacity import retry, stop_after_attempt, wait_exponential`. Então:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/extraction/test_fulltext_acquire.py -v`
Expected: PASS (2 + 3 = 5). Full suite `pytest -q` (157 + 3 = 160). Report actual.

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction/fulltext_acquire.py tests/extraction/test_fulltext_acquire.py
git commit -m "feat(4a): download_pdf — atômico, guard 32MB, injetável

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `resolve` — precedência manual > unpaywall > abstract

**Files:**
- Modify: `scripts/extraction/fulltext_acquire.py`
- Test: `tests/extraction/test_fulltext_acquire.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# adicionar a tests/extraction/test_fulltext_acquire.py
from scripts.extraction.fulltext_acquire import resolve


def _dirs(tmp_path):
    m = tmp_path / "manual"; o = tmp_path / "oa"
    m.mkdir(); o.mkdir()
    return m, o


def test_resolve_manual_has_priority(tmp_path):
    m, o = _dirs(tmp_path)
    (m / "s-001.pdf").write_bytes(b"%PDF inst")
    row = pd.Series(_row("10.1/x", "X"))
    r = resolve(row, "s-001", m, o, email="e@e",
                lookup_fn=lambda doi, email: {"pdf_url": "http://x/p.pdf"},
                download_fn=lambda u, d: "ok")
    assert r["text_source"] == "pdf" and r["fonte"] == "manual"
    assert r["status"] == "ok_manual"
    assert r["pdf_path"].endswith("manual/s-001.pdf")


def test_resolve_no_doi(tmp_path):
    m, o = _dirs(tmp_path)
    row = pd.Series(_row("", "X"))
    r = resolve(row, "s-002", m, o, email="e@e",
                lookup_fn=lambda doi, email: None, download_fn=lambda u, d: "ok")
    assert r["text_source"] == "abstract" and r["status"] == "sem_doi"
    assert r["fonte"] == "—" and r["pdf_path"] == ""


def test_resolve_not_oa(tmp_path):
    m, o = _dirs(tmp_path)
    row = pd.Series(_row("10.1/x", "X"))
    r = resolve(row, "s-003", m, o, email="e@e",
                lookup_fn=lambda doi, email: None, download_fn=lambda u, d: "ok")
    assert r["text_source"] == "abstract" and r["status"] == "nao_oa"


def test_resolve_oa_download_ok(tmp_path):
    m, o = _dirs(tmp_path)
    row = pd.Series(_row("10.1/x", "X"))
    captured = {}

    def fake_dl(url, dest):
        captured["dest"] = dest
        Path(dest).write_bytes(b"%PDF oa")
        return "ok"

    r = resolve(row, "s-004", m, o, email="e@e",
                lookup_fn=lambda doi, email: {"pdf_url": "http://x/p.pdf"},
                download_fn=fake_dl)
    assert r["text_source"] == "pdf" and r["fonte"] == "unpaywall"
    assert r["status"] == "ok_oa" and r["pdf_path"].endswith("oa/s-004.pdf")


def test_resolve_oa_download_failure_and_oversized(tmp_path):
    m, o = _dirs(tmp_path)
    row = pd.Series(_row("10.1/x", "X"))
    r_fail = resolve(row, "s-005", m, o, email="e@e",
                     lookup_fn=lambda doi, email: {"pdf_url": "u"},
                     download_fn=lambda u, d: "download_falhou")
    assert r_fail["text_source"] == "abstract" and r_fail["status"] == "download_falhou"
    r_big = resolve(row, "s-006", m, o, email="e@e",
                    lookup_fn=lambda doi, email: {"pdf_url": "u"},
                    download_fn=lambda u, d: "oversized")
    assert r_big["text_source"] == "abstract" and r_big["status"] == "oversized"


def test_resolve_idempotent_existing_oa(tmp_path):
    m, o = _dirs(tmp_path)
    (o / "s-007.pdf").write_bytes(b"%PDF cached")
    row = pd.Series(_row("10.1/x", "X"))
    calls = {"n": 0}

    def dl(u, d):
        calls["n"] += 1
        return "ok"

    r = resolve(row, "s-007", m, o, email="e@e",
                lookup_fn=lambda doi, email: {"pdf_url": "u"}, download_fn=dl)
    assert r["status"] == "ok_oa" and r["fonte"] == "unpaywall"
    assert calls["n"] == 0  # já em disco → não re-baixa
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/extraction/test_fulltext_acquire.py -k resolve -v`
Expected: FAIL — `ImportError: cannot import name 'resolve'`

- [ ] **Step 3: Write minimal implementation (append)**

```python
def resolve(row, id_: str, manual_dir: Path, oa_dir: Path, *, email: str,
            lookup_fn, download_fn) -> dict:
    """Resolve o texto de UM registro. Precedência: manual > oa-cache >
    unpaywall+download > abstract. Retorna a linha do manifesto.

    lookup_fn(doi, email)->dict|None (default produção: _unpaywall_lookup).
    download_fn(url, dest)->str (default produção: download_pdf).
    """
    doi = str(row.get("doi") or "").strip()
    base = {"id": id_, "review_id": row.get("review_id", ""),
            "doi": doi, "title": str(row.get("title") or "")}

    manual_pdf = manual_dir / f"{id_}.pdf"
    if manual_pdf.exists():
        return {**base, "text_source": "pdf", "fonte": "manual",
                "pdf_path": str(manual_pdf), "status": "ok_manual"}

    oa_pdf = oa_dir / f"{id_}.pdf"
    if oa_pdf.exists():  # idempotente: já baixado antes
        return {**base, "text_source": "pdf", "fonte": "unpaywall",
                "pdf_path": str(oa_pdf), "status": "ok_oa"}

    if not doi:
        return {**base, "text_source": "abstract", "fonte": "—",
                "pdf_path": "", "status": "sem_doi"}

    rec = lookup_fn(doi, email)
    if not rec or not rec.get("pdf_url"):
        return {**base, "text_source": "abstract", "fonte": "—",
                "pdf_path": "", "status": "nao_oa"}

    st = download_fn(rec["pdf_url"], oa_pdf)
    if st == "ok":
        return {**base, "text_source": "pdf", "fonte": "unpaywall",
                "pdf_path": str(oa_pdf), "status": "ok_oa"}
    return {**base, "text_source": "abstract", "fonte": "—",
            "pdf_path": "", "status": st}  # download_falhou | oversized
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/extraction/test_fulltext_acquire.py -v`
Expected: PASS (5 + 6 = 11). Full suite `pytest -q` (160 + 6 = 166). Report actual.

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction/fulltext_acquire.py tests/extraction/test_fulltext_acquire.py
git commit -m "feat(4a): resolve — precedência manual>oa>abstract, idempotente

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `run` + `_cli` — orquestração + cobertura

**Files:**
- Modify: `scripts/extraction/fulltext_acquire.py`
- Test: `tests/extraction/test_fulltext_acquire.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# adicionar a tests/extraction/test_fulltext_acquire.py
import json
from scripts.extraction import fulltext_acquire


def test_run_writes_manifest_and_coverage(tmp_path, capsys):
    src = tmp_path / "03_incluidos_final.csv"
    pd.DataFrame([
        _row("10.1/a", "A"), _row("10.1/b", "B"), _row("", "C"),
    ]).to_csv(src, index=False)
    m, o = _dirs(tmp_path)
    manifest = tmp_path / "04_fulltext_manifest.csv"

    # A → OA ok ; B → não-OA ; C → sem doi
    def lookup(doi, email):
        return {"pdf_url": "u"} if doi == "10.1/a" else None

    def dl(url, dest):
        Path(dest).write_bytes(b"%PDF")
        return "ok"

    fulltext_acquire.run(input=src, manifest=manifest, email="e@e",
                         manual_dir=m, oa_dir=o, lookup_fn=lookup, download_fn=dl)
    mf = pd.read_csv(manifest, keep_default_na=False)
    assert len(mf) == 3
    assert set(mf.columns) == {"id", "review_id", "doi", "title",
                               "text_source", "fonte", "pdf_path", "status"}
    assert (mf["id"].str.match(r"s-\d{3}")).all()
    assert (mf["text_source"] == "pdf").sum() == 1
    assert (mf["text_source"] == "abstract").sum() == 2
    out = capsys.readouterr().out
    assert "Aquisição:" in out and "de 3" in out


def test_run_idempotent_and_incorporates_dropin(tmp_path, capsys):
    src = tmp_path / "c.csv"
    pd.DataFrame([_row("10.1/a", "A")]).to_csv(src, index=False)
    m, o = _dirs(tmp_path)
    manifest = tmp_path / "mf.csv"
    calls = {"n": 0}

    def lookup(doi, email):
        return None  # sem OA

    def dl(url, dest):
        calls["n"] += 1
        return "ok"

    # 1ª rodada: sem OA → abstract
    fulltext_acquire.run(input=src, manifest=manifest, email="e@e",
                         manual_dir=m, oa_dir=o, lookup_fn=lookup, download_fn=dl)
    mf1 = pd.read_csv(manifest, keep_default_na=False)
    sid = mf1.iloc[0]["id"]
    assert mf1.iloc[0]["text_source"] == "abstract"
    # usuário deposita o PDF institucional como <id>.pdf
    (m / f"{sid}.pdf").write_bytes(b"%PDF inst")
    fulltext_acquire.run(input=src, manifest=manifest, email="e@e",
                         manual_dir=m, oa_dir=o, lookup_fn=lookup, download_fn=dl)
    mf2 = pd.read_csv(manifest, keep_default_na=False)
    assert mf2.iloc[0]["text_source"] == "pdf"
    assert mf2.iloc[0]["fonte"] == "manual"
    assert calls["n"] == 0  # nunca baixou (sem OA; depois drop-in)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/extraction/test_fulltext_acquire.py -k run -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'run'`

- [ ] **Step 3: Write minimal implementation (append)**

Adicionar import no topo: `from scripts.screening.fetch_fulltext import _unpaywall_lookup`.

```python
def run(input: Path, manifest: Path, email: str,
        manual_dir: Path, oa_dir: Path,
        lookup_fn=None, download_fn=None) -> None:
    lookup_fn = lookup_fn if lookup_fn is not None else _unpaywall_lookup
    download_fn = download_fn if download_fn is not None else download_pdf
    manual_dir.mkdir(parents=True, exist_ok=True)
    oa_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input, encoding="utf-8", keep_default_na=False)
    df = assign_ids(df)

    rows: list[dict] = []
    for _, r in df.iterrows():
        rows.append(resolve(r, r["id"], manual_dir, oa_dir, email=email,
                            lookup_fn=lookup_fn, download_fn=download_fn))
    mf = pd.DataFrame(rows).sort_values("id", kind="stable").reset_index(drop=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    mf.to_csv(manifest, index=False, encoding="utf-8")

    n = len(mf)
    n_pdf = int((mf["text_source"] == "pdf").sum())
    n_man = int((mf["fonte"] == "manual").sum())
    n_oa = int((mf["fonte"] == "unpaywall").sum())
    n_abs = int((mf["text_source"] == "abstract").sum())
    print(f"Aquisição: {n_pdf} pdf ({n_man} manual / {n_oa} oa) | "
          f"{n_abs} abstract — de {n}")
    print(f"  → {manifest}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Plano 4a: aquisição de texto completo.")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--email", default="")
    p.add_argument("--manual-dir", type=Path, default=Path("data/raw/fulltext/manual"))
    p.add_argument("--oa-dir", type=Path, default=Path("data/raw/fulltext/oa"))
    a = p.parse_args(argv)
    run(input=a.input, manifest=a.manifest, email=a.email,
        manual_dir=a.manual_dir, oa_dir=a.oa_dir)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/extraction/test_fulltext_acquire.py -v` → PASS (11 + 2 = 13).
Full suite `source .venv/bin/activate && pytest -q` (166 + 2 = 168). Report actual.
`source .venv/bin/activate && python -c "import scripts.extraction.fulltext_acquire; print('ok')"` → ok.

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction/fulltext_acquire.py tests/extraction/test_fulltext_acquire.py
git commit -m "feat(4a): run + CLI — manifesto + cobertura, idempotente

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Makefile — alvo `fulltext-acquire`

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Editar o Makefile**

Adicionar APÓS o alvo `arbitragem` e ANTES de `fetch`. TABs, não espaços. `$(PYTHON)`/`$(DATA_PROC)`/`$(EMAIL)` são variáveis existentes:

```makefile
.PHONY: fulltext-acquire
fulltext-acquire:
	$(PYTHON) -m scripts.extraction.fulltext_acquire \
	    --input $(DATA_PROC)/03_incluidos_final.csv \
	    --manifest $(DATA_PROC)/04_fulltext_manifest.csv \
	    --email $(EMAIL) \
	    --manual-dir data/raw/fulltext/manual \
	    --oa-dir data/raw/fulltext/oa
```

NÃO adicionar a `screen`/`all` (operação assistida por humano, rede). Não modificar outro alvo.

- [ ] **Step 2: Verificar**

Run: `make -n fulltext-acquire`
Expected: imprime o comando com os 5 flags, sem erro de Make. Rodar `make -n screen` para confirmar inalterado.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "build(4a): alvo fulltext-acquire (fora de screen)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Protocolo §7 — nota de aquisição

**Files:**
- Modify: `protocols/slr_protocol.md`

- [ ] **Step 1: Editar `protocols/slr_protocol.md`**

Localizar o item 4 de `## 7. Processo de seleção` (`4. **Eligibility (texto completo)** — leitura completa, 100% manual.`). Acrescentar logo após esse item (antes do item 5) o parágrafo:

```markdown

A aquisição de texto completo (2026-05-17) usa Unpaywall (OA automático) com
suplemento institucional manual (PDFs depositados pelo revisor); o PDF é lido
nativamente pelo LLM no Plano 4b (sem extração de texto intermediária).
Estudos sem OA e sem suplemento manual ficam em nível de resumo (`abstract`),
com a cobertura full-text reportada no PRISMA e nas limitações. A decisão de
elegibilidade e a extração por LLM (com verificação humana amostral) — e o
desvio metodológico em relação à leitura 100% manual prevista — são descritos
e declarados no Plano 4b.
```

- [ ] **Step 2: Verificar e commitar**

Run: `grep -n "Unpaywall (OA automático)\|Plano 4b" protocols/slr_protocol.md`
Expected: mostra o parágrafo inserido em §7.

```bash
git add protocols/slr_protocol.md
git commit -m "docs(protocol): §7 — método de aquisição de texto (4a)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Verificação final + tag `v0.6.0-fulltext`

**Files:** nenhum (validação)

- [ ] **Step 1: Suíte completa verde**

Run: `source .venv/bin/activate && pytest -q`
Expected: todos verdes (≥ 155 prévios + novos). Anotar total.

- [ ] **Step 2: Dry-run no corpus real com lookup/download FAKE (sem rede, sem baixar nada)**

Run:
```bash
source .venv/bin/activate && python -c "
from pathlib import Path
import pandas as pd
from scripts.extraction import fulltext_acquire as fa
mdir = Path('/tmp/ft_manual'); odir = Path('/tmp/ft_oa')
mdir.mkdir(parents=True, exist_ok=True); odir.mkdir(parents=True, exist_ok=True)
fa.run(input=Path('data/processed/03_incluidos_final.csv'),
       manifest=Path('/tmp/04_fulltext_manifest.csv'), email='e@e',
       manual_dir=mdir, oa_dir=odir,
       lookup_fn=lambda doi, email: None,           # finge: nada OA
       download_fn=lambda u, d: 'download_falhou')
mf = pd.read_csv('/tmp/04_fulltext_manifest.csv', keep_default_na=False)
print('linhas:', len(mf), '(esperado 852)')
print('ids únicos s-NNN:', mf['id'].is_unique, mf['id'].iloc[0], mf['id'].iloc[-1])
print('status dist:', mf['status'].value_counts().to_dict())
"
```
Expected: 852 linhas; ids `s-001`..`s-852` únicos; com lookup fake retornando None, status majoritariamente `nao_oa` (e `sem_doi` para os ~33 sem DOI). Confirma que o pipeline roda no corpus real sem rede e o manifesto/contagem batem. (A execução REAL com Unpaywall + drop-in é operação manual do usuário, fora deste plano.)

- [ ] **Step 3: Confirmar gitignore protege PDFs**

Run: `touch data/raw/fulltext/oa/s-001.pdf 2>/dev/null || (mkdir -p data/raw/fulltext/oa && touch data/raw/fulltext/oa/s-001.pdf); git status --porcelain data/raw/fulltext/ ; git check-ignore data/raw/fulltext/oa/s-001.pdf`
Expected: `git status` não lista nada em `data/raw/fulltext/`; `git check-ignore` imprime o caminho (ignorado). Limpar: `rm -rf data/raw/fulltext`.

- [ ] **Step 4: Tag**

```bash
git tag -a v0.6.0-fulltext -m "Plano 4a: aquisição de texto completo

Unpaywall OA + drop-in manual; PDF nativo (lido pelo Claude no 4b);
manifesto 04_fulltext_manifest.csv com cobertura. id s-NNN estável
(chave 4a→4b). Execução real (rede + drop-in) é operação manual do usuário."
git tag -l | tail -3
```

---

## Self-Review (autor do plano)

**Cobertura do spec:** §1 decisões (híbrido/PDF nativo/Unpaywall+drop-in/sem-deps/id s-NNN) → Tasks 2-5; §2 arquitetura → Tasks 2-5 (reuso `_unpaywall_lookup`/`cache_key`/`custom_id`); §3 id estável → Task 2; §4 schema manifesto → Tasks 4,5 (8 colunas exatas); §5 resolução/fallback/idempotência → Tasks 4,5; §6 robustez/gitignore/sem-rede-nos-testes → Tasks 1,3,4,5; §7 testes → todas; §8 Makefile+protocolo → Tasks 6,7 (prisma fora de escopo, só registrado); §9 YAGNI (sem lib PDF, sem resolvers extras, não tocar fetch_fulltext/extract.py) → respeitado; §10 sucesso → Task 8. Sem lacunas.

**Placeholders:** nenhum "TBD/TODO"; todo passo de código tem o código completo; comandos com saída esperada explícita. Task 1 (gitignore) é primeira deliberadamente (copyright/segurança antes de qualquer download).

**Consistência de tipos:** `assign_ids(df)->DataFrame` (+`review_id`,`id`) (T2) consumido por `run` (T5); `download_pdf(url,dest,*,get_fn=None,max_bytes)->str` em {"ok","download_falhou","oversized"} (T3) injetado como `download_fn` em `resolve` (T4) e default em `run` (T5); `resolve(row,id_,manual_dir,oa_dir,*,email,lookup_fn,download_fn)->dict` com as 8 chaves do manifesto (T4) montadas em DataFrame por `run` (T5); `lookup_fn` assinatura `(doi,email)->dict|None` idêntica a `_unpaywall_lookup` (reuso real em T5). `id` = `s-{i:03d}` consistente T2/T4/T5. Schema do manifesto (8 colunas) idêntico entre T4 (produz dict), T5 (escreve) e o teste de schema. `keep_default_na=False` na leitura (T5) — célula vazia = "" (coerente com `resolve` tratando doi ""). Consistente.
