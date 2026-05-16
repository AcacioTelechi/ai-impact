# Plano 3 — Screening título+resumo (dual-LLM) — Design

**Data:** 2026-05-16
**Fase PRISMA:** Screening (corresponde a F4 do design geral, §4.3)
**Entrada:** `data/processed/02_corpus_dedup.csv` (2.605 registros)
**Saída:** `data/processed/03_screening_ta.csv`, `03_incluidos_ta.csv`, `text/tables/kappa_screening.tex`
**Marco previsto:** tag `v0.3.0-screening`

---

## 1. Contexto e motivação

O screening por título+resumo filtra o corpus bruto antes da leitura de texto
completo (elegibilidade, Plano 4). Com 2.605 registros, triagem manual completa
é inviável no prazo do TCC (~1 semestre, revisor único).

O `screening_ta.py` atual é um esqueleto: loop síncrono, parse de JSON frágil,
sem retry/backoff, sem κ, sem batch, prompt com janela desatualizada
("2013–2025"). Este plano o substitui por um pipeline dual-LLM robusto.

## 2. Decisões metodológicas (fixadas no brainstorming de 2026-05-16)

1. **Dual-LLM independente**: dois modelos rotulam todos os 2.605 registros de
   forma independente. Modelos: **Claude Sonnet 4.6** (`claude-sonnet-4-6`) e
   **Claude Haiku 4.5** (`claude-haiku-4-5-20251001`). Tiers distintos da mesma
   geração; divergências revelam casos genuinamente ambíguos.
2. **κ de Cohen inter-modelo** reportado como nota metodológica, calculado
   sobre os 3 rótulos originais (`incluir`/`excluir`/`duvida`) antes do colapso.
3. **Regra de divergência — união conservadora**: exclui-se um registro do
   screening **somente se ambos os modelos disserem `excluir`**. Qualquer
   `incluir` ou `duvida` de qualquer modelo → passa para elegibilidade.
   Princípio canônico de SLR: erro de inclusão é corrigível na leitura de
   texto completo; erro de exclusão é perda definitiva e silenciosa.
4. **Zero trabalho manual** de rotulagem. Confiabilidade vem da concordância
   inter-modelo, não de conjunto-ouro humano. Aceito na literatura recente de
   SLR-com-LLM (Khraisha et al. 2024). Preserva o compromisso do protocolo
   registrado (§7, §11) de "LLM-as-judge + checagem de confiabilidade + κ".
5. **Execução via Batch API + prompt caching**. O bloco de critérios é
   idêntico nas 5.210 chamadas → cache de prompt (~90% de desconto nos tokens
   de entrada repetidos). Batch API → −50%. Custo total estimado < US$3.
   Assíncrono (até 24h garantido pela Anthropic, tipicamente minutos);
   irrelevante porque o pipeline não é interativo.

> **Nota de risco registrada:** a opção inicial do usuário foi "sem validação
> humana nenhuma". Foi sinalizado que isso contradiz o protocolo pré-registrado
> em git (§7, §11) e fragiliza a defesa de banca (revisor único sem nenhuma
> checagem de confiabilidade). O dual-LLM foi adotado como alternativa que
> preserva uma estatística de confiabilidade (κ) sem custar tempo manual.

## 3. Arquitetura de módulos

Unidades pequenas, de responsabilidade única, testáveis isoladamente.

| Módulo | Responsabilidade | Depende de |
|--------|------------------|------------|
| `scripts/screening/llm/__init__.py` | pacote | — |
| `scripts/screening/llm/prompt.py` | Monta o prompt: bloco de critérios estável (cacheável) + bloco do registro. Lê os critérios de `inclusion_criteria.md` de forma versionada. | — |
| `scripts/screening/llm/batch_client.py` | Submete um batch à Anthropic, faz polling até concluir, baixa resultados, parse robusto de JSON, retry/backoff (tenacity). Cache em disco por `(chave_registro, modelo)`. | `anthropic`, `tenacity` |
| `scripts/screening/screening_ta.py` | Orquestra: dispara 2 batches (Sonnet, Haiku) → aplica merge união conservadora → grava `03_screening_ta.csv` e `03_incluidos_ta.csv`. Mantém `--mock`. | os dois acima |
| `scripts/screening/agreement.py` | κ de Cohen inter-modelo + matriz de confusão 3×3 + % concordância → `text/tables/kappa_screening.tex`. | `scikit-learn`, `pandas` |

`--mock` preservado: usa o heurístico rule-based atual (`_mock_judge`) para
testes e dry-runs sem custo de API.

## 4. Fluxo de dados

```
02_corpus_dedup.csv (2.605)
   │
   ├─► batch Sonnet 4.6 ──┐
   │                      ├─► merge (união conservadora) ─► 03_screening_ta.csv
   ├─► batch Haiku 4.5 ───┘                                 03_incluidos_ta.csv
   │
   └─► agreement.py ─► text/tables/kappa_screening.tex
```

## 5. Schema de saída

`03_screening_ta.csv` preserva as 8 colunas originais e adiciona:

| Coluna | Conteúdo |
|--------|----------|
| `decisao_sonnet`, `justificativa_sonnet`, `confianca_sonnet` | saída modelo A |
| `decisao_haiku`, `justificativa_haiku`, `confianca_haiku` | saída modelo B |
| `decisao_final` | `excluir` sse ambos=`excluir`; senão `incluir` |
| `concordancia` | `concordam` / `divergem` (auditoria + κ) |
| `criterio_exclusao` | E1, E2, E3 ou E5 quando ambos excluem (do modelo de maior `confianca`) |

