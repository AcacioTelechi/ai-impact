# Design: TCC — Revisão Sistemática sobre Impactos da IA no Mercado de Trabalho

**Data:** 2026-05-13
**Autor:** Acacio
**Status:** Aprovado (brainstorming)
**Próximo passo:** plano de implementação (writing-plans)

---

## 1. Contexto e objetivos

Este documento define o design da Revisão Sistemática da Literatura (SLR) que será o TCC de Bacharelado em Economia. O texto final é em **português (BR)** e composto em **LaTeX**. O prazo é de **um semestre (4–5 meses)**, com orientador já definido.

### 1.1 Pergunta de pesquisa

> Como a literatura econômica caracterizou os efeitos da inteligência artificial sobre o nível e a composição do emprego entre 2013 e 2025, e em que medida o surgimento da IA generativa (pós-novembro de 2022) representa uma ruptura ou continuidade em relação ao consenso anterior?

### 1.2 Objetivo geral

Realizar uma revisão sistemática da literatura econômica sobre o impacto da IA no emprego (deslocamento e criação de postos), comparando achados, mecanismos e métodos antes e depois da difusão de LLMs.

### 1.3 Objetivos específicos

1. Mapear sistematicamente a literatura econômica sobre IA e emprego entre 2013–2025, dividida em três janelas:
   - **2013–2017:** era da automação (Frey-Osborne, Autor)
   - **2018–2022:** era de deep learning / ML aplicado (Acemoglu-Restrepo, Webb, Felten et al.)
   - **2022–2025:** era de IA generativa / LLMs (Eloundou et al., evidência empírica pós-ChatGPT)
2. Caracterizar os mecanismos teóricos propostos para o efeito da IA no emprego (deslocamento, reinstalação, complementaridade, criação de novas tarefas).
3. Sistematizar os achados empíricos quanto a sinal, magnitude, ocupações/setores afetados e robustez metodológica.
4. Comparar os achados pré- e pós-ChatGPT, identificando rupturas e continuidades.
5. Discutir as implicações da literatura revisada para o mercado de trabalho brasileiro, com exercício de cruzamento de exposição ocupacional internacional (Felten-AIOE/Eloundou) com CBO brasileiro **se os dados forem viáveis no prazo**.

### 1.4 Hipótese de trabalho

> A literatura pré-ChatGPT convergia para um quadro de "polarização do emprego" com risco concentrado em tarefas rotineiras de baixa qualificação; a literatura pós-ChatGPT desloca esse risco para tarefas cognitivas de alta qualificação, sugerindo uma ruptura do regime tecnológico anterior.

A hipótese é tratada como referência analítica, não como teste de hipótese formal (a SLR é narrativa-estruturada, não meta-analítica).

### 1.5 Abordagem metodológica geral

Foi adotada a **abordagem C** entre três alternativas avaliadas: extração estruturada em campos fixos por estudo, com **comparação pareada pré/pós-ChatGPT como capítulo central**. Os três períodos aparecem como subseções dentro do capítulo de resultados; o eixo analítico é o quadro comparativo.

Princípios:
- Protocolo registrado em git antes da execução da busca.
- Pipeline reprodutível em Python (`make` orquestra cada etapa).
- Tabelas e figuras nunca escritas à mão — sempre geradas a partir de `data/processed/06_extraction.csv`.

---

## 2. Critérios de inclusão e exclusão

### 2.1 Inclusão

| Dimensão | Critério |
|----------|----------|
| Período | Publicado entre 01/01/2013 e 31/12/2025 |
| Idioma | Inglês, português, espanhol ou francês |
| Tipo de IA | ML supervisionado/não-supervisionado, deep learning, NLP, visão computacional, LLMs/IA generativa, robôs com componente de IA |
| Desfecho | Efeito sobre emprego: nível, criação/destruição de postos, exposição ocupacional, demanda por trabalho |
| Abordagem | Empírica (qualquer método quantitativo), teórica formal, ou de exposição ocupacional |
| Tipo de publicação | Artigos em periódicos com revisão por pares; working papers de instituições reconhecidas (NBER, IZA, CEPR, BIS, OECD, IPEA, BCB, FGV); capítulos de livro indexados |
| Foco geográfico | Qualquer país ou conjunto de países |

### 2.2 Exclusão

