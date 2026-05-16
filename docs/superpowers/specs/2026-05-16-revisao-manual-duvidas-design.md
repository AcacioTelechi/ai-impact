# Revisão manual das dúvidas do screening — Design

**Data:** 2026-05-16
**Contexto:** Pós-Plano 3. O screening dual-LLM produziu 1327 incluídos (gate §F4 [80,600] estourado). Diagnóstico: só 462 são "ambos-incluir"; ~865 são *soft-includes* que passaram pela união conservadora por causa de "dúvida" de ≥1 modelo. Esta ferramenta permite adjudicação humana dos ~865 ambíguos.
**Entrada:** `data/processed/03_screening_ta.csv` (2605 registros, schema dual do Plano 3)
**Saídas:** `data/processed/03_revisao_duvidas.csv` (planilha de trabalho), `03_screening_revisado.csv`, `03_incluidos_final.csv`
**Marco previsto:** tag `v0.4.0-revisao-duvidas`

---

## 1. Motivação e enquadramento metodológico

O protocolo registrado (`slr_protocol.md` §7, §11) sempre prometeu "pré-filtragem por LLM-as-judge **+ revisão humana**". O Plano 3 entregou o pré-filtro LLM (dual, com κ=0.602). Esta ferramenta entrega a **revisão humana** — aplicada de forma cirúrgica apenas aos casos que os dois LLMs não resolveram com confiança. Isso:

- Reduz o corpus de 1327 para um número viável de leitura de texto completo (revisor único, ~1 semestre).
- Realiza o compromisso do protocolo (não é desvio — é a etapa prometida).
- Mitiga a crítica de banca a revisor único: os casos ambíguos têm decisão humana documentada.

## 2. Decisões fixadas no brainstorming (2026-05-16)

1. **Subconjunto revisado = soft-includes (865 = 1327 − 462, computado dinamicamente pelo script):** todo registro com `decisao_final == incluir` que **não** seja "ambos os modelos = incluir".
   - **Ambos-incluir (462):** auto-incluídos, não vão para a planilha.
   - **Ambos-excluir (1278):** permanecem excluídos, não vão para a planilha.
   - Soft-includes = `decisao_final == "incluir" AND NOT (decisao_sonnet == "incluir" AND decisao_haiku == "incluir")`. Compreende as 818 com ≥1 "dúvida" e as 47 divergências incluir/excluir. Os números 865/818/47 são derivados do corpus atual; o script os computa, não os hardcoda.
2. **Interface = round-trip de planilha CSV:** `export` gera a planilha; humano preenche em LibreOffice em N sessões; `ingest` consome.
3. **Resumibilidade por arquivo:** o estado é o próprio CSV preenchido; sem estado externo.

## 3. Arquitetura

Dois scripts pequenos e simétricos em `scripts/screening/`:

| Script | Responsabilidade | Lê | Escreve |
|---|---|---|---|
| `revisao_export.py` | Seleciona soft-includes, gera planilha de trabalho **sem destruir trabalho prévio** | `03_screening_ta.csv` (+ planilha existente se houver) | `03_revisao_duvidas.csv` |
| `revisao_ingest.py` | Valida planilha preenchida, funde decisões humanas, gera corpus revisado | `03_screening_ta.csv` + `03_revisao_duvidas.csv` | `03_screening_revisado.csv`, `03_incluidos_final.csv` |

Convenções do repo: `from __future__ import annotations`; `_cli(argv)` + `if __name__ == "__main__": sys.exit(_cli(sys.argv[1:]))`; pandas; venv local (`source .venv/bin/activate`, não `uv run`); pytest TDD; commits convencionais com `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

## 4. Fluxo de dados

```
03_screening_ta.csv (2605)
   ├── ambos-incluir (462)   → auto-incluir  (origem: llm_concordante)
   ├── ambos-excluir (1278)  → auto-excluir  (origem: llm_concordante)
   └── soft-includes (~865)  → [export] 03_revisao_duvidas.csv
                                   │  (humano preenche decisao_humana em N sessões)
                                   └─ [ingest] ──┐
                                                 ▼
                          03_screening_revisado.csv (2605 + decisao_final_revisada + origem_decisao)
                          03_incluidos_final.csv  → entrada do Plano 4
