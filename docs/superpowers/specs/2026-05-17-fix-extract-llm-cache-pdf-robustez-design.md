# Design — `extract-llm` robusto e re-rodável (fix RC2 + RC3)

**Data:** 2026-05-17
**Autor:** Acacio (via brainstorming superpowers)
**Branch:** `fix-extract-llm-cache-pdf`
**Origem:** diagnóstico sistemático da 1ª rodada real de `make extract-llm`.

---

## 1. Problema (evidência, não suposição)

A 1ª rodada real de `make extract-llm` (Sonnet 4.6, 2026-05-17, batch
`msgbatch_01Bye7bKuBLg9xjQ3pt3W9Er`: **791 ok / 61 errored** = 852) produziu
`data/processed/06_extraction.csv` com 852 linhas, mas **62 com
`nota_extracao=parse_fail`** (extração vazia, incluídos conservadoramente).

Diagnóstico por evidência (resultados do batch, retidos ~29 dias pela
Anthropic) — todos os 61 são `invalid_request_error`, em 3 sub-causas:

| Causa | N | Fonte |
|---|---|---|
| **SEM_CRÉDITO** — saldo Anthropic zerou no meio do batch | 48 | 41 abstract + 7 pdf |
| **PDF_INVÁLIDO** — arquivo baixado (4a) não é PDF válido (provável HTML/paywall salvo como `.pdf`) | 11 | pdf |
| **PDF_PROTEGIDO** — PDF com senha | 2 | pdf |
| parse genuíno (API respondeu, JSON não parseou) | 1 | — |
| **Total parse_fail** | **62** | |

Causas-raiz:

- **RC1 (operacional, 48):** conta sem crédito. Recuperável: recarregar +
  re-rodar. Decisão do usuário em 2026-05-17: **não recarregar agora** →
  re-rodada adiada.
- **RC2 (defeito de código — central):** `screen_with_model`
  (`scripts/screening/llm/batch_client.py:190`) faz
  `cache[cid] = parse_fn(raw_by_cid.get(cid, ""))` **incondicionalmente**.
  Request que erra na API → `raw=""` → grava o **fallback `parse_fail`** no
  cache. `build_requests:123` pula qualquer `cid in cached`. ⇒ requests que
  erraram **nunca são reprocessados** numa re-rodada; o cache idempotente não
  distingue "sucesso" de "errou, precisa retry". Falha transitória vira
  degradação silenciosa e permanente do dataset. Afeta também
  screening/arbitragem (código compartilhado, corpus já consolidado — não
  regredir).
- **RC3 (qualidade de dados, 13):** `fulltext_acquire` (4a) baixou 13 arquivos
  inválidos/protegidos; `build_user_content` os manda como bloco PDF base64 →
  erram para sempre como PDF.

## 2. Decisões de design (definidas no brainstorming)

- **Q1 — contrato do cache:** só **API-errored** reprocessa. Resposta que a
  API **devolveu** mas não parseia → fallback **terminal** cacheado (sem
  re-rodada eterna num JSON cronicamente quebrado).
- **Q2 — RC3:** validar o PDF e cair para `abstract`; **corrigir o manifesto
  04 e a estatística** de cobertura full-text (auditável p/ banca).
- **Q3 — migração do cache:** **precisa, via resultados do batch, agora**
  (enquanto retidos ~29 dias) — remove exatamente os 61 errored; o 1 genuíno
  fica (terminal, conforme Q1).
- **Abordagem A** — sentinela `None` no contrato do `submit_fn` (mínima,
  retrocompatível, ataca a raiz num único ponto de cada lado).
- **`pypdf`** adicionado como dependência para `pdf_is_extractable`
  (detecção confiável de inválido/cifrado; declarar no `pyproject.toml`).

## 3. Arquitetura (unidades pequenas, bordas claras)

| Unidade | Responsabilidade | Depende de |
|---|---|---|
| `anthropic_submit_fn` (mod.) | `None` p/ cid não-`succeeded`; texto p/ sucesso; log conta `n_ok`/`n_err`/`n_empty` | API Anthropic |
| `screen_with_model` (mod.) | não cacheia `None`; fallback **em memória** (não persistido) p/ não quebrar `zip`/asserts; resumo alto de "N errored não cacheados — re-rode" | `submit_fn` |
| `pdf_is_extractable(path)->bool` (novo) | `False` se `pypdf` falhar (inválido) ou `is_encrypted` (protegido); senão `True` | `pypdf` |
| `build_user_content` (mod.) | PDF não-extraível → bloco `abstract` em vez de `document` | `pdf_is_extractable` |
| `migrate_failed_run.py` (novo, one-off) | via resultados do batch: remove os 61 errored do cache; corrige manifesto (13 PDFs→abstract+status); relatório | resultados do batch |
| descritivas/PRISMA | cobertura full-text recomputada do manifesto corrigido | manifesto |

## 4. Comportamento detalhado

### RC2 — `batch_client.py`

`anthropic_submit_fn` (laço de `results()`):
- `entry.result.type == "succeeded"` → `out[cid] = <texto do 1º bloco text, ou "">`
- caso contrário → `out[cid] = None` (hoje: `""`)
- log: `coletado: {n_ok} sucesso, {n_err} erro (não cacheados), {n_empty} sem texto`