| Dimensão | Critério |
|----------|----------|
| Tema fora do escopo | Estudos focados apenas em produtividade individual sem ligação com emprego; estudos sobre IA em educação, saúde, ética, governança sem conexão com mercado de trabalho |
| Tecnologia fora do escopo | Robótica industrial pré-IA, automação puramente mecânica, sistemas especialistas legados sem componente de aprendizado |
| Tipo de documento | Editoriais, resenhas, opiniões, posts de blog, white papers sem metodologia explícita, monografias e teses não publicadas em periódico |
| Acessibilidade | Artigos sem texto completo acessível após 30 dias de esforço (inclusive contato com autores) |
| Qualidade | Estudos sem metodologia descrita ou sem evidência verificável |

### 2.3 Justificativa do recorte temporal (01/01/2013)

O ponto de corte se sustenta em quatro fatores convergentes:

1. **Inflexão tecnológica em IA.** A revolução do deep learning é convencionalmente datada em dezembro de 2012 (AlexNet em ImageNet). Estudos econômicos pré-2013 tratavam de IT/computadores em sentido amplo (literatura SBTC/RBTC: Katz & Murphy 1992; Autor, Levy & Murnane 2003), não de IA como tecnologia identificável.
2. **Inflexão metodológica na economia do trabalho.** Em 2013 emergem simultaneamente Frey & Osborne (escore de probabilidade de automação por ocupação) e Autor (consolidação do *task approach* em JEP). Esses dois trabalhos fornecem o template metodológico de toda a literatura posterior.
3. **Inflexão bibliométrica.** Bases bibliográficas mostram crescimento exponencial de publicações no nexo *AI + labor* a partir de 2013–2014, partindo de base quase nula no quinquênio anterior. Esse padrão será documentado no capítulo de resultados.
4. **Coerência da comparação proposta.** Para que a comparação pré/pós-ChatGPT seja informativa, é necessária uma janela pré-2022 longa o suficiente (≈10 anos) para o corpus exibir evolução interna.

**Trade-off declarado:** trabalhos seminais como Acemoglu & Autor (2011, *Handbook of Labor Economics*) e Brynjolfsson & McAfee (2011, *Race Against the Machine*) ficam fora do corpus sistemático, mas serão tratados como antecedentes no referencial teórico.

---

## 3. Estratégia de busca

### 3.1 Bases de dados

| Base | Cobertura | Função |
|------|-----------|--------|
| Web of Science (Core Collection) | Multidisciplinar, alta seletividade | Padrão-ouro; análise bibliométrica |
| Scopus | Multidisciplinar, ampla | Cobertura complementar; working papers indexados |
| RePEc / IDEAS | Working papers de economia | Captura literatura cinzenta (NBER, IZA, CEPR, BIS, OECD, IPEA, BCB, FGV) |
| SciELO | Periódicos latino-americanos | Cobertura em pt/es |
| Busca direta em periódicos | Economia | Substitui EconLit (sem acesso institucional): AER, JoLE, ReStud, JEEA, *Labour Economics*, *ILR Review*, *Industrial Relations*, *Journal of Human Resources*, RBE, Estudos Econômicos |
| Google Scholar | Geral | **Apenas para snowballing** |

Cada base será consultada via API quando disponível (WoS API, Scopus API, OpenAlex como espelho/complemento). Logs de cada query (data, string, número de resultados) são salvos em `data/raw/searches/`.

### 3.2 Núcleo conceitual da string de busca

```
BLOCO_IA: ("artificial intelligence" OR "machine learning" OR "deep learning"
           OR "neural network*" OR "natural language processing" OR "NLP"
           OR "large language model*" OR "LLM" OR "generative AI"
           OR "ChatGPT" OR "GPT" OR "foundation model*" OR "automation")

BLOCO_TRABALHO: ("employment" OR "labor market*" OR "labour market*"
                OR "jobs" OR "workforce" OR "occupation*" OR "wages"
                OR "labor demand" OR "task displacement" OR "job creation"
                OR "job destruction")

BLOCO_EFEITO: ("impact*" OR "effect*" OR "exposure" OR "displacement"
              OR "automation risk" OR "substitution" OR "complementarity")

QUERY_FINAL: BLOCO_IA AND BLOCO_TRABALHO AND BLOCO_EFEITO
```

### 3.3 Adaptação por idioma

Replicada em pt/es/fr com vocabulário equivalente. Strings finais em `protocols/search_strings/`:
- **Português:** `("inteligência artificial" OR "aprendizado de máquina" OR "automação" OR "IA generativa") AND ("emprego" OR "mercado de trabalho" OR "ocupações" OR "salários") AND ("impacto*" OR "efeito*" OR "deslocamento" OR "substituição")`
- **Espanhol:** análogo (`"inteligencia artificial"`, `"empleo"`, `"mercado laboral"`, ...)
- **Francês:** análogo (`"intelligence artificielle"`, `"emploi"`, `"marché du travail"`, ...)

