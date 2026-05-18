# Fix `extract-llm` robusto e re-rodável — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir o defeito que faz o cache do batch gravar respostas-de-erro como fallback terminal (RC2) e fazer PDFs inválidos/protegidos caírem para o caminho `abstract` (RC3), mais uma migração one-off que limpa o cache e corrige o manifesto da 1ª rodada real.

**Architecture:** Sentinela `None` no contrato do `submit_fn` — request API-errored vira `None` e `screen_with_model` não o cacheia (re-rodada reprocessa); resposta que a API devolveu (mesmo vazia/quebrada) é cacheada como fallback terminal. `pdf_is_extractable` (pypdf) decide PDF vs abstract em `build_user_content`. Um script one-off lê os resultados do batch (retidos ~29 dias) e remove do cache exatamente os errored + corrige o manifesto.

**Tech Stack:** Python 3.12, pytest (TDD), pandas, anthropic SDK (Message Batches), pypdf (novo), venv ativado direto (`source .venv/bin/activate`, **nunca** `uv run`).

**Ambiente (todo subagente):** sempre `source /home/acacio/dev/pessoal/ai-impact/.venv/bin/activate` antes de python/pytest. Branch já criada: `fix-extract-llm-cache-pdf`. Mensagens de commit terminam com:
`Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`
Spec de referência: `docs/superpowers/specs/2026-05-17-fix-extract-llm-cache-pdf-robustez-design.md`.

**Mapa de arquivos:**
- Modify `pyproject.toml` — adiciona `pypdf`.
- Create `scripts/extraction/pdf_validity.py` — `pdf_is_extractable(path)`.
- Modify `scripts/extraction/extract_llm.py:39-57` — `build_user_content` usa `pdf_is_extractable`.
- Modify `scripts/screening/llm/batch_client.py:186-196` — `screen_with_model` não cacheia `None`, fallback em memória, log.
- Modify `scripts/screening/llm/batch_client.py:258-275` — `anthropic_submit_fn` devolve `None` p/ não-`succeeded`, conta erros.
- Create `scripts/extraction/migrate_failed_run.py` — migração one-off.
- Modify `protocols/slr_protocol.md` §8/§11 — nota honesta do incidente.
- Tests: `tests/extraction/test_pdf_validity.py` (novo), `tests/extraction/test_extract_llm.py` (estende), `tests/screening/test_batch_client.py` (estende), `tests/extraction/test_migrate_failed_run.py` (novo).

---

### Task 1: Dependência `pypdf` + `pdf_is_extractable`

**Files:**
- Modify: `pyproject.toml:21`
- Create: `scripts/extraction/pdf_validity.py`
- Test: `tests/extraction/test_pdf_validity.py`

- [ ] **Step 1: Adicionar `pypdf` às dependências e instalar**

Em `pyproject.toml`, dentro de `dependencies = [ ... ]`, após a linha `"langdetect>=1.0.9",` (linha 21), acrescentar:
```toml
    "pypdf>=4.0",
```
Depois:
```bash
source /home/acacio/dev/pessoal/ai-impact/.venv/bin/activate && uv pip install "pypdf>=4.0"
```
Expected: `Successfully installed pypdf-...` (ou "already satisfied").

- [ ] **Step 2: Escrever o teste que falha**

Criar `tests/extraction/test_pdf_validity.py`:
```python
from pathlib import Path

from pypdf import PdfWriter

from scripts.extraction.pdf_validity import pdf_is_extractable


def _valid_pdf(p: Path) -> Path:
    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    with open(p, "wb") as f:
        w.write(f)
    return p


def _encrypted_pdf(p: Path) -> Path:
    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    w.encrypt("segredo")
    with open(p, "wb") as f:
        w.write(f)
    return p


def test_valid_pdf_is_extractable(tmp_path):
    assert pdf_is_extractable(_valid_pdf(tmp_path / "ok.pdf")) is True


def test_junk_bytes_not_extractable(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"<html>paywall</html>")
    assert pdf_is_extractable(bad) is False


def test_encrypted_pdf_not_extractable(tmp_path):
    assert pdf_is_extractable(_encrypted_pdf(tmp_path / "enc.pdf")) is False


def test_missing_path_not_extractable(tmp_path):
    assert pdf_is_extractable(tmp_path / "nope.pdf") is False
```

