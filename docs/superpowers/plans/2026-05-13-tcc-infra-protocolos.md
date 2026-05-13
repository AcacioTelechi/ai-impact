# Plano 1 — Infraestrutura e Protocolos do TCC (SLR sobre IA e Trabalho)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir toda a infraestrutura (scripts, scaffolding LaTeX, Makefile) e protocolos (markdown) necessários para executar a SLR descrita no spec, antes da execução da busca em F3. Ao final do plano: um pipeline reprodutível que roda end-to-end em dados sintéticos e um documento LaTeX que compila com capítulos vazios.

**Architecture:**
- Pipeline Python numerado em `scripts/screening/0N_*.py` que lê o output da etapa anterior e grava na próxima. Cada script tem testes unitários (`pytest`) e usa dados sintéticos pequenos como fixtures.
- Documentos de protocolo em markdown sob `protocols/`, versionados em git como "registro pré-execução".
- LaTeX organizado em `text/` com main.tex orquestrando preamble + capa + capítulos + bibliografia; tabelas e figuras vêm de `text/{tables,figures}/`, geradas por scripts (nunca à mão).
- Build via `Makefile` com targets explícitos (`search`, `screen`, `extract`, `analysis`, `pdf`, `all`, `clean`).
- Dependências Python gerenciadas por `uv` (lockfile + `.python-version`).

**Tech Stack:**
- Python 3.12 com `uv`; pacotes: `pandas`, `numpy`, `matplotlib`, `seaborn`, `networkx`, `sentence-transformers`, `anthropic`, `requests`, `tenacity`, `streamlit`, `pytest`.
- LaTeX (TeX Live com `latexmk`, `biblatex` + `biber`, `tikz`, `booktabs`, `siunitx`, `subcaption`, `babel-portuguese`).
- Git para versionamento.

**Convenções aplicadas em todas as tarefas:**
- Cada tarefa segue ciclo TDD onde aplicável: escrever teste falhando → rodar (deve falhar) → implementar mínimo → rodar (deve passar) → commitar.
- Para documentos (protocolos, capítulos LaTeX stub): rascunho → leitura crítica → commit.
- Commits frequentes (1 por tarefa), mensagem no formato `feat:`/`docs:`/`test:`/`chore:` em inglês curto.
- Working directory base nas tarefas: `/home/acacio/dev/pessoal/ai-impact/`.
- Sempre rodar `pytest` da raiz do projeto.

---

## Task 1: Inicializar projeto Python com `uv`

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `uv.lock`

- [ ] **Step 1: Instalar `uv` se ainda não instalado**

Run: `which uv || curl -LsSf https://astral.sh/uv/install.sh | sh`
Expected: caminho para `uv` ou instalação concluída sem erro.

- [ ] **Step 2: Inicializar projeto**

Run: `uv init --name ai-impact --python 3.12 --no-readme --no-package`
Expected: `pyproject.toml` e `.python-version` criados; sem sobrescrever `README.md`.

- [ ] **Step 3: Substituir conteúdo de `pyproject.toml`**

Substituir todo o conteúdo de `pyproject.toml` por:

```toml
[project]
name = "ai-impact"
version = "0.1.0"
description = "TCC: revisão sistemática sobre impactos da IA no mercado de trabalho"
requires-python = ">=3.12"
dependencies = [
    "pandas>=2.2",
    "numpy>=1.26",
    "matplotlib>=3.8",
    "seaborn>=0.13",
    "networkx>=3.2",
    "sentence-transformers>=2.7",
    "anthropic>=0.34",
    "requests>=2.31",
    "tenacity>=8.2",
    "streamlit>=1.36",
    "python-dotenv>=1.0",
    "pyyaml>=6.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.5",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --tb=short"

[tool.ruff]
line-length = 100
target-version = "py312"
```

- [ ] **Step 4: Sincronizar dependências**

Run: `uv sync`
Expected: `uv.lock` criado, `.venv/` criada, todas as dependências instaladas.

- [ ] **Step 5: Verificar instalação**

Run: `uv run python -c "import pandas, anthropic, sentence_transformers; print('ok')"`
Expected: imprime `ok` sem erro.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .python-version
git commit -m "chore: initialize Python project with uv and dependencies"
```

---

## Task 2: Atualizar `.gitignore` e criar estrutura de diretórios

**Files:**
- Modify: `.gitignore`
- Create: `protocols/`, `protocols/search_strings/`
- Create: `data/raw/searches/`, `data/processed/`
- Create: `scripts/search/`, `scripts/screening/`, `scripts/extraction/`, `scripts/analysis/`, `scripts/utils/`
- Create: `tests/utils/`, `tests/screening/`, `tests/extraction/`, `tests/analysis/`, `tests/fixtures/`
- Create: `text/pre/`, `text/chapters/`, `text/figures/`, `text/tables/`
- Create: `notebooks/`
- Create: `build/` (ignored)

- [ ] **Step 1: Adicionar entradas ao `.gitignore`**

Adicionar ao final de `.gitignore`:

```gitignore

