# Esquema de Extração de Dados

Versão 1.1 — janela 2022-2025→2022-2026 alinhada à extensão §6 do protocolo (2026-05-16); ver nota. Cada linha de `data/processed/06_extraction.csv` segue este esquema.

> Nota 2026-05-17: a terceira janela foi estendida para 2022-2026 para acompanhar a janela de busca §6 (até 2026-06-30); ~124 estudos de 2026 entrariam órfãos com 2022-2025.

## Bloco A — Identificação

| Coluna | Tipo | Valores |
|--------|------|---------|
| `id` | string | UUID estável, formato `s-NNN` (e.g., `s-001`) |
| `doi` | string | DOI normalizado (lowercase, sem URL prefix) |
| `titulo` | string | Título completo do estudo |
| `autores` | string | Lista separada por `; ` (sobrenome, iniciais) |
| `ano` | int | Ano de publicação |
| `periodico` | string | Nome do periódico ou série de working paper |
| `tipo_pub` | enum | `journal` \| `working paper` \| `book chapter` |
| `pais_estudo` | string | País-foco; `multipais` se cross-country |
| `periodo_dados` | string | Janela temporal dos dados empíricos (e.g., `2010-2019`) |

## Bloco B — Classificação temporal

| Coluna | Tipo | Valores |
|--------|------|---------|
| `janela` | enum | `2013-2017` \| `2018-2022` \| `2022-2026` |
| `pre_pos_chatgpt` | enum | `pre` \| `pos` (pivô = 2022-11-30) |
| `tecnologia_focada` | enum | `automação` \| `ML/preditiva` \| `deep learning` \| `IA generativa/LLMs` \| `robôs+IA` \| `geral` |

## Bloco C — Tipo de evidência

| Coluna | Tipo | Valores |
|--------|------|---------|
| `tipo_estudo` | enum | `exposição ocupacional` \| `evidência macro/setorial` \| `firma/freelancer` \| `teórico/modelo` \| `survey/revisão` |
| `metodo_empirico` | enum | `OLS` \| `DiD` \| `IV` \| `RDD` \| `evento-estudo` \| `estrutural` \| `ML` \| `descritivo` \| `modelo teórico` \| `n/a` |
| `unidade_analise` | enum | `ocupação` \| `indústria` \| `firma` \| `indivíduo` \| `país` \| `região` \| `múltipla` |
| `fonte_dados` | string | Texto curto (e.g., `O*NET, BLS-OES`; `Felten-AIOE`; `dados administrativos brasileiros`) |

## Bloco D — Mecanismos teóricos (framework Acemoglu-Restrepo)

| Coluna | Tipo | Valores |
|--------|------|---------|
| `mec_deslocamento` | enum | `sim` \| `não` \| `n/a` |
| `mec_reinstalacao` | enum | `sim` \| `não` \| `n/a` |
| `mec_complementaridade` | enum | `sim` \| `não` \| `n/a` |
| `mec_demanda_agregada` | enum | `sim` \| `não` \| `n/a` |
| `mec_outros` | string | Texto livre |

## Bloco E — Achados sobre emprego *(crítico)*

| Coluna | Tipo | Valores |
|--------|------|---------|
| `sinal_efeito` | enum | `negativo` \| `positivo` \| `nulo` \| `ambíguo` \| `n/a` |
| `magnitude_reportada` | string | Texto livre normalizado (e.g., `-14% no longo prazo`; `exposição média 0.46 Felten`) |
| `magnitude_normalizada` | float | Elasticidade ou % comparável quando aplicável; vazio caso contrário |
| `ocupacoes_afetadas` | string | Códigos SOC/CBO de alto nível ou texto curto (e.g., `alta-qualificação cognitiva`) |
| `polarizacao` | enum | `alta-quali em risco` \| `baixa-quali em risco` \| `ambos` \| `neutro` \| `n/a` |
| `horizonte` | enum | `curto prazo` \| `médio` \| `longo` \| `projeção` |

## Bloco F — Qualidade e robustez

| Coluna | Tipo | Valores |
|--------|------|---------|
| `score_qualidade` | int | 1–5 (ver `quality_rubric.md`) |
| `limitacoes_declaradas` | string | Texto livre curto |
| `replicavel` | enum | `sim` \| `parcial` \| `não` \| `n/a` |
| `revisado_por_pares` | enum | `sim` \| `não` |

## Bloco G — Notas livres

| Coluna | Tipo | Valores |
|--------|------|---------|
| `nota_extracao` | string | Observações livres do extrator |
| `citacoes_chave` | string | IDs de outros estudos do corpus que este cita/contraria, separados por `; ` |
| `revisto_humano` | bool | `True` na versão final (sempre); `False` apenas se pré-preenchido por LLM e ainda não revisado |

## Convenções

- Encoding: UTF-8.
- Separador: `,` (CSV padrão); strings com vírgula são quote-encoded.
- Valores vazios: string vazia para texto, `n/a` para enums (quando o estudo não trata da dimensão).
- Datas: ISO 8601 (`YYYY-MM-DD`).
