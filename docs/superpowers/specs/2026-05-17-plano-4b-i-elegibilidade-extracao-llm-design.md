# Plano 4b-i — Elegibilidade + extração por LLM — Design

**Data:** 2026-05-17
**Contexto:** Pós-4a. Corpus 852 (`03_incluidos_final.csv`) + `04_fulltext_manifest.csv` (134 `pdf` / 718 `abstract`, cobertura full-text 15,7%). O Plano 4b (elegibilidade+extração por LLM com verificação humana amostral) foi decomposto em **4b-i (extração LLM)** e **4b-ii (verificação humana + PRISMA)**. Este é o 4b-i.
**Entrada:** `data/processed/03_incluidos_final.csv` + `data/processed/04_fulltext_manifest.csv`.
**Saída:** `data/processed/06_extraction.csv` (37 colunas) + cache `06_cache_extract.json`.
**Marco previsto:** tag `v0.7.0-extracao`.

---

## 1. Decisões fixadas no brainstorming (2026-05-17)

1. **Uma passada combinada** por paper: o LLM lê o documento UMA vez e devolve `{elegivel, motivo_exclusao, confianca_extracao, extracao{33 campos}}`. Lê o documento só uma vez (PDFs são caros em tokens).
2. **Modelo: Claude Sonnet 4.6** (`claude-sonnet-4-6`) — instrumento único nos 852 (consistente, ~5× mais barato que Opus; a verificação humana amostral do 4b-ii valida).
3. **Híbrido por fonte:** `text_source=pdf` (134) → PDF lido nativamente pela API (bloco *document* base64); `text_source=abstract` (718) → texto do abstract+metadados.
4. **Abstract-only: best-effort nos 33 campos**, sinalizado. O LLM é instruído a responder `n/a`/vazio quando o resumo não sustenta o campo (não inventar). `confianca_extracao` + `text_source` marcam baixa confiança. Schema uniforme nos 852; a síntese (plano futuro) restringe análises profundas (rubrica/mecanismos) ao subconjunto full-text.
5. **Elegibilidade no full-text:** decidido no Plano 4 — o LLM exclui por E1–E5 antes de extrair; só os `elegivel=incluir` formam o corpus de síntese. (Etapa PRISMA Eligibility.)
6. **Verificação humana amostral** (elegibilidade + campos críticos, amostra estratificada, κ humano×LLM) e a **emenda formal do protocolo** (extração ≠ leitura 100% manual) são do **4b-ii**. O 4b-i carrega só uma nota interina.

## 2. Desvio do protocolo (declarado; emenda formal no 4b-ii)

O protocolo v1.1 §7 item 4 ainda diz "Eligibility (texto completo) — leitura completa, 100% manual" e §8 prevê extração manual. O 4b-i operacionaliza ambas por LLM (Sonnet 4.6). Isto é desvio substantivo de um protocolo pré-registrado — declarado abertamente. O 4b-i adiciona uma **nota interina** em §8 apontando que a emenda formal (§7/§8/§11 + versão → 1.2) e a mitigação (verificação humana amostral + κ) são descritas no 4b-ii. Mesmo padrão honesto usado em 4a→4b.

## 3. Arquitetura (reúso máximo, retrocompatível)

| Componente | Mudança |
|---|---|
| `scripts/extraction/llm_extract_prompt.py` | **novo:** `build_extract_system_block() -> list[dict]` — bloco estável/cacheável: critérios E1–E5, esquema dos 33 campos + enums, `quality_rubric` 1–5, convenções, instrução abstract-only, contrato JSON estrito. |
| `scripts/screening/llm/batch_client.py` | **+** parâmetro opcional `user_content_fn` em `build_requests` e `screen_with_model` (default `None` → builder de texto atual `build_user_block`; **zero quebra** nos testes existentes — mesmo padrão do `system_block`). |
| `scripts/extraction/extract_llm.py` | **novo:** `build_user_content(row)`, `parse_extraction(text, text_source)`, `fundir(corpus_df, manifest_df, results)`, `run`, `_cli`. |
| `scripts/extraction/validate.py` | **reusado sem modificação** — sanity pós-extração (ano/janela/pré-pós). |
| `Makefile` | **+** alvo `extract-llm` (fora de `screen`/`all`). |
| `protocols/slr_protocol.md` | **+** nota interina em §8 (emenda formal é do 4b-ii). |

