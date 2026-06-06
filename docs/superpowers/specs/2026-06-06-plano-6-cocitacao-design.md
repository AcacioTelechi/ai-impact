# Plano 6 — Análise bibliométrica: acoplamento e co-citação (exploratória)

**Data:** 2026-06-06
**Status:** desenho aprovado (aguardando revisão do spec)
**Branch:** `plano-6-cocitacao`

## Objetivo

Abrir uma linha de análise bibliométrica **exploratória** sobre o corpus de incluídos,
construindo duas redes complementares e clusterizando-as:

1. **Acoplamento bibliográfico** — clusteriza os *artigos do corpus* pelo
   compartilhamento de referências. Responde: *em que sub-literaturas o corpus se
   divide?*
2. **Co-citação** — clusteriza a *base intelectual citada* (obras que o corpus cita
   em conjunto). Responde: *sobre quais fundamentos o campo se ergue?*

É um primeiro passo exploratório ("ver o que aparece"): não há compromisso de virar
capítulo do TCC nem de tocar no texto. Decidiremos a integração depois.

## Princípios de isolamento

- **Não toca o build do TCC.** Nada em `text/` é alterado; `make analysis` fica intacto.
- Saídas exploratórias em `reports/biblio/`; caches/dados intermediários em
  `data/processed/08_*`.
- **Idempotente e cacheado**: a aquisição de referências grava cache em disco e não
  re-baixa o que já tem (reprodutível, barato de re-rodar).
- Driver próprio: `make biblio` (separado de `make analysis`).

## Dados de entrada (já verificados)

- `data/processed/06_extraction.csv` — 817 incluídos; 785 com DOI utilizável (96%);
  colunas para o cruzamento: `pre_pos_chatgpt`, `janela`, `polarizacao`, `mec_*`,
  `tipo_estudo`, `score_qualidade`, `doi`, `titulo`, `ano`.
- `data/raw/searches/manual/wos/*.bib` — 876 registros WoS, **874 com
  `Cited-References`** (mediana 51 refs/registro). Campo é string:
  `Acemoglu D, 2022, ECONOMETRICA, V90, P1973, DOI 10.3982/ECTA19815.` (refs
  separadas por `.\n`).
- Scopus `.bib` **não traz referências** (export sem o campo) → cobertura via OpenAlex.

**Cobertura de referências (decisão: híbrido):**
- 455 incluídos (56%) casam com registro WoS com refs (por DOI) → fonte local.
- ~330 restantes (Scopus-only, com DOI) → OpenAlex `referenced_works`.
- Papers sem DOI (~32) e refs sem DOI ficam fora do matching (contados e reportados).
- Cobertura efetiva esperada ~96% dos incluídos.

## Arquitetura (camadas)

Pacote novo `scripts/biblio/` (espelha o padrão de `scripts/analysis/`: funções puras
testáveis + uma fronteira de I/O isolada para a rede).

### Camada 1 — Aquisição de referências (`scripts/biblio/refs_acquire.py`)

Para cada incluído com DOI, produz a lista de DOIs das obras que ele cita.

- **WoS** (quando o DOI do paper casa com a base WoS):
  - parser do campo `Cited-References` (split por `.\n`);
  - extrai DOI de cada ref via regex (`DOI\s+(10\.\S+)`), normaliza (lowercase, sem
    pontuação final).
- **OpenAlex** (demais com DOI):
  - `GET /works/https://doi.org/{doi}?mailto=<email>` → `referenced_works` (IDs `W…`);
  - resolve IDs→DOI em lote (`/works?filter=openalex_id:W1|W2|…&select=id,doi`,
    50/página, polite pool), com cache.
- **Identidade unificada da referência = DOI normalizado.** Refs sem DOI resolvível são
  descartadas do matching (prática padrão de co-citação por DOI); a contagem de descarte
  por fonte é logada.
- I/O de rede isolado atrás de `submit_fn`/cliente injetável (testável sem rede).
- **Caches**: `data/processed/08_refs_cache.json` (paper_doi → {fonte, [ref_dois]}) e
  `data/processed/08_openalex_idmap.json` (W-id → doi).
