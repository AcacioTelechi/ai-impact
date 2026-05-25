# Plano 5 — Análise/Síntese dos resultados (design)

**Data:** 2026-05-25
**Status:** aprovado para implementação
**Antecede:** plano de implementação (`docs/superpowers/plans/2026-05-25-plano-5-analise-sintese.md`)

## 1. Problema

A extração LLM (`data/processed/06_extraction.csv`, Plano 4b-i/4b-ii) entregou 852
linhas: **756 incluídos-e-extraídos** (`elegivel=="incluir"` e `nota_extracao!="parse_fail"`),
34 exclusões e 62 `parse_fail` (61 a re-rodar quando houver crédito Anthropic). Os
três capítulos de resultados do TCC (`text/chapters/04_resultados_descritivas.tex`,
`05_resultados_janelas.tex`, `06_comparacao_pre_pos.tex`) precisam ser alimentados
com figuras e tabelas derivadas desse corpus.

Os scripts de análise existentes (`scripts/analysis/descritivas_corpus.py`,
`comparacao_pre_pos.py`, ambos de 2026-05-16, anteriores aos dados reais) estão
**defeituosos**: leem o CSV inteiro sem filtrar, ou seja, rodariam sobre as 852
linhas — contaminando o corpus com as 34 exclusões e os 62 vazios `parse_fail` — em
vez dos 756 corretos. Além disso ignoram as dimensões ricas do schema (mecanismos
Acemoglu-Restrepo `mec_*`, `magnitude_normalizada`, `score_qualidade`, `horizonte`,
`tecnologia_focada`, `metodo_empirico`, `pais_estudo`).

Este plano substitui esses stubs por uma camada de análise correta e testada que
produz os artefatos quantitativos (figuras `.pdf` + tabelas `.tex`) dos três
capítulos. A prosa interpretativa permanece com o autor.

## 2. Decisões (fechadas no brainstorming)

1. **Escopo:** os três capítulos de resultados (04 descritivas, 05 síntese por
   janela, 06 pré/pós) nesta rodada.
2. **Tratamento estatístico:** descritivo + teste de associação χ²/Fisher reportado
   como **exploratório**, com ressalva explícita de que o corpus é o censo dos
   estudos incluídos, não uma amostra aleatória. `scipy` 1.17.1 já disponível.
3. **Sensibilidade por qualidade:** análise primária nos 756; cut de robustez
   repetindo o pré/pós nos 146 estudos com `score_qualidade ≥ 4`.
4. **Magnitude:** reportar cobertura (apenas 13,2% têm `magnitude_normalizada`) +
   descritivo cauteloso (mediana/IQR/faixa por período), **sem pooling** — coerente
   com o desenho narrativo-estruturado, não meta-analítico (§4 do protocolo).
5. **Arquitetura:** camadas — núcleo compartilhado (`corpus`/`stats`/`texkit`) +
   três módulos de capítulo. Funções puras, idempotentes, sem estado em disco.

## 3. Arquitetura

```
06_extraction.csv (852)
        │
        ▼
 corpus.load_corpus()  ──filtra──▶  DataFrame (756) + N + pendentes(parse_fail)
        │
        ├──────────────┬───────────────────┬─────────────────────┐
        ▼              ▼                   ▼                     ▼
 descritivas_   sintese_janelas      comparacao_pre_pos     stats + texkit
 corpus (Cap04) (Cap05)              (Cap06, central)       (compartilhados)
        │              │                   │
        ▼              ▼                   ▼
   figures/*.pdf   fig + tabela        tabelas/*.tex
```

### Módulos (responsabilidade única)

- **`scripts/analysis/corpus.py`** — fonte única da verdade do corpus de análise.
  - `load_corpus(path) -> CorpusAnalise` onde `CorpusAnalise` expõe `.df` (filtrado),
    `.n` (756), `.n_pendentes` (parse_fail), `.n_excluidos`.
  - Filtro canônico: `elegivel == "incluir"` **e** `nota_extracao != "parse_fail"`.
  - Coage `score_qualidade` e `magnitude_normalizada` para numérico (vazio/inválido → NaN).
  - Sem I/O além da leitura do CSV; sem estado persistido.