Convenções: `from __future__ import annotations`; `_cli(argv)` + `if __name__ == "__main__": sys.exit(_cli(sys.argv[1:]))`; `print` p/ feedback; venv local (não `uv run`); pytest TDD; commits convencionais com `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

Reúso: `screen_with_model`/`anthropic_submit_fn` (Batch API + prompt caching + cache por modelo + logging + retry + timeout monotônico) de `batch_client`; `cache_key`/`custom_id` para a chave `review_id`; `SCHEMA_COLUMNS` (33) de `scripts/extraction/extract.py`.

## 4. Fluxo de dados

```
04_fulltext_manifest.csv (852: id, review_id, text_source, pdf_path)
03_incluidos_final.csv   (metadados/abstract; review_id)
   │  join por review_id  →  df (id, review_id, text_source, pdf_path, title, authors, year, venue, abstract, doi)
   └─ screen_with_model(df, model="claude-sonnet-4-6",
        system_block=build_extract_system_block(),
        user_content_fn=build_user_content,
        cache_path=data/processed/06_cache_extract.json)
        │  1 chamada/paper → JSON {elegivel, motivo_exclusao, confianca_extracao, extracao{33}}
        └─ fundir + parse_extraction → data/processed/06_extraction.csv (37 colunas)
```

`build_user_content(row)`: `text_source=="pdf"` e `pdf_path` existe → `[{"type":"document","source":{"type":"base64","media_type":"application/pdf","data":<b64>}}, {"type":"text","text": <instrução + id/título/ano/venue>}]`; senão → `[{"type":"text","text": <instrução + título/autores/ano/venue/abstract>}]`. (Retorna list — daí o `user_content_fn` injetável; o builder default de screening retorna str, ambos aceitos pela API no campo `content`.)

## 5. Contrato JSON e parsing

Saída por paper:
```
{"elegivel": "incluir" | "excluir",
 "motivo_exclusao": "E1".."E5" | "",
 "confianca_extracao": <float 0-1>,
 "extracao": { <campos sob responsabilidade do LLM: blocos B–G + os campos
                de conteúdo do bloco A (tipo_pub, pais_estudo, periodo_dados).
                Os campos bibliográficos de A (id, doi, titulo, autores, ano,
                periodico) NÃO vêm do LLM — são preenchidos do join> }}
