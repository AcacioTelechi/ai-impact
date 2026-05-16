# ai-impact

TCC — Bacharelado em Ciências Econômicas. Revisão sistemática da literatura sobre **impactos da inteligência artificial no mercado de trabalho (2013–2025)**, com comparação pré- e pós-ChatGPT.

## Estrutura

- `protocols/` — protocolo SLR registrado antes da execução.
- `data/raw/` — exports brutos de cada base (imutáveis após geração; **não versionados**).
- `data/processed/` — outputs de cada etapa do pipeline.
- `scripts/` — pipeline Python (`screening/`, `extraction/`, `analysis/`, `utils/`).
- `text/` — fonte LaTeX do TCC.
- `tests/` — testes `pytest` para todos os scripts.
- `docs/superpowers/specs/` — design da revisão.
- `docs/superpowers/plans/` — planos de implementação.

## Setup

Requisitos: Python 3.12, `uv`, TeX Live com `latexmk`.

```bash
uv sync
```

## Comandos principais

```bash
make test        # roda todos os testes pytest
make screen      # consolida + deduplica + screening por LLM
make extract     # abre CLI de extração estruturada
make analysis    # regenera figuras e tabelas em text/
make pdf         # compila TCC em build/main.pdf
make all         # pipeline completo
```

## Documentação

- Design da revisão: `docs/superpowers/specs/2026-05-13-tcc-slr-ia-trabalho-design.md`
- Plano atual: `docs/superpowers/plans/2026-05-13-tcc-infra-protocolos.md`
- Protocolo SLR: `protocols/slr_protocol.md`
- Critérios: `protocols/inclusion_criteria.md`
- Esquema de extração: `protocols/extraction_schema.md`
- Rubrica de qualidade: `protocols/quality_rubric.md`
- Strings de busca: `protocols/search_strings/`
