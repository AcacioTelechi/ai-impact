# Plano 4a — Aquisição de texto completo — Design

**Data:** 2026-05-17
**Contexto:** O corpus pós-arbitragem tem **852 estudos** (`data/processed/03_incluidos_final.csv`). O Plano 4 (elegibilidade + extração por LLM com verificação humana amostral) foi decomposto em **4a (aquisição de texto)** e **4b (elegibilidade/extração/verificação)**. Este é o 4a.
**Entrada:** `data/processed/03_incluidos_final.csv` (852 registros; colunas do corpus incl. `doi`, `title`, `abstract`).
**Saída:** `data/processed/04_fulltext_manifest.csv` + PDFs em `data/raw/fulltext/{manual,oa}/` (gitignored).
**Marco previsto:** tag `v0.6.0-fulltext`.

---

## 1. Decisões fixadas no brainstorming (2026-05-17)

1. **Abordagem híbrida:** texto completo onde houver OA; abstract no resto. Cobertura declarada.
2. **Armazenar PDF nativo, sem extração de texto.** O 4b enviará o PDF diretamente à API do Claude (alta fidelidade: tabelas/figuras/equações; sem lib de PDF nem perda de layout). O 4a só resolve/baixa/cataloga.
3. **Fontes:** Unpaywall (OA automático, reusa o lookup existente) **+** pasta drop-in manual (PDFs institucionais fornecidos pelo usuário, nomeados `<id>.pdf`). Drop-in tem **prioridade** sobre Unpaywall. YAGNI: sem resolvers extras (RePEc/arXiv/NBER) nesta versão — se a cobertura vier baixa, adicionam-se depois (decisão guiada pelo manifesto).
4. **Sem novas dependências.** Contagem de páginas não é feita; o guard de tamanho usa o tamanho do arquivo (32 MB); o limite de ~100 páginas da API do Claude é tratado no 4b (erro da API → fallback abstract). Evita `pypdf` por ganho marginal.
5. **`id` estável `s-NNN`** derivado deterministicamente do `review_id` (= `custom_id(cache_key(row))`, mesma chave de screening/revisão/arbitragem). É a chave que liga 4a → 4b → extração.

## 2. Arquitetura

```
03_incluidos_final.csv (852)
   │  para cada registro (id estável s-NNN):
   ├─ data/raw/fulltext/manual/<id>.pdf existe?  → usa (fonte=manual, prioridade)
   ├─ senão e tem DOI: Unpaywall(DOI) → URL OA → baixa → oa/<id>.pdf (fonte=unpaywall)
   └─ senão (sem DOI / não-OA / falha / oversized): text_source=abstract
        └→ data/processed/04_fulltext_manifest.csv  +  resumo de cobertura no stdout
```

| Arquivo | Responsabilidade |
|---|---|
| `scripts/extraction/__init__.py` | pacote (se ainda não existir) |
| `scripts/extraction/fulltext_acquire.py` | **novo:** `assign_id`, `resolve`, `download_pdf`, `run`, `_cli` |
| `scripts/screening/fetch_fulltext.py` | **reusado:** `_unpaywall_lookup(doi, email)` importado tal qual (não modificar) |
| `scripts/screening/llm/batch_client.py` | **reusado:** `cache_key`, `custom_id` para o `id` estável |
| `data/raw/fulltext/manual/` | drop-in: PDFs institucionais `<id>.pdf` (gitignored) |
| `data/raw/fulltext/oa/` | PDFs OA baixados `<id>.pdf` (gitignored) |
| `data/processed/04_fulltext_manifest.csv` | manifesto (não versionado — `data/processed/` é gitignored; reprodutível pelo alvo) |
| `Makefile` | alvo `fulltext-acquire` |
| `.gitignore` | cobrir `data/raw/fulltext/` |