```
Quando `elegivel="excluir"`, `extracao` vem com `n/a`/vazios.

`parse_extraction(text, text_source) -> dict` (tolerante, mesma disciplina de `batch_client.parse_response`):
- JSON irrecuperável → `elegivel="incluir"` (conservador: falha técnica **nunca** exclui), `confianca_extracao=0.0`, 33 campos `n/a`/vazio, `nota_extracao="parse_fail"`.
- `elegivel` ∉ {incluir,excluir} → `incluir` (conservador) + nota.
- Enum de campo inválido → coage para `n/a`, anexa aviso em `nota_extracao`.
- Campo ausente → `""` (texto) ou `n/a` (enum) conforme o tipo no schema.
- `confianca_extracao` fora de [0,1] → clamp.

## 6. Schema de saída — `06_extraction.csv` (37 colunas)

Os **33** de `SCHEMA_COLUMNS` (`scripts/extraction/extract.py`, blocos A–G — `revisto_humano` já está aí, bloco G) **+ 4 extras**:

| Coluna extra | Conteúdo |
|---|---|
| `elegivel` | `incluir` \| `excluir` |
| `motivo_exclusao` | `E1`..`E5` \| `""` |
| `text_source` | `pdf` \| `abstract` (do manifesto — proveniência da extração) |
| `confianca_extracao` | float 0–1 |

`revisto_humano` (bloco G, já nos 33) é setado `False` aqui; o 4b-ii marca `True` no que verificar — **não** é coluna extra (evita dupla contagem). Total = 33 + 4 = **37**.

`id` = o `s-NNN` do manifesto (não gerado pelo LLM). Corpus pós-elegibilidade = `elegivel=="incluir"`. **Bloco A bibliográfico** (`id`, `doi`, `titulo`, `autores`, `ano`, `periodico`) é preenchido **deterministicamente do join corpus/manifesto** — não se confia no LLM para metadados que já temos. O LLM preenche **B–G + os 3 campos de conteúdo de A** (`tipo_pub`, `pais_estudo`, `periodo_dados`), que são inferência do estudo, não metadado bibliográfico.

## 7. Robustez, custo, segurança

- **Idempotente/retomável:** cache `06_cache_extract.json` por `review_id` via `screen_with_model`. Re-rodar pula extraídos; batch interrompido retoma sem re-pagar.
- **PDF inválido/recusado pela API** (>100 p, corrompido) → erro vira `parse_fail` → fusão conservadora (`incluir`/`confianca=0`/`n/a`, `nota_extracao=parse_fail`) — nunca exclui silenciosamente, nunca quebra o lote; o 4b-ii pega na verificação.
- **Sem rede/sem API nos testes:** `submit_fn`/`user_content_fn` injetáveis; leitura de PDF (bytes→base64) só em produção; fakes nos testes; determinístico.
- **Custo (Sonnet 4.6, Batch −50% + prompt caching no bloco de schema):** dominado pelos 134 PDFs; 718 abstracts baratos. Estimativa **~US$3–8**. Assíncrono.
- **`.gitignore`:** `06_cache_extract.json`/`06_extraction.csv` ficam em `data/processed/` (já gitignored para `*.csv`; o `*.json` de processed é a lacuna pré-existente conhecida — fora do escopo deste plano, registrada como follow-up).

## 8. Testes (TDD, pytest)

- `build_extract_system_block`: determinístico/cacheável (1 dict, `cache_control` ephemeral); contém E1–E5, os 33 nomes de campo, a rubrica 1–5, contrato JSON, instrução abstract-only "não inventar".
- `build_user_content`: `pdf` (path existente) → lista com bloco `document` base64 + texto; `abstract` → lista só texto com abstract/metadados; `pdf` com path ausente → degrada para texto (abstract) + flag.
- `parse_extraction`: JSON ok; irrecuperável → incluir/0/n-a/parse_fail; `elegivel` inválido → incluir; enum inválido → n/a + nota; faltantes → vazio/n-a; confianca clamp.
- `fundir`: 37 colunas exatas; `id` do manifesto; A determinístico do corpus; `elegivel=excluir` → campos B–G n/a; `revisto_humano=False`.
- **Retrocompat batch_client:** `user_content_fn=None` → comportamento idêntico (suíte existente verde, sem alterar testes de screening/arbitragem).
- e2e mock no manifesto real (852) → `06_extraction.csv` 37 colunas, contagens coerentes; `validate.py` roda sobre a saída sem erro estrutural.
- Suíte total verde (≥ 171 + novos).

## 9. Integração

- **Makefile:** `extract-llm` → `python -m scripts.extraction.extract_llm --corpus $(DATA_PROC)/03_incluidos_final.csv --manifest $(DATA_PROC)/04_fulltext_manifest.csv --output $(DATA_PROC)/06_extraction.csv --cache $(DATA_PROC)/06_cache_extract.json`. Fora de `screen`/`all`.
- **Protocolo §8:** nota interina (extração operacionalizada por LLM Sonnet 4.6, híbrido PDF/abstract; emenda formal do desvio + mitigação no 4b-ii).
- **validate.py:** reusado como sanity pós-extração (reporta, não bloqueia).
- **PRISMA:** `elegivel=excluir`+`motivo_exclusao` alimentam a caixa "excluídos no texto completo (com motivo)" — consumido no 4b-ii.

## 10. Fora de escopo (YAGNI)

- Verificação humana amostral, κ humano×LLM, diagrama PRISMA, emenda formal do protocolo → **4b-ii**.
- Síntese/análise do corpus extraído → planos futuros.
- Alterar `validate.py`/`extract.py`/`fetch_fulltext.py` — reusados/intactos (`extract.py` permanece como o formulário manual de fallback; não removido).
- Resolvers OA extras / re-aquisição → não é 4b-i (cobertura é o que é, declarada).
- Segunda passada / dois modelos → decidido: 1 passada, Sonnet único.

## 11. Critérios de sucesso

- `make extract-llm` roda os 852 (PDF nativo nos 134, abstract nos 718) e produz `06_extraction.csv` com 37 colunas e `id` s-NNN do manifesto.
- `elegivel` distribui incluir/excluir com `motivo_exclusao` nos excluídos; corpus pós-elegibilidade = `elegivel==incluir` num tamanho reportado.
- `batch_client` retrocompatível (testes existentes verdes sem alteração) + novos testes do 4b-i.
- `validate.py` roda sobre a saída sem erro estrutural.
- Suíte verde (≥ 171 + novos); protocolo §8 com nota interina; tag `v0.7.0-extracao`.