- **`scripts/analysis/stats.py`** — funções puras, sem I/O.
  - `prop_por_periodo(df, dim) -> dict` — proporções por categoria, **sobre o
    subconjunto classificado** (exclui `n/a` e vazio do denominador); devolve também
    o N de `n/a` para a nota.
  - `assoc_chi2(df, periodo_col, dim) -> ChiResult` — `scipy.stats.chi2_contingency`
    na tabela período × categorias (sem n/a); devolve χ², gl, p, flag de baixa
    contagem esperada (<5).
  - `assoc_fisher_2x2(df, periodo_col, dim, foco) -> FisherResult` — colapsa `dim`
    em {foco, demais}, roda `scipy.stats.fisher_exact`; devolve odds ratio e p exato.
  - `wilson95(k, n) -> (low, high)` — IC Wilson 95% (reaproveitado do Plano 4b-ii).
  - `RESSALVA` — string constante da glosa de não-amostra.

- **`scripts/analysis/texkit.py`** — construção de LaTeX, sem lógica estatística.
  - `escape(s)` — escapa `_` (e demais especiais conforme necessidade).
  - `fmt_pct(x)`, `fmt_p(p)` (exato se ≥0,001, senão `p<0{,}001`), `fmt_ci(low,high)`.
  - `tabela_booktabs(colspec, header, rows, notas=[]) -> str` — `\toprule/\midrule/
    \bottomrule`, notas de rodapé (`\footnotesize`), incluindo a ressalva quando há p.
  - `CANON` — ordenação canônica de cada enum (de `extraction_schema.md`), usada por
    todos os módulos para tabelas/figuras estáveis byte-a-byte.

- **`scripts/analysis/descritivas_corpus.py`** (reescrita) — Cap 04.
  - Figuras: `corpus_anos.pdf`, `corpus_janelas.pdf`, `corpus_tipo_estudo.pdf`
    (denominador corrigido) + `corpus_tecnologia.pdf` (novo, `tecnologia_focada`).
  - Tabela: `descritivas_corpus.tex` — `tipo_pub`, `revisado_por_pares`, top-5
    `pais_estudo`, `metodo_empirico`.

- **`scripts/analysis/sintese_janelas.py`** (novo) — Cap 05.
  - Figura: `mecanismos_janela.pdf` — % de estudos invocando cada `mec_*`
    (deslocamento/reinstalação/complementaridade/demanda_agregada) nas 3 janelas.
  - Tabela: `sintese_janelas.tex` — linhas = `tecnologia_focada` dominante,
    `tipo_estudo` modal, distribuição de `sinal_efeito` e `polarizacao`, % cada
    mecanismo; colunas = janelas `2013-2017`/`2018-2022`/`2022-2026` com N por janela.

- **`scripts/analysis/comparacao_pre_pos.py`** (reescrita) — Cap 06.
  - `comparacao_pre_pos.tex` — tabela central: dimensões (polarização, sinal,
    mecanismos, tipo_estudo, horizonte) × pré (n≈329)/pós (n≈427), proporções +
    p-valor (χ²) + ressalva.
  - `polarizacao_pre_pos.tex` — foco H1: 2×2 período × {alta-quali em risco, demais}
    + Fisher exato + IC Wilson das duas proporções.
  - `robustez_qualidade.tex` — polarização (2×2) + `sinal_efeito` restritos a
    `score_qualidade ≥ 4` (n≈146); nota de células pequenas.
  - `magnitude_cobertura.tex` — cobertura k/n por período + mediana/IQR/faixa de
    `magnitude_normalizada`; **sem** p-valor; ressalva forte.

### Makefile

`analysis` roda os três módulos. Targets isolados: `analysis-descritivas`,
`analysis-janelas`, `analysis-prepos`. Convenção do projeto preservada
(`PYTHON := uv run python`).

## 4. Comportamento detalhado

- **Denominador (regra única):** toda proporção é calculada sobre o subconjunto que
  **classificou** a dimensão — `n/a` e vazio ficam fora do denominador; o N de `n/a`
  é reportado em nota de rodapé. Leitura: "% entre os estudos que trataram a dimensão".
- **Dois níveis de teste:** (a) χ² na tabela período × categorias completa (sem n/a),
  com nota se alguma célula esperada <5 — sem trocar o teste, pois não há Fisher r×c
  exato sem simulação; (b) Fisher exato no 2×2 focado da H1.