```

## 5. Schema de `03_revisao_duvidas.csv`

Colunas, nesta ordem (otimizada para leitura na planilha):

| Coluna | Conteúdo | Editável? |
|---|---|---|
| `review_id` | chave estável = `custom_id` do registro (sha1 de `cache_key`) | **não** |
| `decisao_humana` | vazia; humano preenche `i`/`e`/`incluir`/`excluir` | **sim** |
| `nota_humana` | justificativa livre opcional | sim |
| `year` | ano | não |
| `title` | título | não |
| `venue` | periódico/venue | não |
| `authors` | autores | não |
| `abstract` | resumo completo | não |
| `decisao_sonnet` | rótulo LLM 1 | não |
| `confianca_sonnet` | confiança LLM 1 | não |
| `justificativa_sonnet` | razão LLM 1 | não |
| `decisao_haiku` | rótulo LLM 2 | não |
| `confianca_haiku` | confiança LLM 2 | não |
| `justificativa_haiku` | razão LLM 2 | não |
| `doi` | DOI para conferência | não |

`review_id` deriva do mesmo `cache_key`/`custom_id` do `batch_client` (DOI normalizado → fallback título+ano → sha1[:32]). Reusar a função existente garante consistência.

## 6. Proteção do trabalho manual (requisito crítico)

O `export` é **idempotente e não-destrutivo**:

- Se `03_revisao_duvidas.csv` **não existe** → cria com `decisao_humana`/`nota_humana` vazias.
- Se **existe** → carrega o existente, faz **merge por `review_id`**: preserva integralmente `decisao_humana` e `nota_humana` já preenchidas; atualiza apenas colunas derivadas (caso o screening mude); adiciona linhas novas se o conjunto soft-include mudou; **nunca remove nem sobrescreve uma decisão humana**.
- Linhas que deixaram de ser soft-include (raro) são mantidas mas marcadas — nunca silenciosamente descartadas.

Re-rodar `export` a qualquer momento é seguro. O humano trabalha em N sessões salvando o arquivo no LibreOffice; não há estado externo a perder. O `ingest` casa por `review_id`, então reordenar/filtrar/ocultar colunas na planilha é permitido.

## 7. Validação e regra de decisão (`ingest`)

Normalização de `decisao_humana` (case-insensitive, strip): `i`/`incluir` → `incluir`; `e`/`excluir` → `excluir`; vazio/NaN → `pendente`.

- Valor não reconhecido (ex.: `x`, `talvez`, `1`) → **erro explícito** listando `review_id` e linha; não escreve saídas.
- `pendente` → tratado como `incluir` (conservador, permanece no corpus) mas contabilizado e reportado.
- `ingest` imprime resumo: `N decididas (X incluir, Y excluir), Z pendentes de 865`. Se `Z > 0`, aviso destacado de que PRISMA/Plano 4 só devem rodar com `Z == 0`. Não bloqueia a geração (sempre produz as saídas), apenas alerta — o "fechamento" é decisão do usuário.

Regra final por registro (em `decisao_final_revisada`, com `origem_decisao`):

| Caso | decisao_final_revisada | origem_decisao |
|---|---|---|
| ambos-incluir (462) | `incluir` | `llm_concordante` |
| ambos-excluir (1278) | `excluir` | `llm_concordante` |
| soft-include, humano `i` | `incluir` | `humano` |
| soft-include, humano `e` | `excluir` | `humano` |
| soft-include, vazio | `incluir` | `pendente` |

## 8. Saídas do `ingest`

1. **`03_screening_revisado.csv`** — 2605 linhas: todas as colunas de `03_screening_ta.csv` + `decisao_final_revisada` + `origem_decisao` + `nota_humana` (vazia exceto onde o humano anotou).
2. **`03_incluidos_final.csv`** — subconjunto `decisao_final_revisada == "incluir"`, mesmas colunas do corpus. **Substitui `03_incluidos_ta.csv` como entrada do Plano 4** (`make fetch` e elegibilidade).

## 9. Integração

- **PRISMA:** `prisma_flow.py` passa a ler `03_screening_revisado.csv` (coluna `decisao_final_revisada`) em vez de `03_screening_ta.csv`. A revisão humana é a etapa "revisão humana" do screening (protocolo §7) — não é caixa PRISMA nova; é o screening título/resumo concluído. Exclusões de screening = ambos-excluir LLM + excluídos humanos. (Ajuste de `prisma_flow.py` fica fora deste plano — só se registra a intenção; o script PRISMA é tocado quando o Plano de PRISMA/escrita rodar. Este plano não altera `prisma_flow.py`.)
- **Makefile:** dois alvos novos, `revisao-export` e `revisao-ingest`. **Não** entram em `screen` (exigem ação manual humana entre eles).
- **`slr_protocol.md`:** nota curta em §7 registrando que a revisão humana das dúvidas foi operacionalizada via adjudicação manual do subconjunto soft-include (com referência a este design). Atualização de protocolo é parte da entrega.

## 10. Testes (TDD, pytest)

**`revisao_export.py`:**
- Seleciona exatamente os soft-includes; exclui ambos-incluir e ambos-excluir.
- Schema e ordem de colunas conforme §5.
- **Idempotência não-destrutiva (crítico):** criar planilha → preencher algumas `decisao_humana` → re-exportar → decisões preservadas; linhas novas adicionadas vazias; nenhuma decisão sobrescrita.
- `review_id` estável e consistente com `custom_id` do `batch_client`.

**`revisao_ingest.py`:**
- Casa decisões por `review_id` mesmo com a planilha reordenada.
- `i`/`e`/`incluir`/`excluir`/case-misto normalizam corretamente.
- Valor inválido → erro listando linhas, sem escrever saídas.
- Vazio → `pendente`, contagem e aviso corretos.
- 462 ambos-incluir e 1278 ambos-excluir entram em `03_screening_revisado.csv` com `origem_decisao == llm_concordante` e **não** aparecem na planilha.
- `03_incluidos_final.csv` = exatamente `decisao_final_revisada == incluir`.

**e2e:** `03_screening_ta` (fixture pequena) → export → simula preenchimento parcial → ingest → `03_screening_revisado.csv` + `03_incluidos_final.csv` coerentes, contagem de pendentes correta.

Suíte total continua verde (100 testes pré + novos).

## 11. Fora de escopo (YAGNI)

- UI web/terminal interativo (decidido: planilha).
- Alteração de `prisma_flow.py` (só registra a intenção; feito no plano de PRISMA/escrita).
- Re-rodar LLMs ou mudar prompt (decisão foi revisão humana, não re-prompt).
- 3º modelo árbitro (descartado em favor de humano).
- Segunda rodada de revisão / κ intra-revisor (protocolo prevê dupla revisão em 10% — fica para etapa de qualidade, não aqui).

## 12. Critérios de sucesso

- `make revisao-export` gera `03_revisao_duvidas.csv` com ~865 soft-includes e schema da §5.
- Re-export após preenchimento parcial não destrói nenhuma decisão humana (teste verde).
- `make revisao-ingest` produz `03_screening_revisado.csv` (2605) e `03_incluidos_final.csv`, com contagem de pendentes reportada.
- Com todas as ~865 decididas, `03_incluidos_final.csv` = 462 + (humano-incluídos), número dentro de faixa viável para leitura de texto completo.
- Suíte de testes verde (≥ 100 + novos).
- Protocolo §7 atualizado; tag `v0.4.0-revisao-duvidas`.