- [ ] **Step 3: Rodar o teste e ver falhar**

Run: `source .venv/bin/activate && pytest tests/extraction/test_pdf_validity.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.extraction.pdf_validity'`.

- [ ] **Step 4: Implementar `pdf_validity.py`**

Criar `scripts/extraction/pdf_validity.py`:
```python
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
```

- [ ] **Step 5: Rodar o teste e ver passar**

Run: `source .venv/bin/activate && pytest tests/extraction/test_pdf_validity.py -v`
Expected: PASS — 4 passed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml scripts/extraction/pdf_validity.py tests/extraction/test_pdf_validity.py
git commit -m "feat(rc3): pdf_is_extractable (pypdf) — PDF inválido/cifrado → False

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `build_user_content` cai para abstract em PDF não-extraível

**Files:**
- Modify: `scripts/extraction/extract_llm.py:18-21` (imports) e `:39-57` (`build_user_content`)
- Test: `tests/extraction/test_extract_llm.py` (acrescentar; manter os existentes)

Contexto: hoje `build_user_content` (linhas 39-57) monta o bloco `document` se `text_source=="pdf"` e `p.is_file()`. Precisa também exigir `pdf_is_extractable(p)`.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar ao fim de `tests/extraction/test_extract_llm.py` (imports `pd`, `extract_llm`, `tmp_path` já usados no arquivo):
```python
from pypdf import PdfWriter

from scripts.extraction import extract_llm as _E


def _make_valid_pdf(p):
    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    with open(p, "wb") as f:
        w.write(f)
    return p


def test_build_user_content_pdf_invalido_cai_para_abstract(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"<html>paywall</html>")
    row = {"text_source": "pdf", "pdf_path": str(bad), "title": "T",
           "abstract": "resumo", "authors": "A", "year": 2024,
           "venue": "V", "id": "s-001"}
    content = _E.build_user_content(row)
    assert len(content) == 1
    assert content[0]["type"] == "text"
    assert "apenas resumo" in content[0]["text"]


def test_build_user_content_pdf_valido_usa_document(tmp_path):
    good = _make_valid_pdf(tmp_path / "ok.pdf")
    row = {"text_source": "pdf", "pdf_path": str(good), "title": "T",
           "abstract": "resumo", "authors": "A", "year": 2024,
           "venue": "V", "id": "s-002"}
    content = _E.build_user_content(row)
    assert content[0]["type"] == "document"
    assert content[0]["source"]["media_type"] == "application/pdf"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `source .venv/bin/activate && pytest tests/extraction/test_extract_llm.py -k "pdf_invalido or pdf_valido_usa_document" -v`
Expected: FAIL — `test_build_user_content_pdf_invalido_cai_para_abstract` retorna bloco `document` (len 2), assertion falha.

- [ ] **Step 3: Implementar a mudança**

Em `scripts/extraction/extract_llm.py`, no bloco de imports (após a linha 18 `from scripts.extraction.llm_extract_prompt import build_extract_system_block`), acrescentar:
```python
from scripts.extraction.pdf_validity import pdf_is_extractable
```
E em `build_user_content`, trocar a condição:
```python
        if p.is_file():
```
por:
```python
        if p.is_file() and pdf_is_extractable(p):