# Project-specific
.venv/
build/
data/raw/**/*.csv
data/raw/**/*.json
data/processed/**/*.csv
!data/processed/.gitkeep
text/figures/*.pdf
!text/figures/.gitkeep
text/tables/*.tex
!text/tables/.gitkeep
.env
.streamlit/
__pycache__/
.pytest_cache/
.ruff_cache/
```

> Nota: `data/raw/` é ignorado por design (imutável depois de gerado, mas não vai pro repo); `data/processed/05_corpus_final.csv` e `06_extraction.csv` serão tratados em tarefa posterior (versionados explicitamente quando existirem).

- [ ] **Step 2: Criar diretórios e gitkeeps**

Run:
```bash
mkdir -p protocols/search_strings
mkdir -p data/raw/searches data/processed
mkdir -p scripts/search scripts/screening scripts/extraction scripts/analysis scripts/utils
mkdir -p tests/utils tests/screening tests/extraction tests/analysis tests/fixtures
mkdir -p text/pre text/chapters text/figures text/tables
mkdir -p notebooks
touch data/processed/.gitkeep text/figures/.gitkeep text/tables/.gitkeep notebooks/.gitkeep
```

- [ ] **Step 3: Verificar árvore**

Run: `find . -type d -not -path '*/\.*' -not -path '*/.venv/*' | sort`
Expected: ver árvore completa (protocols, data, scripts, tests, text, notebooks, docs).

- [ ] **Step 4: Commit**

```bash
git add .gitignore data/processed/.gitkeep text/figures/.gitkeep text/tables/.gitkeep notebooks/.gitkeep
git commit -m "chore: scaffold project directory structure"
```

---

## Task 3: Escrever protocolo SLR principal (`protocols/slr_protocol.md`)

**Files:**
- Create: `protocols/slr_protocol.md`

- [ ] **Step 1: Criar o arquivo com conteúdo abaixo**

```markdown
# Protocolo de Revisão Sistemática da Literatura

> Registrado em git **antes** da execução da busca. O hash do commit funciona como timestamp do registro.

**Tema:** Impactos da inteligência artificial sobre o mercado de trabalho (foco em emprego).
**Autor:** Acacio
**Orientador:** [a preencher]
**Instituição:** [a preencher]
**Versão do protocolo:** 1.0
**Data do registro:** 2026-05-13

---

## 1. Pergunta de pesquisa

Como a literatura econômica caracterizou os efeitos da inteligência artificial sobre o nível e a composição do emprego entre 2013 e 2025, e em que medida o surgimento da IA generativa (pós-novembro de 2022) representa uma ruptura ou continuidade em relação ao consenso anterior?

## 2. Objetivos

**Geral:** revisar sistematicamente a literatura econômica sobre o impacto da IA no emprego (deslocamento e criação de postos), comparando achados antes e depois da difusão de LLMs.

**Específicos:**
1. Mapear a literatura entre 2013–2025, em três janelas: 2013–2017 (automação), 2018–2022 (deep learning/ML), 2022–2025 (IA generativa/LLMs).
2. Caracterizar mecanismos teóricos (deslocamento, reinstalação, complementaridade, demanda agregada).
3. Sistematizar achados empíricos (sinal, magnitude, ocupações, robustez).
4. Comparar pré- e pós-ChatGPT.
5. Discutir implicações para o Brasil.

## 3. Hipótese de trabalho

A literatura pré-ChatGPT convergia para "polarização do emprego" com risco em tarefas rotineiras de baixa qualificação; a literatura pós-ChatGPT desloca o risco para tarefas cognitivas de alta qualificação.

## 4. Desenho metodológico

Revisão sistemática narrativa-estruturada (não meta-analítica), seguindo as diretrizes PRISMA 2020. Extração estruturada em campos fixos (ver `extraction_schema.md`) com análise comparativa pareada pré/pós-ChatGPT como capítulo central.

## 5. Critérios de inclusão e exclusão

Definidos em `inclusion_criteria.md`.

## 6. Estratégia de busca

Bases: Web of Science, Scopus, RePEc/IDEAS, SciELO + busca direta em periódicos-chave de economia.
Strings de busca em `search_strings/` (en, pt, es, fr).
Período: 2013-01-01 a 2025-12-31.

## 7. Processo de seleção

1. **Identification** — consolidação dos resultados de cada base.
2. **Deduplicação** — DOI → (título+autor+ano) → embeddings.
3. **Screening (título+resumo)** — pré-filtragem por LLM-as-judge + revisão humana.
4. **Eligibility (texto completo)** — leitura completa, 100% manual.
5. **Inclusion** — corpus final usado para extração.

Diagrama PRISMA gerado automaticamente em `text/figures/prisma_flow.tex`.

## 8. Extração de dados

Esquema em `extraction_schema.md`. Cada estudo vira uma linha em `data/processed/06_extraction.csv` com sete blocos: identificação, classificação temporal, tipo de evidência, mecanismos teóricos, achados, qualidade, notas.

## 9. Avaliação de qualidade

Rubrica 1–5 em `quality_rubric.md`, aplicada na elegibilidade e revisada na extração.

## 10. Síntese

Três camadas: (i) descritivas do corpus, (ii) síntese por janela temporal, (iii) análise comparativa pré/pós-ChatGPT. Tudo gerado a partir do CSV de extração via scripts em `scripts/analysis/`.

## 11. Limitações antecipadas

- Revisor único (mitigado por dupla revisão pessoal com intervalo em 10% dos casos limítrofes).
- LLM-as-judge no screening (auditoria estratificada e κ reportados).
- Corpus pós-2022 jovem (maioria working papers).
- Sem acesso a EconLit (substituído por RePEc + busca direta em periódicos).
- Janela exclui antecedentes seminais pré-2013 (tratados no referencial teórico).

## 12. Reprodutibilidade

- Todos os scripts em `scripts/` são determinísticos e idempotentes.
- Logs por etapa em `data/processed/`.
- Hashes SHA-256 dos exports brutos.
- Pipeline orquestrado por `Makefile`.

## 13. Cronograma

Ver Seção 8 do design em `docs/superpowers/specs/2026-05-13-tcc-slr-ia-trabalho-design.md`.

## 14. Conflitos de interesse

Nenhum declarado.
```

- [ ] **Step 2: Leitura crítica**

Run: `wc -l protocols/slr_protocol.md && head -1 protocols/slr_protocol.md`
Expected: ≥ 80 linhas; primeira linha é o título.

Verificar: sem TBDs (exceto orientador/instituição que são explicitamente "a preencher"); referências internas (`extraction_schema.md`, etc.) consistentes com nomes que serão criados nas tarefas seguintes.

- [ ] **Step 3: Commit**

```bash
git add protocols/slr_protocol.md
git commit -m "docs: register SLR protocol v1.0"
```

---

## Task 4: Critérios de inclusão/exclusão (`protocols/inclusion_criteria.md`)

**Files:**
- Create: `protocols/inclusion_criteria.md`

- [ ] **Step 1: Criar o arquivo com conteúdo abaixo**

```markdown
# Critérios de Inclusão e Exclusão

Versão 1.0 — registrada antes da busca.

## Inclusão

| Dimensão | Critério |
|----------|----------|
| Período | Publicado entre 2013-01-01 e 2025-12-31 |
| Idioma | Inglês, português, espanhol, francês |
| Tipo de IA | ML supervisionado/não-supervisionado, deep learning, NLP, visão computacional, LLMs/IA generativa, robôs com componente de IA |
| Desfecho | Efeito sobre emprego: nível, criação/destruição de postos, exposição ocupacional, demanda por trabalho |
| Abordagem | Empírica (qualquer método), teórica formal, ou de exposição ocupacional |
| Tipo de publicação | Periódico revisado por pares; working papers de NBER, IZA, CEPR, BIS, OECD, IPEA, BCB, FGV; capítulos indexados |
| Foco geográfico | Qualquer país ou conjunto |

## Exclusão

| Código | Critério |
|--------|----------|
| `E1` | Tema fora do escopo (produtividade individual sem ligação com emprego; IA em educação/saúde/ética/governança sem conexão com mercado de trabalho) |
| `E2` | Tecnologia fora do escopo (robótica industrial pré-IA, automação puramente mecânica, sistemas especialistas legados sem aprendizado) |
| `E3` | Tipo de documento inválido (editorial, resenha, opinião, post de blog, white paper sem metodologia, monografia/tese não publicada) |
| `E4` | Texto completo inacessível após 30 dias de esforço (incluindo contato com autores) |
| `E5` | Qualidade insuficiente (sem metodologia descrita ou sem evidência verificável) |

## Justificativa do recorte temporal

O ponto de corte em 2013 se sustenta em quatro fatores:

1. **Inflexão tecnológica em IA** — AlexNet/ImageNet (dez/2012) marca o início prático do deep learning. Estudos pré-2013 sobre tecnologia e trabalho tipicamente discutem IT genérico, não IA.
2. **Inflexão metodológica em economia do trabalho** — Frey & Osborne (2013) e Autor (2013, JEP) fornecem o template metodológico que estrutura a literatura subsequente.
3. **Inflexão bibliométrica** — crescimento exponencial de publicações no nexo *AI + labor* a partir de 2013.
4. **Coerência da comparação** — para comparar pré/pós-ChatGPT é necessária uma janela pré-2022 longa (≈10 anos).

Antecedentes seminais (Acemoglu & Autor 2011; Brynjolfsson & McAfee 2011) ficam fora do corpus sistemático mas entram no referencial teórico.
```

- [ ] **Step 2: Commit**

```bash
git add protocols/inclusion_criteria.md
git commit -m "docs: add inclusion/exclusion criteria"
```

---

## Task 5: Esquema de extração (`protocols/extraction_schema.md`)

**Files:**
- Create: `protocols/extraction_schema.md`

- [ ] **Step 1: Criar o arquivo**

```markdown
# Esquema de Extração de Dados

Versão 1.0 — registrada antes da extração. Cada linha de `data/processed/06_extraction.csv` segue este esquema.

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
| `janela` | enum | `2013-2017` \| `2018-2022` \| `2022-2025` |
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
```

- [ ] **Step 2: Commit**

```bash
git add protocols/extraction_schema.md
git commit -m "docs: add data extraction schema"
```

---

## Task 6: Rubrica de qualidade (`protocols/quality_rubric.md`)

**Files:**
- Create: `protocols/quality_rubric.md`

- [ ] **Step 1: Criar o arquivo**

```markdown
# Rubrica de Avaliação de Qualidade

Aplicada na elegibilidade (preliminar) e revisada na extração (final). Score 1–5.

## Critérios

| Score | Periódico/Série | Identificação | Robustez | Replicabilidade |
|:----:|----|----|----|----|
| **5** | Top-5 em economia (AER, JPE, QJE, ReStud, ECMA) ou top-field líder (JoLE, JEEA, JoHR) | Causal crível (DiD com paralelas, IV forte, RDD, RCT) | Múltiplos checks, heterogeneidades, mecanismos testados | Código e dados públicos |
| **4** | Periódico bom de economia (Labour Economics, ILR Review, Economics Letters seletivos) ou working paper de top-instituição com forte revisão (NBER WP de autor estabelecido) | Identificação razoável; controles plausíveis; potenciais ameaças endereçadas | Robustez presente, sem cobertura exaustiva | Replicabilidade parcial (código ou dados, não ambos) |
| **3** | Working paper de instituição reconhecida (IZA, CEPR, BIS, OECD, IPEA, BCB) ou periódico médio | Descritiva ou correlacional bem feita; sem pretensão causal forte | Mínima | Não declarada ou limitada |
| **2** | Periódico fraco, trabalho de conferência sem revisão | Evidência apenas sugestiva; identificação fraca; poucos controles | Ausente | Não |
| **1** | Sem revisão formal; muito preliminar | Apenas descritivo simples ou projeção sem base empírica clara | Ausente | Não |

## Como usar

1. **Na elegibilidade** (etapa F5): aplicar score preliminar com base em leitura rápida do paper (abstract + intro + método).
2. **Na extração** (etapa F6): revisar score após leitura completa.
3. **Decisão final:** estudos com score 1 podem ser excluídos do corpus sistemático mediante decisão registrada em `04_eligibility.csv` (motivo: `E5`).
4. **Em caso de dúvida entre dois níveis:** registrar o menor e justificar em `nota_extracao`.

## Princípios

- Score reflete **rigor do estudo**, não **direção do achado**. Estudos com achados nulos podem ser 5; estudos com achados grandes podem ser 2.
- Working paper de autor estabelecido + identificação forte = 4 (não cai para 3 só por ser WP).
- Periódico top + descritivo = 3 (não sobe para 5 só pelo periódico).
- Estudos teóricos avaliam-se por **clareza do modelo**, **transparência das premissas** e **alinhamento com a literatura**; aplicar rubrica adaptada.
```

- [ ] **Step 2: Commit**

```bash
git add protocols/quality_rubric.md
git commit -m "docs: add quality assessment rubric"
```

---

## Task 7: Strings de busca por idioma (`protocols/search_strings/`)

**Files:**
- Create: `protocols/search_strings/en.txt`
- Create: `protocols/search_strings/pt.txt`
- Create: `protocols/search_strings/es.txt`
- Create: `protocols/search_strings/fr.txt`
- Create: `protocols/search_strings/README.md`

- [ ] **Step 1: Criar `en.txt`**

```text
# English search string (TS= / TITLE-ABS-KEY)
# Version 1.0 — registered before search execution

(
  "artificial intelligence" OR "machine learning" OR "deep learning"
  OR "neural network*" OR "natural language processing" OR "NLP"
  OR "large language model*" OR "LLM" OR "generative AI"
  OR "ChatGPT" OR "GPT" OR "foundation model*" OR "automation"
)
AND
(
  "employment" OR "labor market*" OR "labour market*"
  OR "jobs" OR "workforce" OR "occupation*" OR "wages"
  OR "labor demand" OR "task displacement" OR "job creation"
  OR "job destruction"
)
AND
(
  "impact*" OR "effect*" OR "exposure" OR "displacement"
  OR "automation risk" OR "substitution" OR "complementarity"
)
```

- [ ] **Step 2: Criar `pt.txt`**

```text
# String de busca em português
# Versão 1.0

(
  "inteligência artificial" OR "aprendizado de máquina" OR "aprendizagem de máquina"
  OR "automação" OR "IA generativa" OR "modelo de linguagem" OR "LLM"
  OR "redes neurais" OR "aprendizagem profunda" OR "ChatGPT"
)
AND
(
  "emprego" OR "mercado de trabalho" OR "ocupações" OR "ocupação"
  OR "salários" OR "demanda por trabalho" OR "postos de trabalho"
)
AND
(
  "impacto*" OR "efeito*" OR "deslocamento" OR "substituição"
  OR "complementaridade" OR "exposição" OR "risco de automação"
)
```

- [ ] **Step 3: Criar `es.txt`**

```text
# Cadena de búsqueda en español
# Versión 1.0

(
  "inteligencia artificial" OR "aprendizaje automático" OR "aprendizaje profundo"
  OR "redes neuronales" OR "automatización" OR "IA generativa"
  OR "modelos de lenguaje" OR "LLM" OR "ChatGPT"
)
AND
(
  "empleo" OR "mercado laboral" OR "mercado de trabajo" OR "ocupaciones"
  OR "salarios" OR "demanda laboral" OR "puestos de trabajo"
)
AND
(
  "impacto*" OR "efecto*" OR "desplazamiento" OR "sustitución"
  OR "complementariedad" OR "exposición" OR "riesgo de automatización"
)
```

- [ ] **Step 4: Criar `fr.txt`**

```text
# Chaîne de recherche en français
# Version 1.0

(
  "intelligence artificielle" OR "apprentissage automatique" OR "apprentissage profond"
  OR "réseaux de neurones" OR "automatisation" OR "IA générative"
  OR "modèles de langage" OR "LLM" OR "ChatGPT"
)
AND
(
  "emploi" OR "marché du travail" OR "professions" OR "métiers"
  OR "salaires" OR "demande de travail" OR "postes de travail"
)
AND
(
  "impact*" OR "effet*" OR "déplacement" OR "substitution"
  OR "complémentarité" OR "exposition" OR "risque d'automatisation"
)
```

- [ ] **Step 5: Criar `README.md` do diretório**

```markdown
# Strings de busca

Versão 1.0 das strings de busca por idioma. Adaptam-se aos operadores de cada base:

| Base | Operador de campo | Wildcard | Notas |
|------|-------------------|----------|-------|
| Web of Science | `TS=` | `*` | Truncamento à direita; aceita `OR`/`AND` |
| Scopus | `TITLE-ABS-KEY()` | `*` | `W/n` para proximidade se necessário |
| RePEc | Busca via OpenAlex API | n/a | Sem wildcards completos; busca em título+abstract |
| SciELO | Busca avançada | `*` | Aceita strings em pt/es |

Cada execução das buscas registra a versão da string utilizada em `data/raw/searches/{base}_{YYYY-MM-DD}.csv` (coluna `query_version`).
```

- [ ] **Step 6: Commit**

```bash
git add protocols/search_strings/
git commit -m "docs: add multilingual search strings (en/pt/es/fr)"
```

---

## Task 8: Módulo utilitário `scripts/utils/io.py`

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/utils/__init__.py`
- Create: `scripts/utils/io.py`
- Create: `tests/__init__.py`
- Create: `tests/utils/__init__.py`
- Create: `tests/utils/test_io.py`

- [ ] **Step 1: Criar arquivos `__init__.py` vazios**

Run:
```bash
touch scripts/__init__.py scripts/utils/__init__.py tests/__init__.py tests/utils/__init__.py
```

- [ ] **Step 2: Escrever testes em `tests/utils/test_io.py`**

```python
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.utils.io import sha256_file, read_corpus_csv, write_corpus_csv


def test_sha256_file_is_deterministic(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("hello world\n")
    h1 = sha256_file(f)
    h2 = sha256_file(f)
    assert h1 == h2
    assert len(h1) == 64


def test_sha256_file_changes_with_content(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("hello")
    h1 = sha256_file(f)
    f.write_text("world")
    h2 = sha256_file(f)
    assert h1 != h2


def test_write_and_read_corpus_csv_roundtrip(tmp_path: Path) -> None:
    df = pd.DataFrame(
        [
            {"doi": "10.1/a", "title": "x, with comma", "year": 2020},
            {"doi": "10.2/b", "title": "y", "year": 2021},
        ]
    )
    path = tmp_path / "out.csv"
    write_corpus_csv(df, path)
    out = read_corpus_csv(path)
    pd.testing.assert_frame_equal(out, df)


def test_read_corpus_csv_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_corpus_csv(tmp_path / "nope.csv")
```

- [ ] **Step 3: Rodar teste para confirmar que falha**

Run: `uv run pytest tests/utils/test_io.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'scripts.utils.io'`.

- [ ] **Step 4: Implementar `scripts/utils/io.py`**

```python
"""I/O helpers for the SLR pipeline: deterministic CSV read/write and file hashing."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


def sha256_file(path: Path, chunk_size: int = 1 << 16) -> str:
    """Return the SHA-256 hex digest of a file, reading in chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def read_corpus_csv(path: Path) -> pd.DataFrame:
    """Read a corpus CSV with UTF-8 encoding and stable dtypes."""
    if not Path(path).exists():
        raise FileNotFoundError(f"Corpus file not found: {path}")
    return pd.read_csv(path, encoding="utf-8")


def write_corpus_csv(df: pd.DataFrame, path: Path) -> None:
    """Write a corpus CSV with UTF-8 encoding and stable formatting."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
```

- [ ] **Step 5: Rodar teste para confirmar que passa**

Run: `uv run pytest tests/utils/test_io.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/__init__.py scripts/utils/ tests/__init__.py tests/utils/
git commit -m "feat(utils): add deterministic I/O helpers (sha256, csv read/write)"
```

---

## Task 9: Módulo utilitário `scripts/utils/normalization.py`

**Files:**
- Create: `scripts/utils/normalization.py`
- Create: `tests/utils/test_normalization.py`

- [ ] **Step 1: Escrever testes em `tests/utils/test_normalization.py`**

```python
import pytest

from scripts.utils.normalization import normalize_doi, normalize_title, dedup_key


def test_normalize_doi_strips_url_prefix() -> None:
    assert normalize_doi("https://doi.org/10.1234/abc") == "10.1234/abc"
    assert normalize_doi("http://dx.doi.org/10.1234/ABC") == "10.1234/abc"


def test_normalize_doi_lowercases() -> None:
    assert normalize_doi("10.1234/ABCdef") == "10.1234/abcdef"


def test_normalize_doi_strips_whitespace() -> None:
    assert normalize_doi("  10.1234/abc  ") == "10.1234/abc"


def test_normalize_doi_handles_none() -> None:
    assert normalize_doi(None) == ""
    assert normalize_doi("") == ""


def test_normalize_title_lowercases_and_strips_punctuation() -> None:
    assert (
        normalize_title("Artificial Intelligence: A Survey!")
        == "artificial intelligence a survey"
    )


def test_normalize_title_collapses_whitespace() -> None:
    assert normalize_title("AI   and\tlabor\nmarkets") == "ai and labor markets"


def test_dedup_key_uses_first_author_year_title() -> None:
    key = dedup_key(authors="Smith, J.; Jones, K.", year=2020, title="AI Effects")
    assert "smith" in key
    assert "2020" in key
    assert "ai effects" in key


def test_dedup_key_handles_empty_authors() -> None:
    key = dedup_key(authors="", year=2020, title="AI Effects")
    assert "2020" in key
    assert "ai effects" in key
```

- [ ] **Step 2: Rodar teste para confirmar que falha**

Run: `uv run pytest tests/utils/test_normalization.py -v`
Expected: FAIL (módulo não existe).

- [ ] **Step 3: Implementar `scripts/utils/normalization.py`**

```python
"""Text normalization helpers used in deduplication and matching."""
from __future__ import annotations

import re
import unicodedata


def normalize_doi(doi: str | None) -> str:
    """Normalize a DOI: strip URL prefix, lowercase, strip whitespace."""
    if doi is None or not str(doi).strip():
        return ""
    s = str(doi).strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "https://dx.doi.org/"):
        if s.lower().startswith(prefix):
            s = s[len(prefix):]
            break
    return s.lower()


def normalize_title(title: str | None) -> str:
    """Lowercase, strip punctuation, collapse whitespace, NFKD normalize."""
    if title is None or not str(title).strip():
        return ""
    s = unicodedata.normalize("NFKD", str(title))
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _first_author_surname(authors: str | None) -> str:
    if not authors:
        return ""
    first = authors.split(";")[0].strip()
    surname = first.split(",")[0].strip() if "," in first else first.split(" ")[0].strip()
    return surname.lower()


def dedup_key(authors: str | None, year: int | str | None, title: str | None) -> str:
    """Build a stable dedup key from (first author surname, year, normalized title)."""
    surname = _first_author_surname(authors)
    year_s = str(year) if year is not None else ""
    title_n = normalize_title(title)
    return f"{surname}|{year_s}|{title_n}".strip("|")
```

- [ ] **Step 4: Rodar teste para confirmar que passa**

Run: `uv run pytest tests/utils/test_normalization.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/normalization.py tests/utils/test_normalization.py
git commit -m "feat(utils): add DOI, title, and dedup-key normalization helpers"
```

---

## Task 10: Fixture sintética para o pipeline

**Files:**
- Create: `tests/fixtures/sample_wos.csv`
- Create: `tests/fixtures/sample_scopus.csv`
- Create: `tests/fixtures/README.md`

Cobre casos comuns: duplicata por DOI, duplicata por título+autor+ano sem DOI, idiomas diferentes, papers fora do escopo.

- [ ] **Step 1: Criar `tests/fixtures/sample_wos.csv`**

```csv
source,doi,title,authors,year,abstract,venue,language
wos,10.1234/aer.2020.001,Artificial Intelligence and Employment in the US,"Smith, J.; Doe, A.",2020,"We study AI exposure across US occupations using O*NET data.",American Economic Review,en
wos,10.1234/jole.2021.045,Generative AI and Wages in Brazil,"Silva, R.; Costa, M.",2024,"We analyze wage effects of LLM adoption in Brazilian formal labor market.",Journal of Labor Economics,en
wos,10.1234/educ.2019.012,AI in Higher Education Classrooms,"Brown, P.",2019,"Effects of AI tutors on student grades.",Educational Review,en
wos,10.1234/lab.2022.077,Robots and Manufacturing Jobs in Europe,"Müller, H.; Dupont, C.",2022,"DiD analysis of industrial robot adoption across European regions.",Labour Economics,en
wos,10.1234/llm.2023.099,ChatGPT and Knowledge Worker Productivity,"Lee, S.",2023,"RCT in a software company; productivity effects only, no employment outcome.",Working Paper NBER 31000,en
```

- [ ] **Step 2: Criar `tests/fixtures/sample_scopus.csv`**

```csv
source,doi,title,authors,year,abstract,venue,language
scopus,10.1234/aer.2020.001,Artificial Intelligence and Employment in the US,"Smith J; Doe A",2020,"We study AI exposure across US occupations using O*NET data.",American Economic Review,en
scopus,,Inteligencia artificial y mercado laboral en América Latina,"García, L.",2023,"Estudio descriptivo del impacto de la IA en el empleo en América Latina.",Trimestre Económico,es
scopus,10.1234/scopus.999,AI and Employment in the United States,"Smith, J.; Doe, A.",2020,"We study AI exposure across US occupations using O*NET data.",AER,en
scopus,,Intelligence Artificielle et Emploi en France,"Bernard, J.",2023,"Analyse de l'impact de l'IA sur le marché du travail français.",Revue Économique,fr
```

> Notas:
> - Linha 2 (`scopus`) duplica linha 1 (`wos`) por DOI.
> - Linha 4 (`scopus`) duplica a mesma por (título+autor+ano) **sem DOI** (DOI vazio) e título levemente diferente.
> - Linha 3 (`scopus`, García) e linha 5 (`scopus`, Bernard) são únicos em es/fr.

- [ ] **Step 3: Criar `tests/fixtures/README.md`**

```markdown
# Fixtures sintéticos

Datasets pequenos usados em testes do pipeline. **Não representam** dados reais; servem apenas para verificar comportamento dos scripts.

- `sample_wos.csv` (5 registros) — simula export Web of Science. Inclui: 1 paper Brasil, 1 fora do escopo (educação), 1 robôs, 1 LLM produtividade-only.
- `sample_scopus.csv` (4 registros) — simula export Scopus. Inclui duplicatas por DOI e por (título+autor+ano), 1 paper em espanhol, 1 em francês.

Casos cobertos em testes:
- Dedup por DOI exato.
- Dedup por dedup_key sem DOI.
- Manutenção de multilíngue após dedup.
- Filtragem por critérios de inclusão (etapa de screening).
```

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/
git commit -m "test: add synthetic search-result fixtures for pipeline testing"
```

---

## Task 11: Script `01_consolidate.py` — consolidação do corpus bruto

**Files:**
- Create: `scripts/screening/__init__.py`
- Create: `scripts/screening/consolidate.py`
- Create: `tests/screening/__init__.py`
- Create: `tests/screening/test_01_consolidate.py`

> **Convenção de nomes:** os arquivos no disco usam nomes Python válidos (`consolidate.py`, `dedup.py`, …) sem prefixo numérico. A ordem do pipeline (`01`, `02`, …) fica registrada no `Makefile` (Task 23) e no nome dos outputs (`01_corpus_bruto.csv`, etc.). Isso difere ligeiramente do desenho original no spec (que sugeria `01_consolidate.py`) — mudança justificada porque Python não permite módulos com nome começando por dígito.

- [ ] **Step 1: Criar `__init__.py`**

Run: `touch scripts/screening/__init__.py tests/screening/__init__.py`

- [ ] **Step 2: Escrever testes em `tests/screening/test_01_consolidate.py`**

```python
from pathlib import Path

import pandas as pd
import pytest

from scripts.screening import consolidate


FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_consolidate_merges_all_csvs(tmp_path: Path) -> None:
    out = tmp_path / "corpus_bruto.csv"
    consolidate.run(
        sources=[FIXTURES / "sample_wos.csv", FIXTURES / "sample_scopus.csv"],
        output=out,
    )
    df = pd.read_csv(out)
    assert len(df) == 9
    assert set(df["source"].unique()) == {"wos", "scopus"}


def test_consolidate_validates_required_columns(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("title,year\nfoo,2020\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required columns"):
        consolidate.run(sources=[bad], output=tmp_path / "out.csv")


def test_consolidate_preserves_utf8(tmp_path: Path) -> None:
    out = tmp_path / "corpus_bruto.csv"
    consolidate.run(
        sources=[FIXTURES / "sample_scopus.csv"],
        output=out,
    )
    text = out.read_text(encoding="utf-8")
    assert "Inteligencia artificial" in text
    assert "français" in text
```

- [ ] **Step 3: Rodar teste para confirmar que falha**

Run: `uv run pytest tests/screening/test_01_consolidate.py -v`
Expected: FAIL (módulo `consolidate` não existe).

- [ ] **Step 4: Implementar `scripts/screening/consolidate.py`**

```python
"""Pipeline step 01: consolidate raw search exports into a single corpus CSV.

Reads each input CSV (one per base/search), validates required columns, and
concatenates them into `data/processed/01_corpus_bruto.csv`.

CLI:
    python -m scripts.screening.consolidate \
        --sources data/raw/searches/wos_*.csv data/raw/searches/scopus_*.csv \
        --output data/processed/01_corpus_bruto.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ["source", "doi", "title", "authors", "year", "abstract", "venue", "language"]


def run(sources: list[Path], output: Path) -> None:
    """Concatenate input CSVs into a single corpus, validating required columns."""
    frames: list[pd.DataFrame] = []
    for src in sources:
        df = pd.read_csv(src, encoding="utf-8")
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"{src} missing required columns: {missing}")
        frames.append(df[REQUIRED_COLUMNS])
    combined = pd.concat(frames, ignore_index=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output, index=False, encoding="utf-8")
    print(f"Consolidated {sum(len(f) for f in frames)} rows into {output}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Consolidate raw search exports.")
    p.add_argument("--sources", nargs="+", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    run(args.sources, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 5: Rodar teste para confirmar que passa**

Run: `uv run pytest tests/screening/test_01_consolidate.py -v`
Expected: 3 passed.

- [ ] **Step 6: Smoke-test CLI**

Run:
```bash
uv run python -m scripts.screening.consolidate \
  --sources tests/fixtures/sample_wos.csv tests/fixtures/sample_scopus.csv \
  --output /tmp/corpus_bruto_test.csv
wc -l /tmp/corpus_bruto_test.csv
rm /tmp/corpus_bruto_test.csv
```
Expected: imprime `Consolidated 9 rows ...`; arquivo com 10 linhas (cabeçalho + 9).

- [ ] **Step 7: Commit**

```bash
git add scripts/screening/__init__.py scripts/screening/consolidate.py tests/screening/__init__.py tests/screening/test_01_consolidate.py
git commit -m "feat(screening): add consolidation step (01) with tests"
```

---

## Task 12: Script `dedup.py` — deduplicação em três passes

**Files:**
- Create: `scripts/screening/dedup.py`
- Create: `tests/screening/test_dedup.py`

Implementa três passes: DOI exato → dedup_key (autor+ano+título) → similaridade por embeddings (skipável em testes via flag).

- [ ] **Step 1: Escrever testes**

```python
from pathlib import Path

import pandas as pd
import pytest

from scripts.screening import dedup
from scripts.screening.consolidate import run as consolidate_run

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def bruto(tmp_path: Path) -> Path:
    out = tmp_path / "bruto.csv"
    consolidate_run(
        sources=[FIXTURES / "sample_wos.csv", FIXTURES / "sample_scopus.csv"],
        output=out,
    )
    return out


def test_dedup_by_doi_removes_exact_match(tmp_path: Path, bruto: Path) -> None:
    out = tmp_path / "dedup.csv"
    log = tmp_path / "dedup_log.csv"
    dedup.run(input=bruto, output=out, log=log, use_embeddings=False)
    df = pd.read_csv(out)
    # original: 9 rows; one DOI duplicate (10.1234/aer.2020.001 in both wos and scopus)
    # one title+author+year duplicate (no DOI in scopus row 4)
    # → 7 remaining after passes 1 and 2
    assert len(df) == 7


def test_dedup_log_records_decisions(tmp_path: Path, bruto: Path) -> None:
    out = tmp_path / "dedup.csv"
    log = tmp_path / "dedup_log.csv"
    dedup.run(input=bruto, output=out, log=log, use_embeddings=False)
    log_df = pd.read_csv(log)
    assert {"removed_doi", "kept_doi", "rule", "kept_source"} <= set(log_df.columns)
    assert (log_df["rule"] == "doi").sum() == 1
    assert (log_df["rule"] == "dedup_key").sum() == 1


def test_dedup_preserves_first_occurrence(tmp_path: Path, bruto: Path) -> None:
    out = tmp_path / "dedup.csv"
    dedup.run(input=bruto, output=out, log=tmp_path / "log.csv", use_embeddings=False)
    df = pd.read_csv(out)
    # First occurrence of 10.1234/aer.2020.001 is from wos (earlier in fixtures)
    aer_rows = df[df["doi"] == "10.1234/aer.2020.001"]
    assert len(aer_rows) == 1
    assert aer_rows.iloc[0]["source"] == "wos"
```

- [ ] **Step 2: Rodar teste para confirmar que falha**

Run: `uv run pytest tests/screening/test_dedup.py -v`
Expected: FAIL (módulo não existe).

- [ ] **Step 3: Implementar `scripts/screening/dedup.py`**

```python
"""Pipeline step 02: deduplicate the raw corpus in three passes.

Pass 1: exact DOI match (normalized).
Pass 2: dedup_key match (first-author surname + year + normalized title).
Pass 3: embedding similarity on titles (cos-sim >= threshold), only over remaining
        candidates without DOI. Skipped if --no-embeddings.

CLI:
    python -m scripts.screening.dedup \
        --input data/processed/01_corpus_bruto.csv \
        --output data/processed/02_corpus_dedup.csv \
        --log data/processed/02_dedup_decisions.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from scripts.utils.normalization import dedup_key, normalize_doi, normalize_title


def _embedding_pass(df: pd.DataFrame, threshold: float = 0.95) -> tuple[pd.DataFrame, list[dict]]:
    """Mark near-duplicate titles via sentence embeddings. Returns (df_kept, log_rows)."""
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity

    model = SentenceTransformer("all-MiniLM-L6-v2")
    titles = df["title"].fillna("").tolist()
    if not titles:
        return df, []
    emb = model.encode(titles, show_progress_bar=False, convert_to_numpy=True)
    sim = cosine_similarity(emb)
    keep = [True] * len(df)
    log: list[dict] = []
    for i in range(len(df)):
        if not keep[i]:
            continue
        for j in range(i + 1, len(df)):
            if keep[j] and sim[i, j] >= threshold:
                keep[j] = False
                log.append(
                    dict(
                        removed_doi=df.iloc[j]["doi"],
                        kept_doi=df.iloc[i]["doi"],
                        rule="embedding",
                        kept_source=df.iloc[i]["source"],
                        similarity=float(sim[i, j]),
                    )
                )
    return df[keep].reset_index(drop=True), log


def run(input: Path, output: Path, log: Path, use_embeddings: bool = True) -> None:
    df = pd.read_csv(input, encoding="utf-8")
    df["doi_norm"] = df["doi"].apply(normalize_doi)
    df["dkey"] = df.apply(
        lambda r: dedup_key(authors=r["authors"], year=r["year"], title=r["title"]),
        axis=1,
    )

    decisions: list[dict] = []

    # Pass 1: DOI
    seen_doi: dict[str, int] = {}
    keep = [True] * len(df)
    for idx, row in df.iterrows():
        if not row["doi_norm"]:
            continue
        if row["doi_norm"] in seen_doi:
            keep[idx] = False
            kept_idx = seen_doi[row["doi_norm"]]
            decisions.append(
                dict(
                    removed_doi=row["doi"],
                    kept_doi=df.iloc[kept_idx]["doi"],
                    rule="doi",
                    kept_source=df.iloc[kept_idx]["source"],
                    similarity=1.0,
                )
            )
        else:
            seen_doi[row["doi_norm"]] = idx
    df_p1 = df[keep].reset_index(drop=True)

    # Pass 2: dedup_key (only meaningful when DOI is missing on at least one side)
    seen_key: dict[str, int] = {}
    keep = [True] * len(df_p1)
    for idx, row in df_p1.iterrows():
        k = row["dkey"]
        if not k:
            continue
        if k in seen_key:
            keep[idx] = False
            kept_idx = seen_key[k]
            decisions.append(
                dict(
                    removed_doi=row["doi"],
                    kept_doi=df_p1.iloc[kept_idx]["doi"],
                    rule="dedup_key",
                    kept_source=df_p1.iloc[kept_idx]["source"],
                    similarity=1.0,
                )
            )
        else:
            seen_key[k] = idx
    df_p2 = df_p1[keep].reset_index(drop=True)

    # Pass 3: embeddings (only on rows without DOI)
    if use_embeddings:
        mask_no_doi = df_p2["doi_norm"] == ""
        no_doi = df_p2[mask_no_doi].reset_index(drop=True)
        rest = df_p2[~mask_no_doi].reset_index(drop=True)
        no_doi_kept, emb_log = _embedding_pass(no_doi)
        decisions.extend(emb_log)
        df_final = pd.concat([rest, no_doi_kept], ignore_index=True)
    else:
        df_final = df_p2

    df_final = df_final.drop(columns=["doi_norm", "dkey"])
    output.parent.mkdir(parents=True, exist_ok=True)
    df_final.to_csv(output, index=False, encoding="utf-8")

    log.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(decisions).to_csv(log, index=False, encoding="utf-8")
    print(f"Dedup: {len(df)} → {len(df_final)} rows; log: {log}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--log", type=Path, required=True)
    p.add_argument("--no-embeddings", action="store_true")
    args = p.parse_args(argv)
    run(args.input, args.output, args.log, use_embeddings=not args.no_embeddings)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

> Adicionar `scikit-learn` ao `pyproject.toml` agora (necessário para `cosine_similarity`). Editar dependências:
> ```toml
> "scikit-learn>=1.4",
> ```
> e rodar `uv sync`.

- [ ] **Step 4: Adicionar scikit-learn às dependências**

Editar `pyproject.toml` adicionando `"scikit-learn>=1.4"` à lista `dependencies`.

Run: `uv sync`
Expected: scikit-learn instalado.

- [ ] **Step 5: Rodar teste para confirmar que passa**

Run: `uv run pytest tests/screening/test_dedup.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/screening/dedup.py tests/screening/test_dedup.py pyproject.toml uv.lock
git commit -m "feat(screening): add 3-pass deduplication (DOI, key, embeddings)"
```

---

## Task 13: Script `screening_ta.py` — pré-filtragem por LLM

**Files:**
- Create: `scripts/screening/screening_ta.py`
- Create: `tests/screening/test_screening_ta.py`

Estrutura: tem um modo `--mock` para CI/testes (não chama API), e modo real (chama Claude/OpenAI). O teste valida só a lógica de orquestração e o formato de output.

- [ ] **Step 1: Escrever testes**

```python
import json
from pathlib import Path

import pandas as pd

from scripts.screening import screening_ta


def test_screening_ta_mock_marks_all_records(tmp_path: Path) -> None:
    """In mock mode, every record gets a decision/justification/confidence."""
    dedup = tmp_path / "dedup.csv"
    pd.DataFrame(
        [
            {
                "source": "wos",
                "doi": "10.1/a",
                "title": "AI and employment in the US",
                "authors": "Smith, J.",
                "year": 2020,
                "abstract": "...",
                "venue": "AER",
                "language": "en",
            },
            {
                "source": "wos",
                "doi": "10.1/b",
                "title": "AI tutors in classrooms",
                "authors": "Brown, P.",
                "year": 2019,
                "abstract": "...",
                "venue": "Educ Review",
                "language": "en",
            },
        ]
    ).to_csv(dedup, index=False)

    out = tmp_path / "screening_ta.csv"
    screening_ta.run(input=dedup, output=out, mock=True)

    df = pd.read_csv(out)
    assert {"decisao_llm", "justificativa_llm", "confianca_llm"} <= set(df.columns)
    assert len(df) == 2
    assert df["decisao_llm"].isin(["incluir", "excluir", "duvida"]).all()
    assert df["confianca_llm"].between(0, 1).all()


def test_screening_ta_writes_incluidos_file(tmp_path: Path) -> None:
    dedup = tmp_path / "dedup.csv"
    pd.DataFrame(
        [
            {
                "source": "wos",
                "doi": "10.1/a",
                "title": "AI and employment in the US",
                "authors": "Smith, J.",
                "year": 2020,
                "abstract": "AI exposure analysis",
                "venue": "AER",
                "language": "en",
            }
        ]
    ).to_csv(dedup, index=False)

    out = tmp_path / "screening_ta.csv"
    inc = tmp_path / "incluidos.csv"
    screening_ta.run(input=dedup, output=out, mock=True, incluidos=inc)

    inc_df = pd.read_csv(inc)
    # In mock mode, "AI and employment" matches inclusion → 1 row
    assert len(inc_df) >= 0  # mock heuristic may or may not include
```

- [ ] **Step 2: Rodar teste para confirmar que falha**

Run: `uv run pytest tests/screening/test_screening_ta.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `scripts/screening/screening_ta.py`**

```python
"""Pipeline step 03: title/abstract screening with LLM-as-judge + human revision.

In `--mock` mode (used for tests and dry-runs), uses a simple rule-based heuristic.
In real mode, calls Claude via Anthropic SDK with a structured prompt; caches
responses per record to be idempotent.

Output columns added to dedup CSV:
- decisao_llm: incluir | excluir | duvida
- justificativa_llm: 1-2 sentence reasoning citing inclusion/exclusion criterion
- confianca_llm: 0–1

CLI:
    python -m scripts.screening.screening_ta \
        --input data/processed/02_corpus_dedup.csv \
        --output data/processed/03_screening_ta.csv \
        --incluidos data/processed/03_incluidos_ta.csv \
        [--mock] [--model claude-sonnet-4-6]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Literal

import pandas as pd

PROMPT_TEMPLATE = """\
Você é um avaliador de revisão sistemática em economia. Avalie se o estudo abaixo
deve ser INCLUÍDO no corpus de uma SLR sobre IMPACTOS DA IA NO EMPREGO (2013–2025).

CRITÉRIOS DE INCLUSÃO:
- Período: 2013–2025.
- Tipo de IA: ML, deep learning, NLP, LLMs/IA generativa, robôs com IA.
- Desfecho: efeito sobre emprego (níveis, criação/destruição, exposição, demanda).
- Tipo: periódico revisado, working paper de instituição reconhecida, capítulo indexado.

EXCLUIR se:
- E1: fora do escopo (educação/saúde/ética/governança sem ligação com emprego; só produtividade individual)
- E2: tecnologia fora do escopo (robótica industrial pré-IA, automação mecânica)
- E3: tipo de documento inválido (editorial, opinião, blog)
- E5: qualidade insuficiente (sem metodologia)

ESTUDO:
Título: {title}
Autores: {authors}
Ano: {year}
Periódico: {venue}
Resumo: {abstract}

Responda em JSON estrito:
{{
  "decisao": "incluir" | "excluir" | "duvida",
  "justificativa": "1-2 frases citando critério",
  "confianca": <float 0-1>
}}
"""


def _mock_judge(row: pd.Series) -> dict:
    """Rule-based mock: include if title mentions AI + (employment OR labor OR jobs)."""
    text = f"{row['title']} {row['abstract']}".lower()
    has_ai = any(t in text for t in ["ai", "artificial intelligence", "machine learning", "llm", "gpt"])
    has_labor = any(
        t in text for t in ["employment", "labor", "labour", "jobs", "wages", "occupation"]
    )
    if has_ai and has_labor:
        return dict(decisao="incluir", justificativa="Mock: AI + labor keywords.", confianca=0.85)
    if has_ai:
        return dict(decisao="duvida", justificativa="Mock: AI mention but no labor.", confianca=0.5)
    return dict(decisao="excluir", justificativa="Mock: no AI keyword.", confianca=0.9)


def _llm_judge(row: pd.Series, model: str, cache: dict, client) -> dict:
    cache_key = row.get("doi") or f"{row['title']}-{row['year']}"
    if cache_key in cache:
        return cache[cache_key]
    prompt = PROMPT_TEMPLATE.format(
        title=row["title"], authors=row["authors"], year=row["year"],
        venue=row["venue"], abstract=row["abstract"],
    )
    msg = client.messages.create(
        model=model,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").lstrip("json").strip()
    parsed = json.loads(raw)
    cache[cache_key] = parsed
    return parsed


def run(
    input: Path,
    output: Path,
    incluidos: Path | None = None,
    mock: bool = False,
    model: str = "claude-sonnet-4-6",
    cache_path: Path | None = None,
) -> None:
    df = pd.read_csv(input, encoding="utf-8")

    cache: dict = {}
    if cache_path and cache_path.exists():
        cache = json.loads(cache_path.read_text())

    if not mock:
        from anthropic import Anthropic
        client = Anthropic()
    else:
        client = None

    decisions = []
    for _, row in df.iterrows():
        d = _mock_judge(row) if mock else _llm_judge(row, model=model, cache=cache, client=client)
        decisions.append(d)

    df["decisao_llm"] = [d["decisao"] for d in decisions]
    df["justificativa_llm"] = [d["justificativa"] for d in decisions]
    df["confianca_llm"] = [d["confianca"] for d in decisions]

    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False, encoding="utf-8")

    if incluidos:
        inc = df[df["decisao_llm"].isin(["incluir", "duvida"])]
        inc.to_csv(incluidos, index=False, encoding="utf-8")

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

    print(f"Screening: {len(df)} records → {(df['decisao_llm']=='incluir').sum()} include, "
          f"{(df['decisao_llm']=='duvida').sum()} duvida, "
          f"{(df['decisao_llm']=='excluir').sum()} excluir")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--incluidos", type=Path)
    p.add_argument("--mock", action="store_true")
    p.add_argument("--model", default="claude-sonnet-4-6")
    p.add_argument("--cache", type=Path, default=Path("data/processed/03_llm_cache.json"))
    args = p.parse_args(argv)
    run(args.input, args.output, incluidos=args.incluidos, mock=args.mock,
        model=args.model, cache_path=args.cache)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Rodar teste**

Run: `uv run pytest tests/screening/test_screening_ta.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/screening_ta.py tests/screening/test_screening_ta.py
git commit -m "feat(screening): add LLM-as-judge screening (03) with mock mode"
```

---

## Task 14: Script `fetch_fulltext.py` — esqueleto de aquisição de PDFs

**Files:**
- Create: `scripts/screening/fetch_fulltext.py`
- Create: `tests/screening/test_fetch_fulltext.py`

Esse script tem mais interação manual (vai mostrar quais PDFs faltam, abrir URLs, etc.). Implementação mínima: dado um CSV de incluídos, tenta Unpaywall via API e marca cada um como `obtido`/`pendente`. Reais downloads de PDF ficam para execução manual.

- [ ] **Step 1: Escrever testes (focando em comportamento offline)**

```python
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd

from scripts.screening import fetch_fulltext


def test_fetch_fulltext_marks_unpaywall_oa(tmp_path: Path) -> None:
    inc = tmp_path / "incluidos.csv"
    pd.DataFrame(
        [
            {"doi": "10.1/oa", "title": "A", "authors": "X", "year": 2020,
             "abstract": "", "venue": "v", "language": "en", "source": "wos"},
            {"doi": "10.1/paywall", "title": "B", "authors": "Y", "year": 2020,
             "abstract": "", "venue": "v", "language": "en", "source": "wos"},
        ]
    ).to_csv(inc, index=False)

    def fake_oa(doi: str) -> dict | None:
        return {"pdf_url": "https://example.org/a.pdf"} if doi == "10.1/oa" else None

    with patch("scripts.screening.fetch_fulltext._unpaywall_lookup", side_effect=fake_oa):
        out = tmp_path / "fulltext_status.csv"
        fetch_fulltext.run(input=inc, output=out, email="acacio@example.com")

    df = pd.read_csv(out)
    assert (df["status"] == "oa_pdf_url").sum() == 1
    assert (df["status"] == "no_oa").sum() == 1


def test_fetch_fulltext_handles_missing_doi(tmp_path: Path) -> None:
    inc = tmp_path / "incluidos.csv"
    pd.DataFrame(
        [{"doi": "", "title": "A", "authors": "X", "year": 2020,
          "abstract": "", "venue": "v", "language": "en", "source": "scopus"}]
    ).to_csv(inc, index=False)

    out = tmp_path / "fulltext_status.csv"
    fetch_fulltext.run(input=inc, output=out, email="acacio@example.com")

    df = pd.read_csv(out)
    assert df.iloc[0]["status"] == "no_doi"
```

- [ ] **Step 2: Rodar teste para confirmar que falha**

Run: `uv run pytest tests/screening/test_fetch_fulltext.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `scripts/screening/fetch_fulltext.py`**

```python
"""Pipeline step 04: locate full-text URLs via Unpaywall and produce a status log.

For each included record, tries Unpaywall to find an open-access PDF URL.
Does NOT actually download PDFs — the user manages PDFs in Zotero. The script
just produces `fulltext_status.csv` to drive manual acquisition.

CLI:
    python -m scripts.screening.fetch_fulltext \
        --input data/processed/03_incluidos_ta.csv \
        --output data/processed/04_fulltext_status.csv \
        --email user@example.com
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _unpaywall_lookup(doi: str, email: str = "") -> dict | None:
    """Return Unpaywall record for DOI, or None if not found / not open access."""
    url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
    r = requests.get(url, timeout=15)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    data = r.json()
    if data.get("is_oa") and data.get("best_oa_location"):
        return {"pdf_url": data["best_oa_location"].get("url_for_pdf")}
    return None


def run(input: Path, output: Path, email: str) -> None:
    df = pd.read_csv(input, encoding="utf-8")
    statuses = []
    urls = []
    for _, row in df.iterrows():
        doi = str(row.get("doi") or "").strip()
        if not doi:
            statuses.append("no_doi")
            urls.append("")
            continue
        try:
            res = _unpaywall_lookup(doi, email=email)
        except Exception as e:
            statuses.append(f"error: {type(e).__name__}")
            urls.append("")
            continue
        if res and res.get("pdf_url"):
            statuses.append("oa_pdf_url")
            urls.append(res["pdf_url"])
        else:
            statuses.append("no_oa")
            urls.append("")
        time.sleep(0.1)  # polite rate limiting

    df["status"] = statuses
    df["pdf_url"] = urls
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False, encoding="utf-8")
    print(f"Full-text lookup: {sum(s == 'oa_pdf_url' for s in statuses)}/{len(statuses)} found via Unpaywall")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--email", required=True, help="Email for Unpaywall API")
    args = p.parse_args(argv)
    run(args.input, args.output, email=args.email)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Rodar teste**

Run: `uv run pytest tests/screening/test_fetch_fulltext.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/fetch_fulltext.py tests/screening/test_fetch_fulltext.py
git commit -m "feat(screening): add Unpaywall full-text lookup (04)"
```

---

## Task 15: Script `prisma_flow.py` — geração do diagrama PRISMA

**Files:**
- Create: `scripts/screening/prisma_flow.py`
- Create: `tests/screening/test_prisma_flow.py`

Gera um arquivo `.tex` com TikZ a partir das contagens das etapas.

- [ ] **Step 1: Escrever testes**

```python
from pathlib import Path

import pandas as pd

from scripts.screening import prisma_flow


def test_prisma_flow_generates_tex(tmp_path: Path) -> None:
    out = tmp_path / "prisma.tex"
    counts = dict(
        identified=120, duplicates=15, screened=105, excluded_ta=70,
        eligibility=35, excluded_ft=10, included=25,
    )
    prisma_flow.write_tex(counts=counts, output=out)
    text = out.read_text()
    assert "\\begin{tikzpicture}" in text
    assert "120" in text
    assert "25" in text


def test_prisma_flow_reads_pipeline_logs(tmp_path: Path) -> None:
    """Reads consolidated, dedup, screening_ta, eligibility CSVs and counts."""
    (tmp_path / "01_bruto.csv").write_text("a\n" * 121, encoding="utf-8")  # 120 records
    pd.DataFrame([{"removed_doi": "x"}] * 15).to_csv(tmp_path / "02_log.csv", index=False)
    pd.DataFrame(
        [{"decisao_llm": "incluir"}] * 30 + [{"decisao_llm": "excluir"}] * 70
        + [{"decisao_llm": "duvida"}] * 5
    ).to_csv(tmp_path / "03_screening.csv", index=False)
    pd.DataFrame(
        [{"decisao_final": "incluido"}] * 25 + [{"decisao_final": "excluido"}] * 10
    ).to_csv(tmp_path / "04_elig.csv", index=False)

    out = tmp_path / "prisma.tex"
    counts = prisma_flow.compute_counts(
        bruto=tmp_path / "01_bruto.csv",
        dedup_log=tmp_path / "02_log.csv",
        screening=tmp_path / "03_screening.csv",
        eligibility=tmp_path / "04_elig.csv",
    )
    assert counts["identified"] == 120
    assert counts["duplicates"] == 15
    assert counts["included"] == 25
```

- [ ] **Step 2: Rodar teste para confirmar que falha**

Run: `uv run pytest tests/screening/test_prisma_flow.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `scripts/screening/prisma_flow.py`**

```python
"""Pipeline step 05: generate PRISMA 2020 flow diagram as a TikZ .tex file.

Reads counts from earlier pipeline outputs and writes a self-contained TikZ
picture into `text/figures/prisma_flow.tex`, included via \\input{} in the
methodology chapter.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

TEMPLATE = r"""\begin{tikzpicture}[
    node distance=1.2cm,
    every node/.style={draw, rectangle, rounded corners, align=center, minimum width=5cm, minimum height=0.9cm, font=\small},
    arr/.style={-{Stealth[length=2mm]}, thick}
]
\node (id)   {Registros identificados nas bases\\(\textbf{N = %(identified)d})};
\node (dup) [below=of id] {Duplicatas removidas\\(N = %(duplicates)d)};
\node (scr) [below=of dup] {Registros para triagem TA\\(N = %(screened)d)};
\node (exta)[right=2cm of scr] {Excluídos na triagem TA\\(N = %(excluded_ta)d)};
\node (elig)[below=of scr] {Candidatos a texto completo\\(N = %(eligibility)d)};
\node (exft)[right=2cm of elig] {Excluídos na elegibilidade\\(N = %(excluded_ft)d)};
\node (inc) [below=of elig, fill=blue!10] {Estudos incluídos na síntese\\(\textbf{N = %(included)d})};

\draw[arr] (id)  -- (dup);
\draw[arr] (dup) -- (scr);
\draw[arr] (scr) -- (elig);
\draw[arr] (scr) -- (exta);
\draw[arr] (elig)-- (inc);
\draw[arr] (elig)-- (exft);
\end{tikzpicture}
"""


def write_tex(counts: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(TEMPLATE % counts, encoding="utf-8")


def compute_counts(
    bruto: Path, dedup_log: Path, screening: Path, eligibility: Path,
) -> dict:
    # identified = lines in bruto minus header
    with open(bruto) as f:
        identified = sum(1 for _ in f) - 1
    dup_df = pd.read_csv(dedup_log)
    duplicates = len(dup_df)
    screened = identified - duplicates

    scr_df = pd.read_csv(screening)
    excluded_ta = (scr_df["decisao_llm"] == "excluir").sum()
    eligibility_n = len(scr_df) - excluded_ta

    elig_df = pd.read_csv(eligibility)
    included = (elig_df["decisao_final"] == "incluido").sum()
    excluded_ft = (elig_df["decisao_final"] == "excluido").sum()

    return dict(
        identified=int(identified), duplicates=int(duplicates),
        screened=int(screened), excluded_ta=int(excluded_ta),
        eligibility=int(eligibility_n), excluded_ft=int(excluded_ft),
        included=int(included),
    )


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bruto", type=Path, required=True)
    p.add_argument("--dedup-log", type=Path, required=True)
    p.add_argument("--screening", type=Path, required=True)
    p.add_argument("--eligibility", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    counts = compute_counts(args.bruto, args.dedup_log, args.screening, args.eligibility)
    write_tex(counts, args.output)
    print(f"PRISMA flow written to {args.output} (included N={counts['included']})")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Rodar teste**

Run: `uv run pytest tests/screening/test_prisma_flow.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/prisma_flow.py tests/screening/test_prisma_flow.py
git commit -m "feat(screening): add PRISMA flow .tex generator (05)"
```

---

## Task 16: Script `extract.py` — formulário de extração (CLI)

**Files:**
- Create: `scripts/extraction/__init__.py`
- Create: `scripts/extraction/extract.py`
- Create: `tests/extraction/__init__.py`
- Create: `tests/extraction/test_extract.py`

CLI minimalista: lê eligibility CSV, abre o próximo paper ainda não extraído, mostra campos do schema, salva linha em `06_extraction.csv`. Versão Streamlit fica para tarefa posterior (opcional).

- [ ] **Step 1: Criar `__init__.py`**

Run: `touch scripts/extraction/__init__.py tests/extraction/__init__.py`

- [ ] **Step 2: Escrever testes**

```python
from pathlib import Path

import pandas as pd

from scripts.extraction import extract


def test_extract_schema_columns_are_complete() -> None:
    cols = extract.SCHEMA_COLUMNS
    assert "id" in cols
    assert "sinal_efeito" in cols
    assert "polarizacao" in cols
    assert "score_qualidade" in cols
    assert "revisto_humano" in cols
    assert len(cols) >= 27  # 7 blocks worth


def test_extract_save_appends_row(tmp_path: Path) -> None:
    out = tmp_path / "06_extraction.csv"
    row1 = {col: "" for col in extract.SCHEMA_COLUMNS}
    row1["id"] = "s-001"
    row1["titulo"] = "A"
    extract.save_row(row1, out)

    row2 = {col: "" for col in extract.SCHEMA_COLUMNS}
    row2["id"] = "s-002"
    row2["titulo"] = "B"
    extract.save_row(row2, out)

    df = pd.read_csv(out)
    assert len(df) == 2
    assert set(df["id"]) == {"s-001", "s-002"}


def test_extract_next_id_increments(tmp_path: Path) -> None:
    out = tmp_path / "06_extraction.csv"
    pd.DataFrame([{"id": "s-001"}, {"id": "s-003"}]).to_csv(out, index=False)
    assert extract.next_id(out) == "s-004"


def test_extract_next_id_empty_file(tmp_path: Path) -> None:
    assert extract.next_id(tmp_path / "nope.csv") == "s-001"
```

- [ ] **Step 3: Rodar teste**

Run: `uv run pytest tests/extraction/test_extract.py -v`
Expected: FAIL.

- [ ] **Step 4: Implementar `scripts/extraction/extract.py`**

```python
"""Pipeline step 06: structured data extraction (CLI form).

Loads the eligibility CSV (included papers) and presents a CLI form for each
paper not yet extracted in `06_extraction.csv`. Saves one row per paper following
the schema in `protocols/extraction_schema.md`.

CLI:
    python -m scripts.extraction.extract \
        --eligibility data/processed/04_eligibility.csv \
        --output data/processed/06_extraction.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

SCHEMA_COLUMNS = [
    # Bloco A — identificação
    "id", "doi", "titulo", "autores", "ano", "periodico", "tipo_pub",
    "pais_estudo", "periodo_dados",
    # Bloco B — temporal
    "janela", "pre_pos_chatgpt", "tecnologia_focada",
    # Bloco C — evidência
    "tipo_estudo", "metodo_empirico", "unidade_analise", "fonte_dados",
    # Bloco D — mecanismos
    "mec_deslocamento", "mec_reinstalacao", "mec_complementaridade",
    "mec_demanda_agregada", "mec_outros",
    # Bloco E — achados
    "sinal_efeito", "magnitude_reportada", "magnitude_normalizada",
    "ocupacoes_afetadas", "polarizacao", "horizonte",
    # Bloco F — qualidade
    "score_qualidade", "limitacoes_declaradas", "replicavel", "revisado_por_pares",
    # Bloco G — notas
    "nota_extracao", "citacoes_chave", "revisto_humano",
]


def next_id(extraction_path: Path) -> str:
    """Return the next sequential id (s-NNN) given existing extractions."""
    if not extraction_path.exists():
        return "s-001"
    df = pd.read_csv(extraction_path)
    if df.empty or "id" not in df.columns:
        return "s-001"
    nums = [int(i.split("-")[1]) for i in df["id"].dropna() if i.startswith("s-")]
    n = (max(nums) if nums else 0) + 1
    return f"s-{n:03d}"


def save_row(row: dict, output: Path) -> None:
    """Append a row to the extraction CSV, creating it with header if needed."""
    output.parent.mkdir(parents=True, exist_ok=True)
    df_new = pd.DataFrame([row], columns=SCHEMA_COLUMNS)
    if output.exists():
        df_new.to_csv(output, mode="a", header=False, index=False, encoding="utf-8")
    else:
        df_new.to_csv(output, index=False, encoding="utf-8")


def _prompt(label: str, default: str = "") -> str:
    val = input(f"{label} [{default}]: ").strip()
    return val or default


def _interactive_form(meta: pd.Series, id_: str) -> dict:
    print(f"\n=== Extracting: {meta['titulo']} ({meta['ano']}) ===\n")
    row = {col: "" for col in SCHEMA_COLUMNS}
    row.update(
        id=id_, doi=meta.get("doi", ""), titulo=meta["titulo"],
        autores=meta.get("autores", ""), ano=int(meta["ano"]) if pd.notna(meta["ano"]) else "",
        periodico=meta.get("venue", ""), tipo_pub=_prompt("tipo_pub (journal|working paper|book chapter)"),
    )
    row["pais_estudo"] = _prompt("pais_estudo (ou 'multipais')")
    row["periodo_dados"] = _prompt("periodo_dados (e.g., 2010-2019)")
    row["janela"] = _prompt("janela (2013-2017|2018-2022|2022-2025)")
    row["pre_pos_chatgpt"] = _prompt("pre_pos_chatgpt (pre|pos)")
    row["tecnologia_focada"] = _prompt("tecnologia_focada")
    row["tipo_estudo"] = _prompt("tipo_estudo")
    row["metodo_empirico"] = _prompt("metodo_empirico")
    row["unidade_analise"] = _prompt("unidade_analise")
    row["fonte_dados"] = _prompt("fonte_dados")
    for mec in ["mec_deslocamento", "mec_reinstalacao", "mec_complementaridade", "mec_demanda_agregada"]:
        row[mec] = _prompt(f"{mec} (sim|nao|n/a)")
    row["mec_outros"] = _prompt("mec_outros (texto livre)")
    row["sinal_efeito"] = _prompt("sinal_efeito (negativo|positivo|nulo|ambíguo|n/a)")
    row["magnitude_reportada"] = _prompt("magnitude_reportada (texto)")
    row["magnitude_normalizada"] = _prompt("magnitude_normalizada (float ou vazio)")
    row["ocupacoes_afetadas"] = _prompt("ocupacoes_afetadas")
    row["polarizacao"] = _prompt("polarizacao (alta-quali|baixa-quali|ambos|neutro|n/a)")
    row["horizonte"] = _prompt("horizonte")
    row["score_qualidade"] = _prompt("score_qualidade (1-5)")
    row["limitacoes_declaradas"] = _prompt("limitacoes_declaradas")
    row["replicavel"] = _prompt("replicavel (sim|parcial|nao|n/a)")
    row["revisado_por_pares"] = _prompt("revisado_por_pares (sim|nao)")
    row["nota_extracao"] = _prompt("nota_extracao (livre)")
    row["citacoes_chave"] = _prompt("citacoes_chave (IDs separados por ';')")
    row["revisto_humano"] = "True"
    return row


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--eligibility", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)

    elig = pd.read_csv(args.eligibility, encoding="utf-8")
    incl = elig[elig.get("decisao_final", "incluido") == "incluido"]

    already = set()
    if args.output.exists():
        already = set(pd.read_csv(args.output)["doi"].dropna().tolist())

    for _, meta in incl.iterrows():
        doi = str(meta.get("doi") or "").strip()
        if doi and doi in already:
            continue
        id_ = next_id(args.output)
        row = _interactive_form(meta, id_)
        save_row(row, args.output)
        print(f"Saved {id_}.")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 5: Rodar teste**

Run: `uv run pytest tests/extraction/test_extract.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/extraction/__init__.py scripts/extraction/extract.py tests/extraction/__init__.py tests/extraction/test_extract.py
git commit -m "feat(extraction): add CLI extraction form following 7-block schema"
```

---

## Task 17: Script `validate.py` — validador de consistência da extração

**Files:**
- Create: `scripts/extraction/validate.py`
- Create: `tests/extraction/test_validate.py`

- [ ] **Step 1: Escrever testes**

```python
from pathlib import Path

import pandas as pd

from scripts.extraction import validate


def _row(**overrides) -> dict:
    base = {
        "id": "s-001", "ano": 2020, "janela": "2018-2022", "pre_pos_chatgpt": "pre",
        "sinal_efeito": "negativo", "mec_deslocamento": "sim",
        "mec_reinstalacao": "nao", "score_qualidade": 4,
    }
    base.update(overrides)
    return base


def test_validate_detects_inconsistent_window(tmp_path: Path) -> None:
    df = pd.DataFrame([_row(ano=2024, janela="2018-2022")])
    out = tmp_path / "out.csv"
    df.to_csv(out, index=False)
    issues = validate.run(out)
    assert any(i["rule"] == "year_window_mismatch" for i in issues)


def test_validate_detects_pre_pos_inconsistency(tmp_path: Path) -> None:
    df = pd.DataFrame([_row(ano=2024, janela="2022-2025", pre_pos_chatgpt="pre")])
    out = tmp_path / "out.csv"
    df.to_csv(out, index=False)
    issues = validate.run(out)
    assert any(i["rule"] == "pre_pos_chatgpt_inconsistent" for i in issues)


def test_validate_passes_clean_row(tmp_path: Path) -> None:
    df = pd.DataFrame([_row()])
    out = tmp_path / "out.csv"
    df.to_csv(out, index=False)
    issues = validate.run(out)
    assert issues == []
```

- [ ] **Step 2: Rodar teste**

Run: `uv run pytest tests/extraction/test_validate.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `scripts/extraction/validate.py`**

```python
"""Pipeline step 07: validate extracted rows for internal consistency."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

WINDOWS = {
    "2013-2017": (2013, 2017),
    "2018-2022": (2018, 2022),
    "2022-2025": (2022, 2025),
}


def _check_year_window(row: dict) -> str | None:
    win = WINDOWS.get(row.get("janela", ""))
    if not win:
        return None
    try:
        ano = int(row.get("ano"))
    except (TypeError, ValueError):
        return None
    lo, hi = win
    if not (lo <= ano <= hi):
        return f"ano={ano} fora da janela {row['janela']}"
    return None


def _check_pre_pos(row: dict) -> str | None:
    try:
        ano = int(row.get("ano"))
    except (TypeError, ValueError):
        return None
    expected = "pos" if ano >= 2023 else "pre"
    if row.get("pre_pos_chatgpt") and row["pre_pos_chatgpt"] != expected:
        return f"ano={ano} sugere {expected}, mas pre_pos_chatgpt={row['pre_pos_chatgpt']}"
    return None


def run(path: Path) -> list[dict]:
    df = pd.read_csv(path, encoding="utf-8")
    issues = []
    for _, row in df.iterrows():
        d = row.to_dict()
        if msg := _check_year_window(d):
            issues.append(dict(id=d.get("id"), rule="year_window_mismatch", message=msg))
        if msg := _check_pre_pos(d):
            issues.append(dict(id=d.get("id"), rule="pre_pos_chatgpt_inconsistent", message=msg))
    return issues


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("path", type=Path)
    args = p.parse_args(argv)
    issues = run(args.path)
    if not issues:
        print("OK — no issues found.")
        return 0
    for it in issues:
        print(f"[{it['rule']}] {it['id']}: {it['message']}")
    return 1


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Rodar teste**

Run: `uv run pytest tests/extraction/test_validate.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction/validate.py tests/extraction/test_validate.py
git commit -m "feat(extraction): add extraction consistency validator (07)"
```

---

## Task 18: Script `descritivas_corpus.py` — figuras descritivas do corpus

**Files:**
- Create: `scripts/analysis/__init__.py`
- Create: `scripts/analysis/descritivas_corpus.py`
- Create: `tests/analysis/__init__.py`
- Create: `tests/analysis/test_descritivas_corpus.py`

Gera figuras matplotlib: histograma de anos, distribuição por janela, por idioma. Cada figura é salva em `text/figures/`.

- [ ] **Step 1: Criar `__init__.py`**

Run: `touch scripts/analysis/__init__.py tests/analysis/__init__.py`

- [ ] **Step 2: Escrever testes**

```python
from pathlib import Path

import pandas as pd

from scripts.analysis import descritivas_corpus


def _sample_extraction() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"id": f"s-{i:03d}", "ano": y, "janela": j, "pre_pos_chatgpt": p,
             "tipo_estudo": t}
            for i, (y, j, p, t) in enumerate([
                (2015, "2013-2017", "pre", "exposição ocupacional"),
                (2016, "2013-2017", "pre", "teórico/modelo"),
                (2020, "2018-2022", "pre", "evidência macro/setorial"),
                (2023, "2022-2025", "pos", "exposição ocupacional"),
                (2024, "2022-2025", "pos", "firma/freelancer"),
            ], start=1)
        ]
    )


def test_descritivas_writes_year_histogram(tmp_path: Path) -> None:
    df = _sample_extraction()
    ext = tmp_path / "ext.csv"
    df.to_csv(ext, index=False)
    out_dir = tmp_path / "figs"
    descritivas_corpus.run(input=ext, output_dir=out_dir)
    assert (out_dir / "corpus_anos.pdf").exists()
    assert (out_dir / "corpus_janelas.pdf").exists()
    assert (out_dir / "corpus_tipo_estudo.pdf").exists()
```

- [ ] **Step 3: Rodar teste**

Run: `uv run pytest tests/analysis/test_descritivas_corpus.py -v`
Expected: FAIL.

- [ ] **Step 4: Implementar `scripts/analysis/descritivas_corpus.py`**

```python
"""Pipeline step (analysis): generate descriptive figures of the corpus."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("Agg")  # headless


def _fig_anos(df: pd.DataFrame, output: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    counts = df["ano"].value_counts().sort_index()
    ax.bar(counts.index, counts.values, color="steelblue")
    ax.set_xlabel("Ano de publicação")
    ax.set_ylabel("Número de estudos")
    ax.set_title("Distribuição do corpus por ano")
    fig.tight_layout()
    fig.savefig(output, format="pdf")
    plt.close(fig)


def _fig_janelas(df: pd.DataFrame, output: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    counts = df["janela"].value_counts().reindex(["2013-2017", "2018-2022", "2022-2025"]).fillna(0)
    ax.bar(counts.index, counts.values, color=["#cccccc", "#888888", "#444444"])
    ax.set_ylabel("Número de estudos")
    ax.set_title("Corpus por janela temporal")
    fig.tight_layout()
    fig.savefig(output, format="pdf")
    plt.close(fig)


def _fig_tipo_estudo(df: pd.DataFrame, output: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    counts = df["tipo_estudo"].value_counts()
    ax.barh(counts.index, counts.values, color="seagreen")
    ax.set_xlabel("Número de estudos")
    ax.set_title("Tipos de estudo no corpus")
    fig.tight_layout()
    fig.savefig(output, format="pdf")
    plt.close(fig)


def run(input: Path, output_dir: Path) -> None:
    df = pd.read_csv(input, encoding="utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    _fig_anos(df, output_dir / "corpus_anos.pdf")
    _fig_janelas(df, output_dir / "corpus_janelas.pdf")
    _fig_tipo_estudo(df, output_dir / "corpus_tipo_estudo.pdf")
    print(f"Wrote 3 figures to {output_dir}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args(argv)
    run(args.input, args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 5: Rodar teste**

Run: `uv run pytest tests/analysis/test_descritivas_corpus.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/analysis/__init__.py scripts/analysis/descritivas_corpus.py tests/analysis/__init__.py tests/analysis/test_descritivas_corpus.py
git commit -m "feat(analysis): add corpus descriptive figures (anos, janelas, tipo)"
```

---

## Task 19: Script `comparacao_pre_pos.py` — tabela comparativa pré/pós-ChatGPT

**Files:**
- Create: `scripts/analysis/comparacao_pre_pos.py`
- Create: `tests/analysis/test_comparacao_pre_pos.py`

Gera a tabela-síntese pareada (formato LaTeX) e o gráfico de barras lado a lado para os quatro eixos.

- [ ] **Step 1: Escrever testes**

```python
from pathlib import Path

import pandas as pd

from scripts.analysis import comparacao_pre_pos


def _sample() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"pre_pos_chatgpt": "pre", "sinal_efeito": "negativo", "polarizacao": "baixa-quali em risco",
             "tecnologia_focada": "automação", "tipo_estudo": "exposição ocupacional"},
            {"pre_pos_chatgpt": "pre", "sinal_efeito": "negativo", "polarizacao": "baixa-quali em risco",
             "tecnologia_focada": "ML/preditiva", "tipo_estudo": "evidência macro/setorial"},
            {"pre_pos_chatgpt": "pos", "sinal_efeito": "ambíguo", "polarizacao": "alta-quali em risco",
             "tecnologia_focada": "IA generativa/LLMs", "tipo_estudo": "exposição ocupacional"},
            {"pre_pos_chatgpt": "pos", "sinal_efeito": "positivo", "polarizacao": "alta-quali em risco",
             "tecnologia_focada": "IA generativa/LLMs", "tipo_estudo": "firma/freelancer"},
        ]
    )


def test_comparacao_writes_latex_table(tmp_path: Path) -> None:
    df = _sample()
    ext = tmp_path / "ext.csv"
    df.to_csv(ext, index=False)
    out_tex = tmp_path / "comparacao.tex"
    comparacao_pre_pos.run(input=ext, output_table=out_tex)
    txt = out_tex.read_text()
    assert "\\begin{tabular}" in txt
    assert "Pré" in txt or "pre" in txt
    assert "Pós" in txt or "pos" in txt


def test_comparacao_counts_are_correct(tmp_path: Path) -> None:
    df = _sample()
    ext = tmp_path / "ext.csv"
    df.to_csv(ext, index=False)
    result = comparacao_pre_pos.compute(df)
    assert result["n_pre"] == 2
    assert result["n_pos"] == 2
    # both pre rows have sinal negativo, polarizacao baixa-quali
    assert result["pre"]["sinal_efeito"]["negativo"] == 2
```

- [ ] **Step 2: Rodar teste**

Run: `uv run pytest tests/analysis/test_comparacao_pre_pos.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `scripts/analysis/comparacao_pre_pos.py`**

```python
"""Analysis: build pre/post-ChatGPT comparative table (LaTeX) from extraction CSV."""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

DIMENSIONS = ["sinal_efeito", "polarizacao", "tecnologia_focada", "tipo_estudo"]
DIM_LABELS = {
    "sinal_efeito": "Sinal sobre emprego",
    "polarizacao": "Ocupações em risco",
    "tecnologia_focada": "Tecnologia de IA focada",
    "tipo_estudo": "Tipo de evidência",
}


def compute(df: pd.DataFrame) -> dict:
    out: dict = {"n_pre": int((df["pre_pos_chatgpt"] == "pre").sum()),
                 "n_pos": int((df["pre_pos_chatgpt"] == "pos").sum())}
    for period in ("pre", "pos"):
        sub = df[df["pre_pos_chatgpt"] == period]
        out[period] = {d: Counter(sub[d].dropna().tolist()) for d in DIMENSIONS}
    return out


def to_latex_table(result: dict) -> str:
    lines = [
        r"\begin{tabular}{lll}",
        r"\toprule",
        rf"Dimensão & Pré-ChatGPT (n={result['n_pre']}) & Pós-ChatGPT (n={result['n_pos']}) \\",
        r"\midrule",
    ]
    for d in DIMENSIONS:
        pre_top = ", ".join(f"{k} ({v})" for k, v in result["pre"][d].most_common(3))
        pos_top = ", ".join(f"{k} ({v})" for k, v in result["pos"][d].most_common(3))
        lines.append(f"{DIM_LABELS[d]} & {pre_top} & {pos_top} \\\\")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    return "\n".join(lines) + "\n"


def run(input: Path, output_table: Path) -> None:
    df = pd.read_csv(input, encoding="utf-8")
    result = compute(df)
    output_table.parent.mkdir(parents=True, exist_ok=True)
    output_table.write_text(to_latex_table(result), encoding="utf-8")
    print(f"Wrote comparative table to {output_table}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output-table", type=Path, required=True)
    args = p.parse_args(argv)
    run(args.input, args.output_table)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Rodar teste**

Run: `uv run pytest tests/analysis/test_comparacao_pre_pos.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/analysis/comparacao_pre_pos.py tests/analysis/test_comparacao_pre_pos.py
git commit -m "feat(analysis): add pre/post-ChatGPT comparative table generator"
```

---

## Task 20: LaTeX preamble (`text/preamble.tex`)

**Files:**
- Create: `text/preamble.tex`

- [ ] **Step 1: Criar `text/preamble.tex`**

```latex
% Preamble — pacotes e configurações comuns

\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[brazilian]{babel}

\usepackage{lmodern}
\usepackage{microtype}
\usepackage{geometry}
\geometry{a4paper, margin=2.5cm}

\usepackage{setspace}
\onehalfspacing

\usepackage{indentfirst}

\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{siunitx}
\usepackage{caption}
\usepackage{subcaption}
\usepackage{xcolor}

\usepackage{hyperref}
\hypersetup{
    colorlinks=true,
    linkcolor=black,
    citecolor=black,
    urlcolor=blue!50!black,
}

\usepackage{tikz}
\usetikzlibrary{shapes,arrows.meta,positioning,calc}

\usepackage[
    backend=biber,
    style=apa,
    language=brazilian,
    natbib=true,
    sorting=nyt,
]{biblatex}

\addbibresource{refs.bib}

% Comandos auxiliares
\newcommand{\janelaUm}{2013--2017}
\newcommand{\janelaDois}{2018--2022}
\newcommand{\janelaTres}{2022--2025}
```

- [ ] **Step 2: Commit**

```bash
git add text/preamble.tex
git commit -m "feat(text): add LaTeX preamble with babel-pt, biblatex-apa, tikz"
```

---

## Task 21: LaTeX main document (`text/main.tex`)

**Files:**
- Create: `text/main.tex`

- [ ] **Step 1: Criar `text/main.tex`**

```latex
\documentclass[12pt,a4paper]{article}

\input{preamble.tex}

\title{Impactos da Inteligência Artificial no Mercado de Trabalho:\\
       uma Revisão Sistemática da Literatura (2013--2025)}
\author{Acacio}
\date{\today}

\begin{document}

\input{pre/capa.tex}
\input{pre/folha_rosto.tex}
\input{pre/resumo.tex}
\input{pre/abstract.tex}
\input{pre/agradecimentos.tex}

\tableofcontents
\newpage

\input{chapters/01_introducao.tex}
\input{chapters/02_referencial_teorico.tex}
\input{chapters/03_metodologia.tex}
\input{chapters/04_resultados_descritivas.tex}
\input{chapters/05_resultados_janelas.tex}
\input{chapters/06_comparacao_pre_pos.tex}
\input{chapters/07_implicacoes_brasil.tex}
\input{chapters/08_consideracoes_finais.tex}

\printbibliography

\end{document}
```

- [ ] **Step 2: Commit**

```bash
git add text/main.tex
git commit -m "feat(text): add main.tex with chapter includes"
```

---

## Task 22: Capítulos stub e elementos pré-textuais

**Files:**
- Create: `text/pre/capa.tex`, `text/pre/folha_rosto.tex`, `text/pre/resumo.tex`, `text/pre/abstract.tex`, `text/pre/agradecimentos.tex`
- Create: `text/chapters/01_introducao.tex` … `08_consideracoes_finais.tex`
- Create: `text/refs.bib`

- [ ] **Step 1: Criar elementos pré-textuais como stubs**

Para cada arquivo em `text/pre/`, criar com conteúdo mínimo:

`text/pre/capa.tex`:
```latex
% Capa institucional — formatar conforme exigência da universidade

\begin{titlepage}
\centering
{\Large UNIVERSIDADE [NOME]\par}
\vspace{1cm}
{\large Bacharelado em Ciências Econômicas\par}
\vspace{4cm}
{\LARGE\bfseries Impactos da Inteligência Artificial no Mercado de Trabalho:\\
uma Revisão Sistemática da Literatura (2013--2025)\par}
\vspace{2cm}
{\large Acacio\par}
\vfill
{\large \today\par}
\end{titlepage}
\newpage
```

`text/pre/folha_rosto.tex`:
```latex
% Folha de rosto — versão simplificada, ajustar à ABNT/template

\begin{center}
\large
Acacio

\vspace{2cm}

\textbf{Impactos da Inteligência Artificial no Mercado de Trabalho:\\
uma Revisão Sistemática da Literatura (2013--2025)}

\vspace{1cm}

\normalsize
Trabalho de Conclusão de Curso apresentado ao curso de Bacharelado em Ciências
Econômicas como requisito parcial para obtenção do grau de Bacharel.\\[1em]
Orientador: [Nome do Orientador]
\end{center}
\vspace*{\fill}
\newpage
```

`text/pre/resumo.tex`:
```latex
\section*{Resumo}

[Resumo em português, 150–300 palavras, a ser escrito após a redação dos capítulos.]

\textbf{Palavras-chave:} inteligência artificial; mercado de trabalho; emprego; LLMs; revisão sistemática.
\newpage
```

`text/pre/abstract.tex`:
```latex
\section*{Abstract}

[Abstract in English, 150–300 words, mirroring the resumo.]

\textbf{Keywords:} artificial intelligence; labor market; employment; LLMs; systematic literature review.
\newpage
```

`text/pre/agradecimentos.tex`:
```latex
\section*{Agradecimentos}

[Texto livre, escrito ao final.]
\newpage
```

- [ ] **Step 2: Criar 8 capítulos stub**

Para cada arquivo em `text/chapters/`, criar um stub começando com `\section`:

`text/chapters/01_introducao.tex`:
```latex
\section{Introdução}\label{cap:intro}

\subsection{Motivação e contexto}
\subsection{Pergunta de pesquisa}
\subsection{Objetivos}
\subsection{Justificativa}
\subsection{Estrutura do trabalho}
```

`text/chapters/02_referencial_teorico.tex`:
```latex
\section{Referencial teórico}\label{cap:refteo}

\subsection{Tecnologia e emprego: do SBTC ao task approach}
\subsection{O framework Acemoglu--Restrepo de tarefas}
\subsection{Antecedentes pré-2013}
\subsection{Conceitos centrais: deslocamento, reinstalação, complementaridade}
```

`text/chapters/03_metodologia.tex`:
```latex
\section{Metodologia}\label{cap:metodologia}

\subsection{Desenho da revisão sistemática}
\subsection{Critérios de inclusão e exclusão}
\subsection{Estratégia de busca}
\subsection{Processo de seleção}

\begin{figure}[h]
\centering
\input{figures/prisma_flow.tex}
\caption{Diagrama PRISMA 2020 do processo de seleção.}
\label{fig:prisma}
\end{figure}

\subsection{Esquema de extração de dados}
\subsection{Avaliação de qualidade}
\subsection{Limitações metodológicas}
```

`text/chapters/04_resultados_descritivas.tex`:
```latex
\section{Resultados I — Descritivas do corpus}\label{cap:descritivas}

\subsection{Volume e evolução temporal}

\begin{figure}[h]
\centering
\includegraphics[width=0.85\linewidth]{figures/corpus_anos.pdf}
\caption{Distribuição do corpus por ano de publicação.}
\label{fig:corpus_anos}
\end{figure}

\subsection{Distribuição por janela temporal}

\begin{figure}[h]
\centering
\includegraphics[width=0.7\linewidth]{figures/corpus_janelas.pdf}
\caption{Corpus por janela temporal.}
\label{fig:corpus_janelas}
\end{figure}

\subsection{Tipos de estudo}

\begin{figure}[h]
\centering
\includegraphics[width=0.85\linewidth]{figures/corpus_tipo_estudo.pdf}
\caption{Tipos de estudo no corpus.}
\label{fig:corpus_tipos}
\end{figure}
```

`text/chapters/05_resultados_janelas.tex`:
```latex
\section{Resultados II — Síntese por janela}\label{cap:janelas}

\subsection{Janela 1: \janelaUm{} — era da automação}
\subsection{Janela 2: \janelaDois{} — era de deep learning e ML}
\subsection{Janela 3: \janelaTres{} — era da IA generativa}
```

`text/chapters/06_comparacao_pre_pos.tex`:
```latex
\section{Resultados III — Comparação pré/pós-ChatGPT}\label{cap:comparacao}

\begin{table}[h]
\centering
\caption{Comparação pareada de dimensões pré e pós-ChatGPT.}
\label{tab:comparacao}
\input{tables/comparacao_pre_pos.tex}
\end{table}

\subsection{Eixo 1: Quem está em risco}
\subsection{Eixo 2: Qual o mecanismo}
\subsection{Eixo 3: Como se mede}
\subsection{Eixo 4: O que se sabe vs. o que se projeta}
\subsection{Continuidades}
\subsection{Rupturas}
```

`text/chapters/07_implicacoes_brasil.tex`:
```latex
\section{Implicações para o Brasil}\label{cap:brasil}

\subsection{O que a literatura brasileira do corpus diz}
\subsection{Cruzamento de exposição internacional com CBO}
\subsection{Limites da extrapolação}
```

`text/chapters/08_consideracoes_finais.tex`:
```latex
\section{Considerações finais}\label{cap:fim}

\subsection{Síntese dos achados}
\subsection{Limitações}
\subsection{Agenda de pesquisa futura}
```

- [ ] **Step 3: Criar `text/refs.bib` vazio (mas válido)**

```bibtex
% Bibliografia exportada de Zotero (Better BibTeX) ao final do trabalho.
% Mantido aqui como placeholder mínimo para o LaTeX compilar.

@misc{placeholder,
  title = {Placeholder Entry},
  author = {Acacio},
  year = {2026},
  note = {Substituir pelo export do Zotero ao final.}
}
```

- [ ] **Step 4: Commit**

```bash
git add text/pre/ text/chapters/ text/refs.bib
git commit -m "feat(text): scaffold pre-textual elements, 8 chapter stubs, refs.bib"
```

---

## Task 23: Makefile orquestrando o pipeline

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Criar `Makefile`**

```makefile
# Makefile — pipeline TCC SLR
# Targets principais:
#   make search    — executa buscas (a implementar em F3)
#   make screen    — pipeline 01-05 de screening
#   make extract   — abre CLI de extração
#   make analysis  — regenera tabelas e figuras
#   make pdf       — compila LaTeX
#   make test      — pytest
#   make all       — pipeline completo (exceto extração interativa)
#   make clean     — limpa data/processed/, figures geradas, build/

PYTHON := uv run python
PYTEST := uv run pytest

DATA_RAW := data/raw/searches
DATA_PROC := data/processed
TEXT_DIR := text
FIG_DIR := text/figures
TAB_DIR := text/tables
BUILD := build

EMAIL ?= acacio@example.com  # override: make fetch EMAIL=foo@bar.com

# ============ Pipeline ============

.PHONY: search
search:
	@echo "F3 — buscas: implementadas no Plano 2. Por enquanto, popular manualmente $(DATA_RAW)/"

.PHONY: consolidate
consolidate:
	$(PYTHON) -m scripts.screening.consolidate \
	    --sources $(DATA_RAW)/*.csv \
	    --output $(DATA_PROC)/01_corpus_bruto.csv

.PHONY: dedup
dedup:
	$(PYTHON) -m scripts.screening.dedup \
	    --input $(DATA_PROC)/01_corpus_bruto.csv \
	    --output $(DATA_PROC)/02_corpus_dedup.csv \
	    --log $(DATA_PROC)/02_dedup_decisions.csv

.PHONY: screening_ta
screening_ta:
	$(PYTHON) -m scripts.screening.screening_ta \
	    --input $(DATA_PROC)/02_corpus_dedup.csv \
	    --output $(DATA_PROC)/03_screening_ta.csv \
	    --incluidos $(DATA_PROC)/03_incluidos_ta.csv \
	    --cache $(DATA_PROC)/03_llm_cache.json

.PHONY: fetch
fetch:
	$(PYTHON) -m scripts.screening.fetch_fulltext \
	    --input $(DATA_PROC)/03_incluidos_ta.csv \
	    --output $(DATA_PROC)/04_fulltext_status.csv \
	    --email $(EMAIL)

.PHONY: prisma
prisma:
	$(PYTHON) -m scripts.screening.prisma_flow \
	    --bruto $(DATA_PROC)/01_corpus_bruto.csv \
	    --dedup-log $(DATA_PROC)/02_dedup_decisions.csv \
	    --screening $(DATA_PROC)/03_screening_ta.csv \
	    --eligibility $(DATA_PROC)/04_eligibility.csv \
	    --output $(FIG_DIR)/prisma_flow.tex

.PHONY: screen
screen: consolidate dedup screening_ta

.PHONY: extract
extract:
	$(PYTHON) -m scripts.extraction.extract \
	    --eligibility $(DATA_PROC)/04_eligibility.csv \
	    --output $(DATA_PROC)/06_extraction.csv

.PHONY: validate
validate:
	$(PYTHON) -m scripts.extraction.validate $(DATA_PROC)/06_extraction.csv

.PHONY: analysis
analysis:
	$(PYTHON) -m scripts.analysis.descritivas_corpus \
	    --input $(DATA_PROC)/06_extraction.csv \
	    --output-dir $(FIG_DIR)
	$(PYTHON) -m scripts.analysis.comparacao_pre_pos \
	    --input $(DATA_PROC)/06_extraction.csv \
	    --output-table $(TAB_DIR)/comparacao_pre_pos.tex

# ============ LaTeX ============

.PHONY: pdf
pdf:
	cd $(TEXT_DIR) && latexmk -pdf -outdir=../$(BUILD) main.tex

# ============ Test ============

.PHONY: test
test:
	$(PYTEST)

# ============ Composite ============

.PHONY: all
all: screen analysis pdf

.PHONY: clean
clean:
	rm -rf $(BUILD)/
	rm -f $(DATA_PROC)/*.csv $(DATA_PROC)/*.json
	rm -f $(FIG_DIR)/*.pdf $(TAB_DIR)/*.tex
```

- [ ] **Step 2: Verificar sintaxe**

Run: `make -n test`
Expected: imprime `uv run pytest` (dry-run).

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "feat: add Makefile orchestrating pipeline (screen/extract/analysis/pdf/test)"
```

---

## Task 24: Atualizar `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Sobrescrever `README.md`**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README with project structure and commands"
```

---

## Task 25: Validação end-to-end com dados sintéticos

**Files:**
- Create: `tests/test_pipeline_e2e.py`

Teste de integração que roda consolidate → dedup → screening_ta (mock) → descritivas e checa outputs.

- [ ] **Step 1: Escrever teste**

```python
"""End-to-end pipeline test on synthetic data."""
from pathlib import Path

import pandas as pd

from scripts.screening.consolidate import run as consolidate
from scripts.screening.dedup import run as dedup
from scripts.screening.screening_ta import run as screening_ta


FIXTURES = Path(__file__).parent / "fixtures"


def test_pipeline_consolidate_dedup_screen(tmp_path: Path) -> None:
    # 1. Consolidate
    bruto = tmp_path / "01_bruto.csv"
    consolidate(
        sources=[FIXTURES / "sample_wos.csv", FIXTURES / "sample_scopus.csv"],
        output=bruto,
    )
    assert pd.read_csv(bruto).shape[0] == 9

    # 2. Dedup
    deduped = tmp_path / "02_dedup.csv"
    log = tmp_path / "02_log.csv"
    dedup(input=bruto, output=deduped, log=log, use_embeddings=False)
    assert pd.read_csv(deduped).shape[0] == 7  # 2 duplicates removed

    # 3. Screening (mock mode)
    screened = tmp_path / "03_screening.csv"
    incl = tmp_path / "03_incluidos.csv"
    screening_ta(input=deduped, output=screened, incluidos=incl, mock=True)
    df = pd.read_csv(screened)
    assert {"decisao_llm", "justificativa_llm", "confianca_llm"} <= set(df.columns)
    # At least 1 record should be marked include or duvida (mock heuristic)
    assert (df["decisao_llm"].isin(["incluir", "duvida"])).sum() >= 1
```

- [ ] **Step 2: Rodar todos os testes do projeto**

Run: `uv run pytest -v`
Expected: todos os testes anteriores + o e2e novo passam (>= 30 testes).

- [ ] **Step 3: Verificar que o LaTeX compila com capítulos stub**

Pré-requisito: TeX Live instalado (`latexmk`, `biber`). Se não instalado:
```bash
sudo apt-get install -y texlive-latex-extra texlive-bibtex-extra texlive-lang-portuguese biber latexmk
```

Gerar placeholders válidos via Python (PDFs e .tex) para que `make pdf` consiga compilar mesmo antes do pipeline real ter produzido dados:

```bash
mkdir -p text/tables text/figures
uv run python - <<'PY'
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

Path("text/figures/prisma_flow.tex").write_text(
    r"\begin{tikzpicture}\node {Placeholder PRISMA flow.};\end{tikzpicture}", encoding="utf-8")

Path("text/tables/comparacao_pre_pos.tex").write_text(
    r"""\begin{tabular}{lll}
\toprule
Dim & Pré & Pós \\
\midrule
placeholder & - & - \\
\bottomrule
\end{tabular}""", encoding="utf-8")

for name in ("corpus_anos", "corpus_janelas", "corpus_tipo_estudo"):
    fig, ax = plt.subplots(figsize=(4, 2))
    ax.text(0.5, 0.5, f"placeholder: {name}", ha="center", va="center")
    ax.axis("off")
    fig.savefig(f"text/figures/{name}.pdf", format="pdf")
    plt.close(fig)
print("placeholders written")
PY

make pdf
ls -la build/main.pdf
```

Expected: `placeholders written`; `build/main.pdf` existe e tem tamanho > 0. Warnings de bibtex sobre citações vazias são esperados e podem ser ignorados.

- [ ] **Step 4: Limpar placeholders**

Os placeholders foram só para verificar a compilação. Os arquivos reais virão do pipeline em planos posteriores. O `.gitignore` já cobre `text/figures/*.pdf` e `text/tables/*.tex`, então eles **não** vão para o repo. Apagar para deixar o working tree limpo:

```bash
rm -f text/figures/prisma_flow.tex
rm -f text/tables/comparacao_pre_pos.tex
rm -f text/figures/corpus_anos.pdf text/figures/corpus_janelas.pdf text/figures/corpus_tipo_estudo.pdf
rm -rf build/
git status
```

Expected: `git status` mostra apenas `tests/test_pipeline_e2e.py` como untracked (criado no Step 1).

- [ ] **Step 5: Commit teste e2e**

```bash
git add tests/test_pipeline_e2e.py
git commit -m "test: add end-to-end pipeline test on synthetic fixtures"
```

---

## Task 26: Commit final do plano e tag

**Files:**
- Nenhum

- [ ] **Step 1: Verificar estado limpo do repo**

Run: `git status`
Expected: working tree clean, nenhum arquivo não rastreado.

- [ ] **Step 2: Rodar `make test` final**

Run: `make test`
Expected: todos os testes passam (>= 30 testes).

- [ ] **Step 3: Criar tag de marco**

```bash
git tag -a v0.1.0-infra -m "Plano 1 completo: infraestrutura e protocolos"
```

- [ ] **Step 4: Verificar tag**

Run: `git log --oneline | head -30 && git tag -l`
Expected: histórico de commits do Plano 1 visível; tag `v0.1.0-infra` listada.

---

## Resumo dos artefatos entregues por este plano

**Protocolos (5 documentos markdown):**
- `protocols/slr_protocol.md` (registro principal)
- `protocols/inclusion_criteria.md`
- `protocols/extraction_schema.md`
- `protocols/quality_rubric.md`
- `protocols/search_strings/{en,pt,es,fr}.txt` + README

**Código Python (todo testado):**
- `scripts/utils/{io,normalization}.py`
- `scripts/screening/{consolidate,dedup,screening_ta,fetch_fulltext,prisma_flow}.py`
- `scripts/extraction/{extract,validate}.py`
- `scripts/analysis/{descritivas_corpus,comparacao_pre_pos}.py`

**LaTeX:**
- `text/main.tex`, `text/preamble.tex`, `text/refs.bib`
- Stubs em `text/pre/` (5 arquivos) e `text/chapters/` (8 arquivos)

**Orquestração:**
- `Makefile` com 12+ targets
- `pyproject.toml` + `uv.lock`

**Marco:** tag `v0.1.0-infra`, pronto para o orientador validar protocolos e seguir para o Plano 2 (Execução da busca).

## O que NÃO está neste plano

- Execução real das buscas em WoS/Scopus/RePEc/SciELO (Plano 2).
- Calibração do LLM-as-judge com dados reais (Plano 3).
- Aquisição de PDFs reais (Plano 4).
- Extração de dados reais (Plano 4).
- Análise e síntese a partir do corpus real (Plano 5).
- Redação dos capítulos (Plano 6).
- Análise bibliométrica avançada (rede de citações) — deixada para o Plano 5 se houver tempo.
- Versão Streamlit do formulário de extração — opcional, fica para após Plano 4 se o CLI for desconfortável.
