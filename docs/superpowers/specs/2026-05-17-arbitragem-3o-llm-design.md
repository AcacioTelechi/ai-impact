# Arbitragem por 3º LLM das dúvidas do screening — Design

**Data:** 2026-05-17
**Contexto:** Pós-Plano 3 + v0.4.0. O screening dual-LLM produziu 1327 incluídos (865 são *soft-includes* ambíguos passados pela união conservadora por "dúvida"/divergência). O usuário optou por resolver esses 865 com um terceiro LLM árbitro **em vez de** revisão humana manual.
**Entrada:** `data/processed/03_screening_ta.csv` (2605 registros, schema Plano 3)
**Saídas:** `data/processed/03_screening_arbitrado.csv`, `03_incluidos_final.csv`, `text/tables/arbitragem_kappa.tex`
**Marco previsto:** tag `v0.5.0-arbitragem`

---

## 1. Decisões fixadas no brainstorming (2026-05-17)

1. **O 3º LLM substitui a revisão humana** dos 865 soft-includes. Não há triagem manual.
2. **Árbitro cego e independente:** lê apenas título/autores/ano/venue/resumo (o mesmo `build_user_block`), sem ver os pareceres de Sonnet/Haiku.
3. **Árbitro forçado a binário:** contrato de saída `incluir` | `excluir`; "duvida" proibido (a decisão precisa ser decisiva). Critérios idênticos aos do screening (instrumento comparável).
4. **Modelo árbitro:** Claude **Opus 4.7** (`claude-opus-4-7`) — mais capaz e não-participante do screening (Sonnet 4.6 / Haiku 4.5).
5. **Regra de fusão:** o veredito do árbitro é final para os 865 não-unânimes; 462 ambos-incluir e 1278 ambos-excluir permanecem aceitos pela concordância LLM.
6. **κ:** concordância par-a-par árbitro×Sonnet e árbitro×Haiku nos 865 (rótulo binário comparável); **não** Fleiss 3-way (espaços de rótulo diferentes — árbitro não tem "duvida").
7. **Reúso máximo** da infraestrutura existente (Batch API + prompt caching + cache por modelo + logging do `batch_client`).

## 2. Desvio do protocolo pré-registrado — declarado abertamente

O protocolo `slr_protocol.md` v1.0, registrado em git **antes** da execução, comprometeu-se com "Screening (título+resumo) — pré-filtragem por LLM-as-judge **+ revisão humana**" (§7) e listou "revisor único (mitigado por dupla revisão pessoal)" (§11). Substituir a revisão humana por um 3º LLM é um **desvio substantivo de um protocolo pré-registrado**.

Este design trata o desvio com honestidade (não o oculta):
- **§7 reescrito** (protocolo → versão 1.1, nota de emenda datada 2026-05-17): a etapa de screening passa a ser **tri-LLM** — dois triadores (Sonnet 4.6, Haiku 4.5) + um árbitro independente mais capaz (Opus 4.7) que decide os casos não-unânimes. A revisão humana prevista foi substituída por arbitragem automática por restrição de tempo/escala (revisor único, 865 casos, prazo de um semestre).
- **§11 (limitações)** ganha item explícito: ausência de revisor humano na seleção é desvio do protocolo originalmente registrado; mitigado por três modelos independentes (árbitro mais capaz e fora do screening), concordância par-a-par reportada, e regra conservadora (na incerteza, inclui); **limitação reconhecida e passível de questionamento em banca**.
- A versão registrada original permanece no histórico git (rastreável); a emenda é datada e justificada — coerente com a cláusula §3 do protocolo ("o hash do commit funciona como timestamp do registro").

Atualizar o protocolo é **parte da entrega** deste design.

## 3. Arquitetura

Reúso máximo; um script novo + extensões mínimas e retrocompatíveis.