- **Dimensões multi-categoria vs. mecanismos binários:** `polarizacao`, `sinal_efeito`,
  `tipo_estudo`, `horizonte`, `tecnologia_focada` são enums multi-categoria → χ² na
  tabela completa. Os quatro `mec_*` são binários (`sim`/`não`, com `n/a` fora do
  denominador): cada um vira **uma linha "% que invoca"** na tabela central (e na
  síntese por janela) e seu teste é um 2×2 (`assoc_fisher_2x2` com foco=`sim`). Ou
  seja, "mecanismos" na tabela central são quatro linhas, não uma dimensão única.
- **Pivô pré/pós:** coluna `pre_pos_chatgpt` já materializada (pivô 2022-11-30).
- **Janelas:** literais `2013-2017`/`2018-2022`/`2022-2026` (schema v1.1).
- **Magnitude:** mediana, IQR (Q1–Q3) e faixa min–max sobre `magnitude_normalizada`
  numérica por período; cobertura = não-nulos/total do período; nenhum teste.
- **Determinismo:** ordenação canônica por enum (não `value_counts`); matplotlib
  backend `Agg`; nenhuma aleatoriedade. Re-rodada após recuperar os 61 apenas
  atualiza números — sem estado a corromper (diferente do snapshot do 4b-ii).
- **Formatação:** proporções 1 casa decimal com `\%`; χ² 2 casas; p exato se ≥0,001,
  senão `p<0{,}001`; vírgula decimal (pt-BR) nas tabelas.

## 5. Testes (TDD)

`tests/analysis/` (fixtures pequenas com literais reais `incluir`/`excluir`/`parse_fail`):

- `test_corpus.py` — filtra para incluir & não-parse_fail (N correto); exclui
  exclusões e parse_fail; coage numéricos (vazio→NaN); conta pendentes.
- `test_stats.py` — `prop_por_periodo` exclui `n/a` do denominador; χ² confere com
  contingência conhecida; Fisher 2×2 (associação clara → p pequeno; independência →
  p≈1); `wilson95` bate com valores do 4b-ii; `RESSALVA` presente.
- `test_texkit.py` — escapa `_`; formata `%`/p (ramo `p<0,001` e exato); estrutura
  booktabs; nota de `n/a`; ordenação canônica respeitada.
- `test_descritivas.py` — figuras escritas (smoke, não-vazias) sobre corpus filtrado;
  estrutura de `descritivas_corpus.tex`.
- `test_sintese_janelas.py` — tabela com 3 colunas de janela + N corretos; mecanismos
  sobre classificados; ordenação canônica; figura escrita.
- `test_comparacao_pre_pos.py` — tabela central (proporções + p + ressalva);
  `polarizacao_pre_pos` (2×2 + Fisher + Wilson); `robustez_qualidade` restrito a
  score≥4; `magnitude_cobertura` com cobertura/mediana/IQR e **sem** p-valor (asserta
  ausência de teste).
- **Determinismo:** rodar um módulo 2× → `.tex` byte-idêntico.

## 6. Escopo

**Inclui:**
- 6 módulos Python (`corpus`, `stats`, `texkit`, `descritivas_corpus`,
  `sintese_janelas`, `comparacao_pre_pos`) + ~20 testes.
- 5 figuras + 6 tabelas (lista na §3).
- Fiação dos três capítulos `.tex` aos novos artefatos (`\includegraphics`/`\input`).
- Atualização do `Makefile` (`analysis` + 3 targets isolados).

**Não inclui (fora do escopo):**
- Prosa interpretativa dos capítulos (autor).
- Meta-análise / pooling de efeitos (vedado pelo §4 do protocolo).
- Conserto do `prisma_flow` (ticket separado — `prisma-flow-schema-bug`).
- Re-rodada da extração dos 61 (passo operacional do usuário; análise é idempotente).
- Histograma de magnitude (descartado: n=48/52, unidades heterogêneas).

## 7. Critérios de aceitação

- `make analysis` produz as 5 figuras + 6 tabelas sem erro, sobre os 756.
- Nenhuma proporção inclui `n/a`/vazio no denominador; N de `n/a` em nota.
- Tabela central e `polarizacao_pre_pos` trazem p-valor + ressalva de não-amostra.
- `magnitude_cobertura` não traz teste de hipótese.
- `robustez_qualidade` usa exatamente `score_qualidade ≥ 4`.
- Rodar duas vezes gera `.tex` byte-idênticos.
- Suite de testes verde (incrementos em `tests/analysis/`).
- Sanity opcional na base real: N = 756.