```
(nenhuma outra linha muda; PDF não-extraível segue para o `return` do caminho abstract).

- [ ] **Step 4: Rodar e ver passar (inclui regressão do arquivo)**

Run: `source .venv/bin/activate && pytest tests/extraction/test_extract_llm.py -v`
Expected: PASS — todos (os novos 2 + os pré-existentes inalterados).

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction/extract_llm.py tests/extraction/test_extract_llm.py
git commit -m "feat(rc3): build_user_content cai para abstract em PDF não-extraível

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `screen_with_model` não cacheia `None` (RC2 — núcleo)

**Files:**
- Modify: `scripts/screening/llm/batch_client.py:186-196`
- Test: `tests/screening/test_batch_client.py` (acrescentar; manter os existentes)

Contexto — código atual (linhas 186-196):
```python
    if pending:
        raw_by_cid = submit_fn(pending)
        for req in pending:
            cid = req["custom_id"]
            cache[cid] = (parse_fn or parse_response)(raw_by_cid.get(cid, ""))
        _save_cache(cache_path, cache)
        print(f"[{label}] {n_pending} processados e gravados em cache")
    else:
        print(f"[{label}] nada a fazer → pulando (0 chamadas, $0)")

    return [cache[custom_id(cache_key(row))] for _, row in df.iterrows()]
```

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `tests/screening/test_batch_client.py` (o arquivo já importa `pandas as pd` e de `scripts.screening.llm.batch_client`; usar os mesmos nomes — confirmar no topo do arquivo e reusar imports existentes):
```python
def test_errored_none_nao_cacheia_e_reprocessa(tmp_path):
    from scripts.screening.llm import batch_client as BC
    df = pd.DataFrame([
        {"doi": "10.1/a", "title": "A", "year": 2020, "abstract": "x"},
        {"doi": "10.1/b", "title": "B", "year": 2021, "abstract": "y"},
    ])
    cache = tmp_path / "c.json"
    calls = []

    def submit_ok_none(reqs):
        calls.append([r["custom_id"] for r in reqs])
        # 1º cid responde JSON válido; 2º cid = API-errored (None)
        out = {}
        for i, r in enumerate(reqs):
            out[r["custom_id"]] = (
                '{"decisao":"incluir","confianca":0.9}' if i == 0 else None
            )
        return out

    res1 = BC.screen_with_model(df, model="claude-haiku-4-5-20251001",
                                cache_path=cache, submit_fn=submit_ok_none)
    assert res1[0]["decisao"] == "incluir"
    # o cid errored NÃO foi cacheado: 2ª chamada reprocessa só ele
    res2 = BC.screen_with_model(df, model="claude-haiku-4-5-20251001",
                                cache_path=cache, submit_fn=submit_ok_none)
    assert len(calls) == 2
    assert len(calls[1]) == 1  # só o pendente (o errored) reenviado


def test_resposta_vazia_cacheia_fallback_terminal(tmp_path):
    from scripts.screening.llm import batch_client as BC
    df = pd.DataFrame([{"doi": "10.1/z", "title": "Z", "year": 2022,
                        "abstract": "w"}])
    cache = tmp_path / "c.json"
    calls = []

    def submit_empty(reqs):
        calls.append(1)
        return {r["custom_id"]: "" for r in reqs}  # API respondeu vazio

    r1 = BC.screen_with_model(df, model="claude-haiku-4-5-20251001",
                              cache_path=cache, submit_fn=submit_empty)
    assert r1[0]["justificativa"] == "parse_fail"  # fallback
    # "" é resposta da API → cacheado TERMINAL: 2ª chamada não re-submete
    BC.screen_with_model(df, model="claude-haiku-4-5-20251001",
                         cache_path=cache, submit_fn=submit_empty)
    assert len(calls) == 1