- **Saída**: `data/processed/08_paper_refs.csv` (colunas: `paper_doi`, `ref_doi`,
  `fonte`).

### Camada 2 — Construção das redes (`scripts/biblio/networks.py`)

A partir de `08_paper_refs.csv`:

- **Acoplamento bibliográfico** (`build_coupling`):
  - nós = papers do corpus (com DOI e ≥1 ref resolvida);
  - aresta(u,v) = nº de refs compartilhadas; peso normalizado por cosseno/Salton
    (`shared / sqrt(|R_u|·|R_v|)`) para não privilegiar papers com muitas refs;
  - filtra arestas com nº de refs compartilhadas brutas `< 2`.
- **Co-citação** (`build_cocitation`):
  - candidatas a nó = refs citadas por ≥ **K=3** papers do corpus;
  - aresta(a,b) = nº de papers do corpus que citam *ambas*;
  - mantém top-N nós por grau ponderado para legibilidade (default N=300, ajustável).
- Exporta GraphML para cada rede em `reports/biblio/`.

### Camada 3 — Clusterização e caracterização (`scripts/biblio/cluster.py`)

- **Louvain** (`networkx.community.louvain_communities`, ponderado, `seed` fixo para
  reprodutibilidade). Leiden (`leidenalg`) fica como upgrade opcional futuro.
- Por cluster:
  - tamanho; nós centrais (grau ponderado / betweenness);
  - termos-título salientes via TF-IDF (sklearn) dos títulos dos membros (acoplamento)
    ou das obras citadas (co-citação, quando houver título disponível).
- **Só no acoplamento** (papers do corpus têm metadados): cruza `cluster ×
  pre_pos_chatgpt`, `× polarizacao`, `× mecanismos`, `× janela` (join no
  `06_extraction.csv`) — amarra à espinha pré/pós do TCC.

### Camada 4 — Saídas (`reports/biblio/`)

- Figuras das duas redes (matplotlib, layout spring, cor = cluster) → `.png`.
- Perfis de cluster: `clusters_acoplamento.{md,csv}`, `clusters_cocitacao.{md,csv}`.
- `RESUMO.md` — narrativa curta "o que apareceu" (nº de clusters, temas, achados do
  cruzamento pré/pós), para leitura rápida.

## Driver e make

```
make biblio        # refs_acquire → networks → cluster → saídas
```
Encadeia os três módulos lendo/gravando os artefatos acima. Separado de `make analysis`.

## Dependências

- Sem dependência nova obrigatória: `networkx` (Louvain nativo), `scikit-learn`
  (TF-IDF), `requests`, `matplotlib` — todos já instalados.
- Opcional futuro: `leidenalg`/`python-igraph` para Leiden.

## Testes (TDD, padrão do repo)

Funções puras, sem rede:
- parser WoS `Cited-References` (split, extração/normalização de DOI, refs sem DOI);
- normalização de DOI;
- `build_coupling` (pesos, cosseno, filtro <2) em grafo-brinquedo;
- `build_cocitation` (limiar K, contagem de co-ocorrência) em grafo-brinquedo;
- caracterização de cluster (crosstab determinístico a partir de fixture).
A fronteira OpenAlex é testada com `submit_fn` mock.

## Caveats (a documentar nas saídas)

- Análise **exploratória/descritiva**, não-inferencial (corpus é censo, não amostra).
- Cobertura híbrida ~96% dos com-DOI; papers e refs sem DOI excluídos do matching →
  reportar nº de exclusões por fonte.
- WoS e OpenAlex podem divergir em completude de referências; a unificação por DOI
  mitiga, mas não elimina, vieses de fonte.

## Fora de escopo (YAGNI)

- Integração no texto do TCC (Cap próprio ou insumo dos Caps 04–06) — decisão posterior.
- Co-citação via citantes externos (quem cita o corpus) — exige `cited_by`, não previsto.
- Leiden / detecção hierárquica de comunidades — só se Louvain não bastar.
- Normalização de autor/afiliação/país — não é objeto desta linha.