### 3.4 Campos e limitadores

- **Campos:** título + resumo + palavras-chave (TS=, TITLE-ABS-KEY)
- **Período:** 2013-01-01 a 2025-12-31
- **Tipos:** artigos de periódico, working papers das instituições listadas, capítulos indexados
- **Áreas (quando aplicável):** Economics, Business, Public Administration, Social Sciences

### 3.5 Snowballing

Após primeira rodada de screening, dois passes:
1. **Backward:** referências dos ≈ 20 estudos mais centrais por centralidade na rede de citações.
2. **Forward:** quem cita esses estudos (Google Scholar / OpenAlex API).

Os novos passam pelos mesmos critérios.

### 3.6 Reprodutibilidade

- `protocols/search_protocol.md` — protocolo final.
- `data/raw/searches/{base}_{YYYY-MM-DD}.csv` — exports brutos.
- `scripts/search/run_search.py` — orquestrador.
- Hash SHA-256 de cada export para imutabilidade.

---

## 4. Workflow de screening e seleção

PRISMA define quatro etapas: Identification → Screening → Eligibility → Inclusion.

### 4.1 Identification (consolidação)

- **Script:** `scripts/screening/01_consolidate.py`.
- **Output:** `data/processed/01_corpus_bruto.csv` (colunas: `source`, `doi`, `title`, `authors`, `year`, `abstract`, `venue`, `language`).
- **PRISMA:** `n_identified` por base.

### 4.2 Deduplicação

- **Script:** `scripts/screening/02_dedup.py`.
- **Três passes:**
  1. DOI normalizado.
  2. (título normalizado + primeiro autor + ano).
  3. Similaridade de embedding (`all-MiniLM-L6-v2`, cos-sim ≥ 0.95) com revisão manual dos candidatos.
- **Output:** `data/processed/02_corpus_dedup.csv` + `02_dedup_decisions.csv`.

### 4.3 Screening por título e resumo (LLM + humano)

Volume típico: 2.000–5.000 registros pós-dedup.

**Estratégia híbrida:**

1. **Pré-filtragem por LLM-as-judge** (Claude Sonnet 4.6 ou GPT-4o-mini). Cada registro recebe:
   - `decisao_llm`: {incluir, excluir, dúvida}
   - `justificativa_llm`: 1–2 frases citando critério
   - `confianca_llm`: 0–1
2. **Revisão humana:**
   - 100% dos `incluir` e `dúvida`.
   - Amostra estratificada de 10–15% dos `excluir`, com sobre-amostragem de `confianca_llm < 0.7`.
   - Se erro do LLM em rejeições > 5%, recalibrar threshold e re-rodar.
3. **κ de Cohen** entre LLM e humano vira nota metodológica.

- **Script:** `scripts/screening/03_screening_ta.py` com cache local de respostas e retry/backoff.
- **Output:** `03_screening_ta.csv`, `03_incluidos_ta.csv`.

**Limitação:** revisor único (SLR canônico exige dois). A nota metodológica admite a limitação e mitiga via dupla revisão sua com intervalo (≥ 1 semana) em amostra de 10% dos casos limítrofes.

### 4.4 Eligibility (texto completo)

Volume esperado: 150–400 papers.

- **Aquisição:** `scripts/screening/04_fetch_fulltext.py` tenta DOI → Unpaywall → acesso institucional → e-mail aos autores.
- **Limite:** 30 dias de esforço por paper; inacessíveis vão para `data/processed/04_inacessiveis.csv` (reportar em PRISMA).
- **Triagem 100% manual:**
  - Decisão final: {incluído, excluído}
  - Motivo padronizado (códigos `E1`...`E5`).
  - Score de qualidade preliminar (1–5).
- **Tooling:** Zotero + Better BibTeX (gerencia PDFs locais); decisões em `data/processed/04_eligibility.csv`.

### 4.5 Inclusão final e PRISMA flow

- **Script:** `scripts/screening/05_prisma_flow.py` gera diagrama PRISMA 2020 em TikZ → `text/figures/prisma_flow.tex`.
- **Output do corpus:** `data/processed/05_corpus_final.csv`.

---

## 5. Esquema de extração de dados

Cada estudo do corpus final vira uma linha em `data/processed/06_extraction.csv`. Os blocos abaixo são fixados antes do início da extração para evitar viés ex-post.