def test_regressao_mock_str_inalterado(tmp_path):
    from scripts.screening.llm import batch_client as BC
    df = pd.DataFrame([{"doi": "10.1/r", "title": "R", "year": 2019,
                        "abstract": "v"}])
    cache = tmp_path / "c.json"

    def submit_str(reqs):
        return {r["custom_id"]: '{"decisao":"excluir","confianca":0.7,'
                                '"criterio":"C1"}' for r in reqs}

    out = BC.screen_with_model(df, model="claude-haiku-4-5-20251001",
                               cache_path=cache, submit_fn=submit_str)
    assert out[0]["decisao"] == "excluir"
    assert out[0]["criterio"] == "C1"
    assert abs(out[0]["confianca"] - 0.7) < 1e-9
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -k "errored_none or vazia_cacheia or regressao_mock_str" -v`
Expected: FAIL — `test_errored_none_nao_cacheia_e_reprocessa` quebra: hoje `None` é cacheado via `parse_response(None→"")` e o `return` faz `cache[cid]` (KeyError não; mas o cid fica cacheado e a 2ª chamada não reprocessa → `len(calls[1])` seria 0/`calls` len 1).

- [ ] **Step 3: Implementar a mudança**

Em `scripts/screening/llm/batch_client.py`, substituir as linhas 186-196 por:
```python
    if pending:
        raw_by_cid = submit_fn(pending)
        n_skipped = 0
        for req in pending:
            cid = req["custom_id"]
            v = raw_by_cid.get(cid)            # None = API-errored / ausente
            if v is None:
                n_skipped += 1
                continue                       # NÃO cacheia → re-rodada reprocessa
            cache[cid] = (parse_fn or parse_response)(v)
        _save_cache(cache_path, cache)
        print(f"[{label}] {n_pending - n_skipped} processados e gravados em cache")
        if n_skipped:
            print(
                f"[{label}] {n_skipped} requests erraram na API e NÃO foram "
                f"cacheados — re-rode após resolver a causa (ex.: crédito)"
            )
    else:
        print(f"[{label}] nada a fazer → pulando (0 chamadas, $0)")

    _miss = (parse_fn or parse_response)("")
    return [
        cache.get(custom_id(cache_key(row)), _miss)
        for _, row in df.iterrows()
    ]
```

- [ ] **Step 4: Rodar e ver passar (inclui suite inteira do batch_client)**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -v`
Expected: PASS — os 3 novos + todos os pré-existentes (regressão screening/arbitragem inalterada, pois mocks devolvem `str`, nunca `None`).

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/llm/batch_client.py tests/screening/test_batch_client.py
git commit -m "fix(rc2): screen_with_model não cacheia request API-errored (None)

None=errado → não cacheia (re-rodada reprocessa); resposta da API (mesmo
vazia) → fallback terminal cacheado. Fallback em memória no retorno preserva
zip/asserts. Retrocompatível: mock str nunca produz None.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `anthropic_submit_fn` devolve `None` p/ não-`succeeded` (RC2 — produtor)

**Files:**
- Modify: `scripts/screening/llm/batch_client.py:258-275`
- Test: `tests/screening/test_batch_client.py` (acrescentar)

Contexto — código atual (258-275):
```python
        out: dict[str, str] = {}
        n_ok = 0
        for entry in client.messages.batches.results(batch.id):
            if getattr(entry.result, "type", None) == "succeeded":
                blocks = entry.result.message.content
                out[entry.custom_id] = next(
                    (b.text for b in blocks if getattr(b, "type", None) == "text"),
                    "",
                )
                n_ok += 1
            else:
                out[entry.custom_id] = ""  # → parse_fail → duvida/0
        print(
            f"  [{_label(model)}] coletado: {n_ok} sucesso, "
            f"{total - n_ok} sem resposta (→ duvida/0)",
            flush=True,
        )
        return out
```

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar ao fim de `tests/screening/test_batch_client.py`:
```python
def test_anthropic_submit_fn_errored_vira_none():
    import types
    from scripts.screening.llm import batch_client as BC

    def mk(cid, kind, text=""):
        r = types.SimpleNamespace()
        r.custom_id = cid
        if kind == "succeeded":
            blk = types.SimpleNamespace(type="text", text=text)
            r.result = types.SimpleNamespace(
                type="succeeded",
                message=types.SimpleNamespace(content=[blk]))
        else:
            r.result = types.SimpleNamespace(type="errored", error=None)
        return r

    class FakeBatch:
        id = "msgbatch_x"
        processing_status = "ended"
        request_counts = types.SimpleNamespace(
            succeeded=1, errored=1, processing=0, canceled=0, expired=0)

    class FakeClient:
        class messages:
            class batches:
                @staticmethod
                def create(requests):
                    return FakeBatch()

                @staticmethod
                def retrieve(_id):
                    return FakeBatch()

                @staticmethod
                def results(_id):
                    return [mk("rOK", "succeeded", '{"decisao":"incluir"}'),
                            mk("rERR", "errored")]

    fn = BC.anthropic_submit_fn("claude-haiku-4-5-20251001",
                                client=FakeClient(), poll_interval=0)
    out = fn([{"custom_id": "rOK"}, {"custom_id": "rERR"}])
    assert out["rOK"] == '{"decisao":"incluir"}'
    assert out["rERR"] is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -k anthropic_submit_fn_errored -v`