`screen_with_model` (laço de gravação do cache):
```
for req in pending:
    cid = req["custom_id"]
    v = raw_by_cid.get(cid)            # None = API-errored / ausente
    if v is None:
        n_skipped += 1
        continue                       # NÃO cacheia → re-rodada reprocessa
    cache[cid] = (parse_fn or parse_response)(v)   # v="" → fallback TERMINAL
_save_cache(cache_path, cache)
if n_skipped:
    print(f"[{label}] {n_skipped} requests erraram na API e NÃO foram "
          f"cacheados — re-rode após resolver a causa (ex.: crédito)")
```
Retorno final: cid ausente do cache → fallback **em memória** (mesma estrutura
do `parse_fn` p/ texto vazio) para preservar ordem, `zip` e
`assert len(res)==len(df)` — sem persistir no cache.

**Retrocompat:** `mock=True` e mocks `dict[str,str]` nunca produzem `None` →
caminho idêntico ao atual. Coberto por teste de regressão.

### RC3 — `extract_llm.py` + `pdf_is_extractable`

`pdf_is_extractable(path: Path) -> bool`: tenta `pypdf.PdfReader(str(path))`;
retorna `False` em qualquer exceção (PDF inválido/corrompido) ou se
`reader.is_encrypted`; `True` caso contrário. Arquivo inexistente → `False`.

`build_user_content`: o ramo `text_source == "pdf"` só monta o bloco
`document` se `p.is_file() and pdf_is_extractable(p)`; senão segue para o
mesmo `return` do caminho abstract (texto). Nenhuma outra mudança.

### Migração — `scripts/extraction/migrate_failed_run.py`

CLI: `--batch-id` (default `msgbatch_01Bye7bKuBLg9xjQ3pt3W9Er`),
`--cache` (default `data/processed/06_cache_extract.json`),
`--manifest` (default `data/processed/04_fulltext_manifest.csv`),
`--dry-run`. Idempotente.

1. `client.messages.batches.results(batch_id)`; classifica cids `errored`
   (motivo via `error.message`: credit / password / not valid / outro).
2. Mapeia cid→`review_id` (= `custom_id(cache_key(row))` do corpus∩manifesto)
   e remove do cache exatamente os cids errored presentes. O 1 parse-genuíno
   (cid `succeeded`) **não** é tocado.
3. Manifesto: linhas dos 13 (PDF_INVÁLIDO/PDF_PROTEGIDO) →
   `text_source="abstract"`, `status="pdf_invalido"` ou `"pdf_protegido"`.
4. Relatório: nº removidos do cache, linhas de manifesto alteradas, cobertura
   full-text antes/depois (134→~121 de 852). `--dry-run` só imprime.

### Estado pós-fix (sem crédito) e adiado

- **Agora:** cache limpo dos 61; manifesto+estatística corretos;
  `06_extraction.csv` **permanece** com os 62 parse_fail (não há como
  re-extrair sem crédito) — documentado.
- **Adiado (gatilho: crédito + `make extract-llm`):** re-rodada idempotente
  reprocessa só os 61 (48 sem-crédito normal; 13 PDF-ruim via abstract) e
  reescreve `06_extraction.csv`.
- **Protocolo:** §8 (nota interina) e §11 (limitações) ganham nota honesta do
  incidente, do defeito corrigido e do estado pendente.

## 5. Testes (TDD)

- `screen_with_model`: (a) `submit_fn` devolve `None` p/ um cid → não cacheia;
  2ª chamada re-submete esse cid. (b) `""` → cacheia fallback terminal; 2ª
  chamada **não** re-submete. (c) regressão: screening/arbitragem com mock
  `dict[str,str]` → resultado byte-idêntico ao atual.
- `anthropic_submit_fn`: cliente fake com 1 `errored` + 1 `succeeded` →
  `{cid_err: None, cid_ok: "texto"}`; log conta certo.
- `pdf_is_extractable`: PDF mínimo válido→`True`; bytes não-`%PDF`→`False`;
  PDF cifrado→`False`; caminho inexistente→`False`.
- `build_user_content`: `text_source=pdf` com arquivo inválido → bloco de
  texto (abstract), não `document`; com PDF válido → `document` (inalterado).
- `migrate_failed_run`: cliente fake; `--dry-run` não altera arquivos; aplicar
  remove exatamente os errored, preserva o `succeeded`, corrige manifesto;
  rodar 2× = no-op (idempotente).
- Suite cheia continua verde (era 192) + novos testes.

## 6. Escopo

**Inclui:** RC2 (contrato do cache), RC3 (validade de PDF + correção
manifesto/estatística), migração one-off, dependência `pypdf`, testes, nota de
protocolo §8/§11.

**Não inclui:** recarga de crédito e a re-rodada real (operacional, adiada
pelo usuário); re-aquisição dos 13 PDFs (Q2 rejeitou); Plano 4b-ii
(verificação humana/κ/PRISMA final) — separado, depende deste + da re-rodada.

## 7. Critérios de sucesso

1. `submit_fn` sinaliza `None` p/ API-errored; `screen_with_model` não cacheia
   `None`; uma 2ª chamada reprocessa exatamente os não-cacheados.
2. Screening/arbitragem inalterados (regressão verde, byte-idêntico no mock).
3. PDF inválido/protegido → caminho abstract automaticamente.
4. Migração (real, batch retido): cache perde exatamente os 61; manifesto
   reflete os 13; cobertura recomputada ~14,2%; idempotente.
5. Suite verde (192 + novos). Protocolo §8/§11 com nota honesta do incidente.