### 5.1 Blocos de campos

**Bloco A — Identificação**
`id`, `doi`, `titulo`, `autores`, `ano`, `periodico`, `tipo_pub` (journal | working paper | book chapter), `pais_estudo`, `periodo_dados`.

**Bloco B — Classificação temporal**
`janela` ∈ {2013–2017, 2018–2022, 2022–2025}; `pre_pos_chatgpt` ∈ {pre, pos} (pivô = nov/2022); `tecnologia_focada` ∈ {automação, ML/preditiva, deep learning, IA generativa/LLMs, robôs+IA, geral}.

**Bloco C — Tipo de evidência**
`tipo_estudo` ∈ {exposição ocupacional, evidência macro/setorial, firma/freelancer, teórico/modelo, survey/revisão}; `metodo_empirico` ∈ {OLS, DiD, IV, RDD, evento-estudo, estrutural, ML, descritivo, modelo teórico, n/a}; `unidade_analise` ∈ {ocupação, indústria, firma, indivíduo, país, região, múltipla}; `fonte_dados` (texto curto).

**Bloco D — Mecanismos teóricos** (framework Acemoglu-Restrepo)
`mec_deslocamento`, `mec_reinstalacao`, `mec_complementaridade`, `mec_demanda_agregada` ∈ {sim, não, n/a}; `mec_outros` (texto livre).

**Bloco E — Achados sobre emprego** *(campo mais crítico)*
`sinal_efeito` ∈ {negativo, positivo, nulo, ambíguo, n/a}; `magnitude_reportada` (texto livre normalizado); `magnitude_normalizada` (elasticidade ou % comparável quando possível); `ocupacoes_afetadas` (códigos SOC/CBO de alto nível ou texto curto); `polarizacao` ∈ {alta-quali em risco, baixa-quali em risco, ambos, neutro, n/a}; `horizonte` ∈ {curto prazo, médio, longo, projeção}.

**Bloco F — Qualidade e robustez**
`score_qualidade` 1–5 (rubrica abaixo); `limitacoes_declaradas` (texto livre); `replicavel` ∈ {sim, parcial, não, n/a}; `revisado_por_pares` ∈ {sim, não}.

**Bloco G — Notas livres**
`nota_extracao` (livre); `citacoes_chave` (outros papers do corpus que este estudo cita ou contraria).

### 5.2 Rubrica de qualidade

| Score | Critério |
|-------|----------|
| 5 | Periódico top-5/top-field, identificação causal crível, robustez extensa, código/dados públicos |
| 4 | Periódico bom, identificação razoável, robustez presente, replicabilidade parcial |
| 3 | Working paper de instituição reconhecida ou periódico médio; identificação descritiva/correlacional bem feita |
| 2 | Evidência sugestiva, identificação fraca, poucos controles |
| 1 | Apenas descritivo simples ou projeção sem base empírica clara |

### 5.3 Workflow de extração

- **Script:** `scripts/extraction/06_extract.py` apresenta cada PDF e abre formulário (CLI ou Streamlit local).
- **Assistência LLM:** Claude com PDF anexado sugere pré-preenchimento dos campos B, C, D; flag `revisto_humano` sempre `True` na versão final.
- **Validação:** `scripts/extraction/07_validate.py` checa consistência (sinal vs. mecanismos, anos plausíveis) e lista campos inconsistentes.

---

## 6. Síntese e análise comparativa

Tudo é gerado a partir de `06_extraction.csv` por scripts em `scripts/analysis/`. Re-executar `make analysis` regenera todas as tabelas e figuras.

### 6.1 Camada 1 — Descritivas do corpus

(Seção introdutória do capítulo de Resultados.)

- Publicações por ano (barra + acumulada).
- Distribuição por janela, idioma, país-foco, tipo de publicação, base.
- Top periódicos e working paper series.
- Rede de citações intra-corpus (grafo com clusters por janela).
- Núcleo de palavras-chave por janela (n-gramas ou tópicos).

Saída: ≈5 figuras e 2 tabelas.

### 6.2 Camada 2 — Síntese por janela

Para cada janela (2013–2017, 2018–2022, 2022–2025), mesma estrutura:
1. Quantos estudos, que tipos, que países, que metodologias.
2. Mecanismos teóricos dominantes (tabela de frequência).
3. Achados sobre emprego (tabela-resumo + narrativa).
4. 5–10 estudos âncora discutidos com profundidade.
5. Tensões internas à janela.