Expected: FAIL — `assert out["rERR"] is None` falha (hoje vale `""`).

- [ ] **Step 3: Implementar a mudança**

Substituir as linhas 258-275 por:
```python
        out: dict[str, str | None] = {}
        n_ok = n_err = n_empty = 0
        for entry in client.messages.batches.results(batch.id):
            if getattr(entry.result, "type", None) == "succeeded":
                blocks = entry.result.message.content
                txt = next(
                    (b.text for b in blocks if getattr(b, "type", None) == "text"),
                    "",
                )
                out[entry.custom_id] = txt
                if txt:
                    n_ok += 1
                else:
                    n_empty += 1
            else:
                out[entry.custom_id] = None  # API-errored → não cacheia (RC2)
                n_err += 1
        print(
            f"  [{_label(model)}] coletado: {n_ok} sucesso, "
            f"{n_err} erro (não cacheados), {n_empty} sem texto",
            flush=True,
        )
        return out
```

- [ ] **Step 4: Rodar e ver passar**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -v`
Expected: PASS — novo teste + todos os anteriores.

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/llm/batch_client.py tests/screening/test_batch_client.py
git commit -m "fix(rc2): anthropic_submit_fn devolve None p/ request não-succeeded

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `migrate_failed_run.py` — migração one-off

**Files:**
- Create: `scripts/extraction/migrate_failed_run.py`
- Test: `tests/extraction/test_migrate_failed_run.py`

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/extraction/test_migrate_failed_run.py`:
```python
import json
import types

import pandas as pd

from scripts.extraction import migrate_failed_run as M


def _fake_client(entries):
    def mk(cid, kind, msg=""):
        r = types.SimpleNamespace()
        r.custom_id = cid
        if kind == "succeeded":
            r.result = types.SimpleNamespace(type="succeeded")
        else:
            inner = types.SimpleNamespace(message=msg)
            r.result = types.SimpleNamespace(
                type="errored",
                error=types.SimpleNamespace(error=inner))
        return r

    class C:
        class messages:
            class batches:
                @staticmethod
                def results(_bid):
                    return [mk(*e) for e in entries]
    return C()


def _setup(tmp_path):
    cache = {"rCRED": {"x": 1}, "rPDFBAD": {"x": 2},
             "rOK": {"x": 3}, "rGENUINO": {"x": 4}}
    cp = tmp_path / "cache.json"
    cp.write_text(json.dumps(cache), encoding="utf-8")
    man = pd.DataFrame([
        {"id": "s-1", "review_id": "rCRED", "doi": "d1", "title": "t1",
         "text_source": "abstract", "fonte": "—", "pdf_path": "",
         "status": "nao_oa"},
        {"id": "s-2", "review_id": "rPDFBAD", "doi": "d2", "title": "t2",
         "text_source": "pdf", "fonte": "oa", "pdf_path": "/x.pdf",
         "status": "oa"},
        {"id": "s-3", "review_id": "rOK", "doi": "d3", "title": "t3",
         "text_source": "pdf", "fonte": "oa", "pdf_path": "/y.pdf",
         "status": "oa"},
    ])
    mp = tmp_path / "man.csv"
    man.to_csv(mp, index=False)
    return cp, mp


def test_classify():
    assert M.classify("Your credit balance is too low") == "credito"
    assert M.classify("The PDF specified is password protected.") == "pdf_protegido"
    assert M.classify("The PDF specified was not valid.") == "pdf_invalido"
    assert M.classify("weird") == "outro"


def test_dry_run_nao_altera(tmp_path):
    cp, mp = _setup(tmp_path)
    before_c = cp.read_text(); before_m = mp.read_text()
    cli = _fake_client([
        ("rCRED", "errored", "Your credit balance is too low"),
        ("rPDFBAD", "errored", "The PDF specified was not valid."),
        ("rGENUINO", "succeeded"),
    ])
    rep = M.run(cli, "b", cp, mp, dry_run=True)
    assert cp.read_text() == before_c
    assert mp.read_text() == before_m
    assert rep["cache_removed"] == 2          # rCRED + rPDFBAD presentes
    assert rep["manifest_changed"] == 1       # só rPDFBAD (era pdf)
    assert rep["pdf_before"] == 2 and rep["pdf_after"] == 1


def test_apply_e_idempotente(tmp_path):
    cp, mp = _setup(tmp_path)
    entries = [
        ("rCRED", "errored", "Your credit balance is too low"),
        ("rPDFBAD", "errored", "The PDF specified was not valid."),
        ("rGENUINO", "succeeded"),
    ]
    M.run(_fake_client(entries), "b", cp, mp, dry_run=False)
    cache = json.loads(cp.read_text())
    assert "rCRED" not in cache and "rPDFBAD" not in cache
    assert "rOK" in cache and "rGENUINO" in cache  # genuíno preservado
    man = pd.read_csv(mp, keep_default_na=False)
    row = man[man["review_id"] == "rPDFBAD"].iloc[0]
    assert row["text_source"] == "abstract" and row["status"] == "pdf_invalido"
    # idempotente: 2ª rodada = no-op
    rep2 = M.run(_fake_client(entries), "b", cp, mp, dry_run=False)
    assert rep2["cache_removed"] == 0 and rep2["manifest_changed"] == 0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `source .venv/bin/activate && pytest tests/extraction/test_migrate_failed_run.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.extraction.migrate_failed_run'`.