`03_incluidos_ta.csv` = subconjunto `decisao_final == incluir` → entrada do Plano 4.

### Tabela-verdade do merge (3 rótulos por modelo)

| Sonnet | Haiku | decisao_final | concordancia |
|--------|-------|---------------|--------------|
| excluir | excluir | **excluir** | concordam |
| incluir | incluir | incluir | concordam |
| duvida | duvida | incluir | concordam |
| incluir | excluir | **incluir** | divergem |
| excluir | incluir | **incluir** | divergem |
| incluir | duvida | incluir | divergem |
| duvida | excluir | **incluir** | divergem |
| excluir | duvida | **incluir** | divergem |
| duvida | incluir | incluir | divergem |

Regra resumida: `final = excluir` ⟺ `sonnet == excluir AND haiku == excluir`.
`concordancia = concordam` ⟺ rótulos originais idênticos.

## 6. Prompt

Correções obrigatórias ao prompt atual:

- Janela: **2013-01-01 a 2026-06-30** (era "2013–2025"; alinhado ao protocolo
  §6 pós-extensão de 2026-05-16).
- Critérios: os cinco E1–E5 de `inclusion_criteria.md`. E4 (texto completo
  inacessível) é explicitamente marcado como **não aplicável** em título/resumo
  — o modelo não deve excluir por E4 nesta fase.
- Estrutura em dois blocos: (1) instruções + critérios — **estável**, marcado
  para cache de prompt; (2) dados do registro — variável.
- Saída JSON estrita: `{"decisao": incluir|excluir|duvida, "justificativa":
  "1-2 frases citando critério", "confianca": float 0-1, "criterio": "E1..E5
  ou null"}`.

## 7. Tratamento de erro

- **Parse JSON tolerante**: strip de ```` ```json ```` fences; fallback regex
  para extrair o objeto; JSON irrecuperável → `decisao=duvida, confianca=0,
  justificativa="parse_fail"`. Conservador: falha técnica nunca exclui.
- **Retomável**: cache em disco por `(doi_ou_chave_titulo_ano, modelo)`.
  Re-rodar pula o já decidido → idempotente. Permite retomar batch interrompido.
- **Falha de batch** (timeout >24h, erro de API após retries) → exceção
  explícita; não grava CSV parcial corrompido.
- `ANTHROPIC_API_KEY` via `.env` + `load_dotenv()` (mesmo padrão do
  `openalex_search.py`). `.env` já está em `.gitignore` — chave nunca commitada.

## 8. Testes (TDD, modo mock, custo zero)

- Tabela-verdade do merge união conservadora: **todos os 9 pares** de rótulos.
- Parse JSON: fence ```` ```json ````, JSON sujo com texto antes/depois,
  irrecuperável → `duvida/0`.
- κ de Cohen: concordância perfeita → κ=1; independência → κ≈0; caso fixo
  com valor conhecido.
- Idempotência: re-rodar com cache cheio → zero chamadas de API.
- E2E mock: `02_corpus_dedup.csv` (fixture) → `03_screening_ta.csv` com schema
  completo + `03_incluidos_ta.csv` coerente.
- `agreement.py`: gera `kappa_screening.tex` com κ, n, % e matriz 3×3.

Meta: suíte total continua verde (baseline 63 testes pré-Plano 3; 96 após a implementação).

## 9. Makefile

Target `screening_ta` atualizado: dois modelos, sem `--mock` por padrão em
produção. Novo target `screening-kappa` roda `agreement.py`. `screen` composite
encadeia `consolidate → dedup → screening_ta → screening-kappa`.

## 10. Custo

2.605 × 2 modelos = 5.210 chamadas. Batch API (−50%) + prompt caching no bloco
de critérios (~90% nos tokens de entrada repetidos). Sonnet 4.6 + Haiku 4.5
(Haiku ~10× mais barato que Sonnet). **Estimativa total < US$3.**

## 11. Fora de escopo (YAGNI)

- Revisão/rotulagem humana manual — descartada por decisão do usuário;
  substituída por concordância inter-modelo.
- Snowballing — Plano 4+.
- Fetch de texto completo, elegibilidade, extração — Planos 4–5.
- Busca em periódicos individuais — não necessária (WoS+Scopus cobriram).

## 12. Critérios de sucesso

- Pipeline `02 → 03` roda fim-a-fim com os dois modelos reais.
- `03_screening_ta.csv` com schema completo; `03_incluidos_ta.csv` coerente
  com a regra de união conservadora.
- `text/tables/kappa_screening.tex` gerado com κ inter-modelo reportável.
- Suíte de testes verde (≥ 63 baseline + novos testes do Plano 3; 96 ao final).
- Corpus pós-screening dentro de uma faixa plausível. O gate original do
  design §F4 era [80, 400], calibrado para um corpus bruto estimado em ~150;
  como o corpus real (2.605) é ~17× maior, a faixa de sanidade pós-screening
  é ajustada para [80, 600]. Fora dela, inspecionar prompt/critérios antes
  do Plano 4.
- Tag `v0.3.0-screening`.