Saída: 3 seções de ≈ 8–15 páginas cada com tabelas padronizadas para facilitar comparação.

### 6.3 Camada 3 — Análise comparativa pré/pós-ChatGPT (capítulo central)

1. **Tabela-síntese pareada** (linha = dimensão; colunas = pré / pós; conteúdo = % do corpus).
2. **Quatro eixos narrativos:**
   - Eixo 1: Quem está em risco? — inversão do gradiente de qualificação.
   - Eixo 2: Qual o mecanismo? — deslocamento puro vs. complementaridade/reinstalação.
   - Eixo 3: Como se mede? — evolução metodológica (exposição ocupacional → evidência empírica de mercado).
   - Eixo 4: O que sabemos vs. o que projetamos? — proporção de projeções vs. evidência observacional.
3. **Mapa de continuidades** — onde a literatura pós-2022 confirma ou estende achados anteriores.
4. **Mapa de rupturas** — claims pré-2022 contrariados pela literatura pós-2022.
5. **Discussão de viés temporal** — corpus pós-2022 é jovem e majoritariamente working papers; limita conclusões. **Nota obrigatória.**

Saída: capítulo de ≈ 25–35 páginas, 4–6 figuras, 3–5 tabelas comparativas.

### 6.4 Implicações para o Brasil

Capítulo curto (≈ 10–15 páginas):
1. O que a literatura brasileira do corpus diz.
2. Como o perfil ocupacional brasileiro (CBO, formalidade) interage com achados internacionais.
3. **Exercício condicional:** cruzamento de exposição-Felten / Eloundou com CBO via correspondência ISCO-CBO, **se os dados forem viáveis no prazo**. Caso contrário, vira nota de pesquisa futura.
4. Limites da extrapolação (regime tecnológico, complementaridade vs. substituição em economia em desenvolvimento).

---

## 7. Estrutura do repositório

```
ai-impact/
├── README.md
├── Makefile                         # search, screen, extract, analysis, pdf, all, clean
├── .gitignore
├── pyproject.toml                   # uv
├── .python-version
│
├── protocols/
│   ├── slr_protocol.md
│   ├── search_strings/
│   ├── inclusion_criteria.md
│   ├── extraction_schema.md
│   └── quality_rubric.md
│
├── data/
│   ├── raw/
│   │   └── searches/{base}_{YYYY-MM-DD}.csv
│   └── processed/
│       ├── 01_corpus_bruto.csv
│       ├── 02_corpus_dedup.csv
│       ├── 02_dedup_decisions.csv
│       ├── 03_screening_ta.csv
│       ├── 03_incluidos_ta.csv
│       ├── 04_eligibility.csv
│       ├── 04_inacessiveis.csv
│       ├── 05_corpus_final.csv
│       └── 06_extraction.csv
│
├── scripts/
│   ├── search/
│   │   └── run_search.py
│   ├── screening/
│   │   ├── 01_consolidate.py
│   │   ├── 02_dedup.py
│   │   ├── 03_screening_ta.py
│   │   ├── 04_fetch_fulltext.py
│   │   └── 05_prisma_flow.py
│   ├── extraction/
│   │   ├── 06_extract.py
│   │   └── 07_validate.py
│   ├── analysis/
│   │   ├── build_tables.py
│   │   ├── build_figures.py
│   │   ├── descritivas_corpus.py
│   │   ├── rede_citacoes.py
│   │   └── comparacao_pre_pos.py
│   └── utils/
│
├── text/
│   ├── main.tex
│   ├── preamble.tex
│   ├── refs.bib                     # exportado de Zotero (Better BibTeX), commitado
│   ├── pre/
│   │   ├── capa.tex
│   │   ├── folha_rosto.tex
│   │   ├── resumo.tex
│   │   ├── abstract.tex
│   │   └── agradecimentos.tex
│   ├── chapters/
│   │   ├── 01_introducao.tex
│   │   ├── 02_referencial_teorico.tex
│   │   ├── 03_metodologia.tex
│   │   ├── 04_resultados_descritivas.tex
│   │   ├── 05_resultados_janelas.tex
│   │   ├── 06_comparacao_pre_pos.tex
│   │   ├── 07_implicacoes_brasil.tex
│   │   └── 08_consideracoes_finais.tex
│   ├── figures/
│   └── tables/
│
├── notebooks/                       # exploração ad-hoc
│
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-05-13-tcc-slr-ia-trabalho-design.md
```

### 7.1 Princípios