- [ ] **Step 3: Implementar `migrate_failed_run.py`**

Criar `scripts/extraction/migrate_failed_run.py`:
```python
"""One-off: limpa o cache e corrige o manifesto após a 1ª rodada real de
extract-llm (batch 791 ok / 61 errored — ver
docs/superpowers/specs/2026-05-17-fix-extract-llm-cache-pdf-robustez-design.md).

NÃO faz extração (sem custo de modelo): só lê os resultados do batch (retidos
~29 dias) e ajusta arquivos locais. Idempotente — rodar 2× = no-op.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

DEFAULT_BATCH = "msgbatch_01Bye7bKuBLg9xjQ3pt3W9Er"
_BAD_PDF = {"pdf_protegido", "pdf_invalido"}


def _err_message(result) -> str:
    err = getattr(result, "error", None)
    if err is None:
        return ""
    inner = getattr(err, "error", err)
    return str(getattr(inner, "message", "") or "")


def classify(msg: str) -> str:
    m = msg.lower()
    if "credit balance" in m:
        return "credito"
    if "password protected" in m:
        return "pdf_protegido"
    if "not valid" in m:
        return "pdf_invalido"
    return "outro"


def collect_errored(client, batch_id: str) -> dict[str, str]:
    """{custom_id: categoria} p/ entradas com result.type != 'succeeded'."""
    out: dict[str, str] = {}
    for e in client.messages.batches.results(batch_id):
        if getattr(e.result, "type", None) != "succeeded":
            out[e.custom_id] = classify(_err_message(e.result))
    return out


def run(client, batch_id: str, cache_path: Path, manifest_path: Path,
        dry_run: bool) -> dict:
    errored = collect_errored(client, batch_id)
    cache = (json.loads(Path(cache_path).read_text(encoding="utf-8"))
             if Path(cache_path).exists() else {})
    to_remove = [cid for cid in errored if cid in cache]

    man = pd.read_csv(manifest_path, encoding="utf-8", keep_default_na=False)
    pdf_before = int((man["text_source"] == "pdf").sum())
    changed = 0
    for cid, cat in errored.items():
        if cat not in _BAD_PDF:
            continue
        mask = man["review_id"] == cid
        if mask.any() and (man.loc[mask, "text_source"] == "pdf").any():
            man.loc[mask, "text_source"] = "abstract"
            man.loc[mask, "status"] = cat
            changed += int(mask.sum())
    pdf_after = int((man["text_source"] == "pdf").sum())

    report = {
        "errored_total": len(errored),
        "cache_removed": len(to_remove),
        "cache_kept": len(cache) - len(to_remove),
        "manifest_changed": changed,
        "pdf_before": pdf_before,
        "pdf_after": pdf_after,
        "by_category": {c: sum(1 for v in errored.values() if v == c)
                        for c in sorted(set(errored.values()))},
    }
    if not dry_run:
        for cid in to_remove:
            del cache[cid]
        Path(cache_path).write_text(
            json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        man.to_csv(manifest_path, index=False, encoding="utf-8")
    return report


def _cli(argv) -> int:
    p = argparse.ArgumentParser(description="Migração pós-rodada extract-llm.")
    p.add_argument("--batch-id", default=DEFAULT_BATCH)
    p.add_argument("--cache", type=Path,
                   default=Path("data/processed/06_cache_extract.json"))
    p.add_argument("--manifest", type=Path,
                   default=Path("data/processed/04_fulltext_manifest.csv"))
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    from dotenv import load_dotenv
    load_dotenv()
    from anthropic import Anthropic
    rep = run(Anthropic(), a.batch_id, a.cache, a.manifest, a.dry_run)
    tag = "[DRY-RUN] " if a.dry_run else ""
    print(f"{tag}errored={rep['errored_total']} categorias={rep['by_category']}")
    print(f"{tag}cache: removidos={rep['cache_removed']} "
          f"mantidos={rep['cache_kept']}")
    print(f"{tag}manifesto: linhas alteradas={rep['manifest_changed']} | "
          f"text_source=pdf {rep['pdf_before']} → {rep['pdf_after']}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `source .venv/bin/activate && pytest tests/extraction/test_migrate_failed_run.py -v`
Expected: PASS — 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction/migrate_failed_run.py tests/extraction/test_migrate_failed_run.py
git commit -m "feat: migrate_failed_run — limpa cache + corrige manifesto (one-off)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Migração real + nota de protocolo + verificação final

**Files:**
- Modify: `protocols/slr_protocol.md` (§8 nota interina; §11 limitações)
- Data (alterados pela migração real): `data/processed/06_cache_extract.json`, `data/processed/04_fulltext_manifest.csv`

- [ ] **Step 1: Migração real — dry-run primeiro**

```bash
source /home/acacio/dev/pessoal/ai-impact/.venv/bin/activate && \
python -m scripts.extraction.migrate_failed_run --dry-run
```
Expected: `[DRY-RUN] errored=61 categorias={'credito': 48, 'pdf_invalido': 11, 'pdf_protegido': 2}` · `cache: removidos=61 mantidos=791` · `manifesto: linhas alteradas=13 | text_source=pdf 134 → 121`. Nenhum arquivo alterado (confirmar com `git status --porcelain data/processed/04_fulltext_manifest.csv` → vazio).
Se os números divergirem (ex.: resultados do batch expiraram → `errored=0`), **PARAR** e reportar como BLOCKED (a janela de ~29 dias pode ter passado); não aplicar.

- [ ] **Step 2: Aplicar a migração**

```bash
source .venv/bin/activate && python -m scripts.extraction.migrate_failed_run
```
Expected: mesmos números, sem `[DRY-RUN]`. Verificar:
```bash
source .venv/bin/activate && python -c "
import json, pandas as pd
c=json.load(open('data/processed/06_cache_extract.json'))
m=pd.read_csv('data/processed/04_fulltext_manifest.csv', keep_default_na=False)
print('cache entries', len(c))
print('manifest text_source', m['text_source'].value_counts().to_dict())
print('status pdf_*', m[m['status'].str.startswith('pdf_')]['status'].value_counts().to_dict())
"
```
Expected: `cache entries 791`; manifest `{'abstract': 731, 'pdf': 121}`; status `{'pdf_invalido': 11, 'pdf_protegido': 2}`.

- [ ] **Step 3: Rodar a migração de novo (provar idempotência no dado real)**

```bash
source .venv/bin/activate && python -m scripts.extraction.migrate_failed_run --dry-run
```
Expected: `cache: removidos=0 mantidos=791` · `manifesto: linhas alteradas=0 | text_source=pdf 121 → 121` (no-op).

- [ ] **Step 4: Nota honesta no protocolo**

Em `protocols/slr_protocol.md`, na **Nota interina (2026-05-17, Plano 4b-i)** da §8, acrescentar ao fim da nota:
```markdown