| Componente | Mudança |
|---|---|
| `scripts/screening/llm/prompt.py` | **+** `build_arbiter_system_block() -> list[dict]`: reusa o texto de critérios do `build_system_block` (mesmo período, E1–E5, escopo) mas com contrato de saída estrito (sem "duvida"). Marcado para prompt caching (estável). `build_user_block` reusado sem alteração. |
| `scripts/screening/llm/batch_client.py` | `build_requests(df, model, cached=None, system_block=None)` e `screen_with_model(df, model, *, cache_path=None, submit_fn=None, mock=False, system_block=None)` ganham parâmetro opcional `system_block`. Default `None` → usa `build_system_block()` (comportamento atual; **zero quebra** nos testes existentes). Árbitro injeta `build_arbiter_system_block()`. |
| `scripts/screening/arbitragem.py` | **novo.** `selecionar` (reusa `soft_includes` de `revisao_export`), `fundir` (tabela-verdade), `run`, `_cli`. |
| `scripts/screening/agreement.py` | **inalterado.** `arbitragem.py` importa `cohen_kappa` dele (DRY) para a tabela do árbitro; `agreement.py` em si não muda (menos regressão). |
| `Makefile` | **+** alvo `arbitragem` (não entra em `screen`). |
| `protocols/slr_protocol.md` | §7 reescrito, §11 +item, versão→1.1 + nota de emenda. |

Convenções do repo: `from __future__ import annotations`; `_cli(argv)` + `if __name__ == "__main__": sys.exit(_cli(sys.argv[1:]))`; `print` para feedback; venv local (não `uv run`); pytest TDD; commits convencionais com `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

O `_mock_judge` existente (em `screening_ta.py`, importado por `batch_client`) é reutilizado no modo mock do árbitro — mas como ele pode devolver "duvida", a camada de fusão normaliza qualquer resultado ∉ {incluir,excluir} (ver §5). Em produção o prompt estrito evita "duvida"; a normalização é salvaguarda.

## 4. Fluxo de dados

```
03_screening_ta.csv (2605)
   ├── ambos-incluir (462)  → incluir   (origem: llm_concordante)
   ├── ambos-excluir (1278) → excluir   (origem: llm_concordante)
   └── soft-includes (865)  → screen_with_model(model="claude-opus-4-7",
                                  system_block=build_arbiter_system_block(),
                                  cache_path=data/processed/03_cache_arbitro.json)
                                   │
                                   └→ fundir → 03_screening_arbitrado.csv (2605)
                                              03_incluidos_final.csv (→ Plano 4)
                                              text/tables/arbitragem_kappa.tex