1. **Numeração nos scripts (`01_`, `02_`, …)** sinaliza ordem do pipeline.
2. **`data/raw/` é imutável**; toda transformação cai em `data/processed/`.
3. **`text/` é o produto final**; tudo fora dele pode ser regenerado.
4. **`protocols/` é o contrato** — registrado em git antes da busca.
5. **Tabelas e figuras nunca à mão** — sempre `\input{}` / `\includegraphics{}` de arquivos gerados.

### 7.2 Build

`Makefile` com targets: `search`, `screen`, `extract`, `analysis`, `pdf` (`latexmk -pdf -outdir=build text/main.tex`), `all`, `clean`.

### 7.3 Dependências

- **Python (gerenciado por `uv`):** `pandas`, `numpy`, `matplotlib`, `seaborn`, `networkx`, `sentence-transformers`, `anthropic`, `requests`, `tenacity`, `streamlit`.
- **LaTeX:** `latexmk`, biblatex+biber, TikZ, `booktabs`, `siunitx`, `subcaption`.
- **Externo:** Zotero + Better BibTeX para gerenciar PDFs e exportar `refs.bib`.

---

## 8. Cronograma (4–5 meses, ≈15 h/semana)

| Fase | Semanas | Saída | Risco |
|------|---------|-------|-------|
| F1 — Protocolo registrado | 1–2 | `protocols/slr_protocol.md` final, validado pelo orientador; rubrica calibrada em 5 papers-teste | Baixo |
| F2 — Setup técnico | 1–2 | Repo estruturado, scripts esqueleto, APIs configuradas, Zotero+Better BibTeX | Baixo |
| F3 — Busca e consolidação | 2–3 | `01_corpus_bruto.csv`, `02_corpus_dedup.csv`, relatório de hits por base | Médio |
| F4 — Screening título+resumo | 3 | `03_screening_ta.csv`, κ LLM × humano, lista para texto completo | Médio |
| F5 — Aquisição de PDFs e elegibilidade | 3 | PDFs locais, `04_eligibility.csv`, `05_corpus_final.csv` (≈80–150 papers), diagrama PRISMA | **Alto** |
| F6 — Extração estruturada | 4–5 | `06_extraction.csv` completo, validação automática | **Alto** |
| F7 — Análise e síntese | 3 | Todas as tabelas e figuras em `text/tables/` e `text/figures/` | Médio |
| F8 — Redação | 4–5 | Capítulos 1–8, `refs.bib` consolidado, PDF compilado | Médio |
| F9 — Revisão, ajustes e defesa | 2 | Revisão com orientador, ajustes de banca, apresentação | Médio |

Total bruto ≈ 23 semanas; cabe em 4–5 meses com sobreposição. Redação começa cedo (intro + metodologia durante F3–F5).

### 8.1 Milestones de decisão

- **Fim F1:** orientador valida protocolo; sem isso, não passa para F3.
- **Fim F4:** se corpus pós-screening estiver fora de [80, 400], recalibrar critérios antes de F5.
- **Fim F6:** se Bloco E tiver muitos `n/a`, repensar análise comparativa.

### 8.2 Ordem de cortes se cronograma estourar

1. Capítulo 7 (Brasil) vira nota curta sem cruzamento Felten×CBO.
2. Rede de citações simplificada para tabela descritiva.
3. Janela 2013–2017 vira seção curta (não capítulo).
4. **Não cortar:** capítulo comparativo pré/pós-ChatGPT.

---

## 9. Limitações declaradas

1. **Revisor único.** Mitigado por dupla revisão pessoal com intervalo (10% de casos limítrofes).
2. **Uso de LLM no screening.** Justificado por volume e literatura recente (Wagner et al. 2023, Khraisha et al. 2024); auditoria estratificada e κ reportados.
3. **Corpus pós-2022 jovem.** Maior parte working papers; conclusões da camada 3 são preliminares.
4. **Sem acesso a EconLit.** Substituído por RePEc + busca direta em periódicos-chave; trade-off declarado em capítulo de metodologia.
5. **Janela 2013–2025 exclui antecedentes seminais** (Acemoglu-Autor 2011, Brynjolfsson-McAfee 2011); tratados como referencial teórico.

---

## 10. Próximos passos

Após validação deste design pelo autor:
1. **Plano de implementação** detalhado via skill `writing-plans`, decomposto em tarefas executáveis com critérios de verificação por etapa.
2. **Validação do protocolo pelo orientador** antes da F3.
3. **Início da F1 e F2 em paralelo** assim que o plano estiver aprovado.