Convenções do repo: `from __future__ import annotations`; `_cli(argv)` + `if __name__ == "__main__": sys.exit(_cli(sys.argv[1:]))`; `print` p/ feedback; venv local (não `uv run`); pytest TDD; commits convencionais com `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

I/O de rede isolada atrás de callables injetáveis (mesmo padrão `submit_fn` do `batch_client`): `lookup_fn(doi,email)->url|None` e `download_fn(url,dest)->bool`. Em produção usam `_unpaywall_lookup` e um downloader `requests`+`tenacity`; em teste, fakes determinísticos (zero rede).

## 3. `id` estável

`assign_id(row) -> "s-NNN"`: ordena os 852 deterministicamente por `custom_id(cache_key(row))` e numera `s-001..s-852`. O mapeamento `id ↔ review_id ↔ doi` é registrado no manifesto. Garante a mesma chave em 4a/4b/extração mesmo que o CSV seja reordenado. (Reusa `cache_key`/`custom_id` de `scripts.screening.llm.batch_client` — DRY, idêntico ao resto do pipeline.)

## 4. Schema do manifesto

`data/processed/04_fulltext_manifest.csv` — 1 linha por registro (852), ordem por `id`:

| Coluna | Conteúdo |
|---|---|
| `id` | `s-NNN` estável |
| `review_id` | `custom_id(cache_key(row))` (liga ao corpus) |
| `doi` | DOI normalizado (vazio se ausente) |
| `title` | título (conferência) |
| `text_source` | `pdf` \| `abstract` |
| `fonte` | `manual` \| `unpaywall` \| `—` |
| `pdf_path` | caminho relativo do PDF (vazio se abstract) |
| `status` | `ok_manual` \| `ok_oa` \| `sem_doi` \| `nao_oa` \| `download_falhou` \| `oversized` |

## 5. Regras de resolução e fallback

Precedência por registro:
1. **`data/raw/fulltext/manual/<id>.pdf` existe** → `text_source=pdf`, `fonte=manual`, `status=ok_manual`. (Tem prioridade mesmo se houver OA — o usuário forneceu deliberadamente.)
2. Senão, **sem DOI** → `text_source=abstract`, `status=sem_doi`.
3. Senão, **Unpaywall(DOI)**: sem retorno OA → `abstract`/`nao_oa`; com URL → baixar.
   - download falha após retries → `abstract`/`download_falhou`.
   - PDF baixado > 32 MB → descarta o arquivo, `abstract`/`oversized`.
   - sucesso → `oa/<id>.pdf`, `text_source=pdf`, `fonte=unpaywall`, `status=ok_oa`.

`text_source=abstract` significa: nenhum PDF; o 4b usará a coluna `abstract` do corpus (confiança baixa, declarada no PRISMA/limitações do 4b).

**Idempotência/retomada:** se `manual/<id>.pdf` ou `oa/<id>.pdf` já existe, não re-baixa nem rebaixa — apenas recomputa a linha do manifesto a partir do que está em disco. Fluxo de uso em 2 passes: (1) roda 4a → manifesto mostra quais ficaram `abstract`; (2) usuário baixa institucionalmente os faltantes, salva como `manual/<id>.pdf`; (3) roda 4a de novo → incorpora (idempotente). Download grava em `<id>.pdf.part` e renomeia no sucesso (nunca PDF parcial).

**Cobertura no stdout:** `Aquisição: {n_pdf} pdf ({n_manual} manual / {n_oa} oa) | {n_abs} abstract — de {total}`.

## 6. Robustez, segurança, versionamento

- **Rede:** `tenacity` retry/backoff nos GETs (Unpaywall e download); timeout; Unpaywall polite pool via `--email`. Streaming do download com checagem de tamanho durante o stream (aborta cedo se exceder 32 MB).
- **Testes sem rede:** `lookup_fn`/`download_fn` injetáveis; fakes nos testes; zero rede; determinístico.
- **`.gitignore`:** adicionar `data/raw/fulltext/` (PDFs com copyright **não** vão para o git). O manifesto fica em `data/processed/` (já gitignored como o resto de processed) — não versionado; é reproduzível rodando o alvo.
- **Idempotente e seguro p/ re-rodar** quantas vezes for preciso (operação assistida por humano em 2 passes).

## 7. Testes (TDD, pytest)

- `assign_id`: determinístico, estável sob reordenação do CSV, formato `s-NNN`, único por registro, consistente com `custom_id(cache_key(row))`.
- `resolve` (com `lookup_fn`/`download_fn` fakes): precedência manual > unpaywall > abstract; cada `status` (ok_manual, ok_oa, sem_doi, nao_oa, download_falhou, oversized).
- `download_pdf`: grava `.part` e renomeia no sucesso; aborta/limpa em falha; nunca deixa parcial; respeita guard de 32 MB.
- `run` e2e com fakes: manifesto com schema/contagens corretos; cobertura impressa; idempotência (2ª rodada não re-baixa; drop-in adicionado entre rodadas é incorporado e muda `fonte`/`status`).
- Suíte total verde (≥ 155 + novos).

## 8. Integração

- **Makefile:** `fulltext-acquire` → `python -m scripts.extraction.fulltext_acquire --input $(DATA_PROC)/03_incluidos_final.csv --manifest $(DATA_PROC)/04_fulltext_manifest.csv --email $(EMAIL) --manual-dir data/raw/fulltext/manual --oa-dir data/raw/fulltext/oa`. **Não** entra em `screen`/`all` (operação assistida por humano, rede).
- **Protocolo §7 (Eligibility):** nota curta registrando o método de aquisição (Unpaywall OA + suplemento institucional manual; PDF nativo lido pelo LLM no 4b) e que a cobertura full-text será reportada no PRISMA/limitações. **O desvio metodológico maior (elegibilidade/extração por LLM em vez de manual) é declarado no 4b**, não aqui — 4a é só aquisição.
- **PRISMA:** a contagem de inacessíveis (`text_source=abstract` por `nao_oa`/`download_falhou`/`sem_doi`) alimenta a caixa "texto completo não recuperado" do PRISMA — consumida no 4b/plano de PRISMA, fora do escopo do 4a (só registra a intenção).

## 9. Fora de escopo (YAGNI)

- Extração de texto de PDF (decidido: PDF nativo no 4b).
- Resolvers além do Unpaywall (RePEc/arXiv/NBER/IZA) — adicionar depois só se a cobertura exigir.
- Contagem de páginas / `pypdf` — guard por tamanho de arquivo; limite de páginas tratado no 4b.
- Elegibilidade, extração, verificação humana, PRISMA — são o **4b**.
- Alterar `fetch_fulltext.py` — reusado sem modificação.

## 10. Critérios de sucesso

- `make fulltext-acquire` roda os 852, gera `04_fulltext_manifest.csv` com schema da §4 e imprime a cobertura.
- Drop-in tem prioridade; 2ª rodada é idempotente e incorpora PDFs adicionados manualmente.
- Nenhum PDF parcial/corrompido em falha; oversized/sem-doi/nao-oa caem para `abstract` com `status` correto.
- `data/raw/fulltext/` gitignored; nenhum PDF com copyright commitado.
- Suíte verde (≥ 155 + novos); protocolo §7 com a nota de aquisição; tag `v0.6.0-fulltext`.