**Incidente da 1ª rodada (2026-05-17) e correção.** A 1ª execução real teve
62/852 sem extração: 48 por esgotamento de crédito da API no meio do lote, 13
por PDF inválido/protegido baixado na aquisição (4a) e 1 por JSON malformado.
Diagnóstico por evidência (resultados do *batch*, retidos ~29 dias). Corrigiu-se
o defeito que cacheava respostas-de-erro como resultado terminal (o cache agora
só persiste respostas efetivamente devolvidas pela API; requests com erro são
reprocessados numa nova execução) e passou-se a validar o PDF antes do envio
(inválido/protegido → nível de resumo, registrado no manifesto). A cobertura
*full-text* real é 121/852 (14,2%), não 134/852. A reextração dos 61 depende de
recarga de crédito e está pendente; enquanto não ocorrer, esses registros
permanecem sem extração e são declarados como tal.
```
E em §11 (Limitações), acrescentar um item:
```markdown
- Reextração pendente de 61 registros da 1ª rodada (48 por crédito esgotado,
  13 por PDF não-extraível): documentada e sanável por nova execução
  idempotente após recarga; cobertura full-text efetiva 14,2%.
```

- [ ] **Step 5: Suite completa + commit**

```bash
source .venv/bin/activate && pytest -q
```
Expected: tudo verde (era 192; agora 192 + novos de pdf_validity/extract_llm/batch_client/migrate).
```bash
git add protocols/slr_protocol.md data/processed/04_fulltext_manifest.csv data/processed/06_cache_extract.json
git commit -m "chore(4b-i): migração real (cache -61, manifesto -13 PDF) + nota protocolo §8/§11

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```
Observação: se `data/processed/06_cache_extract.json` estiver no `.gitignore`, **não** forçar add — apenas commitar `protocols/slr_protocol.md` e `04_fulltext_manifest.csv`; o cache local já fica corrigido em disco. Verificar com `git check-ignore data/processed/06_cache_extract.json` antes do add.

---

## Notas de verificação (self-review do plano)

- **Cobertura da spec:** RC2 produtor (Task 4) + consumidor (Task 3); RC3 (Task 1 `pdf_is_extractable` + Task 2 `build_user_content`); migração precisa via batch + correção manifesto/estatística (Task 5 código, Task 6 execução real); dependência pypdf (Task 1); nota protocolo §8/§11 (Task 6); testes em todas. Q1 (só API-errored reprocessa; "" terminal) coberto pelos testes da Task 3. Q3 (preserva o 1 genuíno) coberto pelo `rGENUINO` na Task 5.
- **Retrocompatibilidade:** Task 3 inclui `test_regressao_mock_str_inalterado`; suite inteira roda no Step 4 da Task 3 e no Step 5 da Task 6.
- **Consistência de tipos:** `pdf_is_extractable(path)->bool` (Task 1) usado igual na Task 2; `run(client, batch_id, cache_path, manifest_path, dry_run)->dict` e chaves do report idênticas entre Task 5 (testes) e implementação; sentinela `None` produzido na Task 4 e consumido na Task 3.
- **Ordem:** 1→2 (pdf), 3→4 (RC2; Task 3 testa via submit_fn injetado, não depende da Task 4), 5 (usa contrato estável), 6 (execução real depende de 1-5 mergeados/limpos e dos resultados do batch ainda retidos).