```

`soft_includes` (de `scripts/screening/revisao_export.py`) é a fonte única do predicado (`decisao_final=="incluir"` e não ambos-incluir). `arbitragem.py` o importa — DRY, sem reimplementar.

## 5. Regra de fusão (`fundir`)

Produz `decisao_final_arbitrada` + `origem_decisao` para os 2605, casando o resultado do árbitro por `review_id` (= `custom_id(cache_key(row))`, idêntico ao usado em screening/revisão — robusto e consistente).

| Caso | `decisao_final_arbitrada` | `origem_decisao` |
|---|---|---|
| Sonnet=incluir ∧ Haiku=incluir | `incluir` | `llm_concordante` |
| Sonnet=excluir ∧ Haiku=excluir | `excluir` | `llm_concordante` |
| soft-include, árbitro=`incluir` | `incluir` | `arbitro` |
| soft-include, árbitro=`excluir` | `excluir` | `arbitro` |
| soft-include, árbitro ∉ {incluir,excluir} | `incluir` | `arbitro_falha` |

A última linha é a salvaguarda de alta sensibilidade: `parse_response` mapeia JSON irrecuperável → `duvida`; como "duvida" não é resultado válido do árbitro, normaliza-se defensivamente para **incluir** (falha técnica nunca exclui um paper silenciosamente) e marca-se `arbitro_falha` para auditoria. Consistente com o princípio de segurança do projeto (toda falha de parse cai para o lado conservador).

## 6. Schema de saída

`03_screening_arbitrado.csv` — 2605 linhas, todas as colunas de `03_screening_ta.csv` mais:

| Coluna | Conteúdo |
|---|---|
| `decisao_arbitro` | `incluir`/`excluir` nos 865; vazio nos 1740 concordantes |
| `justificativa_arbitro` | 1-2 frases do árbitro; vazio nos concordantes |
| `confianca_arbitro` | float 0-1; vazio nos concordantes |
| `decisao_final_arbitrada` | `incluir`/`excluir` (§5) |
| `origem_decisao` | `llm_concordante` / `arbitro` / `arbitro_falha` |

`03_incluidos_final.csv` — subconjunto `decisao_final_arbitrada == "incluir"`, mesmas colunas; **mesmo nome de arquivo** do caminho manual v0.4.0 (Plano 4 consome igual, agnóstico ao caminho).

## 7. Métrica de concordância (honesta)

`text/tables/arbitragem_kappa.tex`, calculada **apenas nos 865** soft-includes:
- Para comparar o árbitro (binário) com Sonnet/Haiku (que têm "duvida"), mapeia-se cada um dos triadores para rótulo binário pela mesma lógica da união conservadora: `excluir → "excluir"`, `incluir`/`duvida → "manter"`.
- Reporta, para árbitro×Sonnet e árbitro×Haiku: n, % concordância bruta e κ de Cohen (binário). A geração da tabela vive em `arbitragem.py`, que **importa** `cohen_kappa` de `agreement.py` (DRY; `agreement.py` não é modificado).
- A legenda da tabela declara explicitamente a definição de rótulo binário usada (transparência; não inflar κ). **Não** se computa Fleiss 3-way (espaços de rótulo distintos).

## 8. Custo

865 registros × 1 modelo (Opus 4.7) via Batch API (−50%) + prompt caching no bloco de critérios estável (~90% nos tokens de entrada repetidos). Estimativa **~US$3–6**. Assíncrono (irrelevante, não interativo). Cache em `03_cache_arbitro.json` → idempotente/retomável (mesma robustez do screening: backup de batch via `submit_fn`, polling com timeout monotônico, logging de progresso).

## 9. Testes (TDD, pytest)

- `build_arbiter_system_block`: determinístico/cacheável; contém os critérios (período 2013-01-01..2026-06-30, E1–E5); contrato estrito (cita `"incluir"`/`"excluir"`, **não** oferece `"duvida"`); estrutura igual ao bloco de screening (lista de 1 dict com `cache_control`).
- `build_requests`/`screen_with_model`: `system_block=None` → idêntico ao atual (regressão: os testes existentes seguem verdes sem alteração); `system_block` injetado → usado nos requests; cache por modelo continua isolado.
- `arbitragem.fundir`: tabela-verdade completa (4 categorias + a linha `arbitro_falha`→incluir); casamento por `review_id` robusto a reordenação; 462/1278 entram como `llm_concordante` sem aparecer entre os arbitrados.
- e2e mock: `03_screening_ta` (fixture) → `arbitragem.run --mock` → `03_screening_arbitrado.csv` (2605, schema completo) + `03_incluidos_final.csv` coerente + tabela κ gerada.
- agreement: a função de κ do árbitro reusa `cohen_kappa`; tabela LaTeX com `\%` escapado (mesma disciplina do `agreement.py`).
- Suíte total continua verde (≥ 142 + novos).

## 10. Integração

- **PRISMA:** `prisma_flow.py` passará a poder ler `03_screening_arbitrado.csv` (coluna `decisao_final_arbitrada`). **Fora de escopo deste plano** (igual ao v0.4.0: o ajuste de `prisma_flow.py` fica para o plano de PRISMA/escrita). Apenas registra-se a intenção.
- **Makefile:** alvo `arbitragem` (Opus, produção sem `--mock`); dry-run mock documentado. **Não** adicionado a `screen` (passo pós-screening, custa API, decisão deliberada do usuário).
- **Protocolo:** §7 reescrito, §11 +item, versão 1.0→1.1 com nota de emenda datada (entrega deste plano).

## 11. Fora de escopo (YAGNI)

- Remover/alterar a ferramenta manual v0.4.0 (`revisao_export`/`revisao_ingest`) — permanece intacta como alternativa/auditoria; não usada neste caminho.
- Alterar `prisma_flow.py` (registra intenção; feito no plano de PRISMA/escrita).
- Árbitro informado (vê pareceres) ou Fleiss 3-way — descartados no brainstorming.
- Árbitro de provedor externo (Gemini/GPT) — descartado (escopo/manutenção).
- Re-rodar Sonnet/Haiku ou mudar o prompt de screening — não se tocam.

## 12. Critérios de sucesso

- `make arbitragem` roda os 865 no Opus 4.7 e produz `03_screening_arbitrado.csv` (2605) + `03_incluidos_final.csv` + `arbitragem_kappa.tex`.
- `origem_decisao` distribui 462 `llm_concordante`-incluir + 1278 `llm_concordante`-excluir + 865 `arbitro`/`arbitro_falha`.
- Corpus final (`decisao_final_arbitrada == incluir`) dentro de faixa viável para leitura de texto completo; se ainda fora de [80, 600] (gate §F4), reportar e discutir antes do Plano 4.
- `build_requests`/`screen_with_model` retrocompatíveis (142 testes existentes verdes sem mudança) + novos testes do árbitro.
- Protocolo §7/§11 atualizado, versão 1.1; tag `v0.5.0-arbitragem`.
