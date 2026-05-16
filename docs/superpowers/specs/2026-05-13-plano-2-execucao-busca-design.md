# Design: Plano 2 — Execução da Busca (F3)

**Data:** 2026-05-13
**Autor:** Acacio
**Status:** Aprovado (brainstorming)
**Próximo passo:** plano de implementação (writing-plans)
**Spec relacionado:** [Design da SLR](2026-05-13-tcc-slr-ia-trabalho-design.md)
**Plano anterior:** [Plano 1 — Infraestrutura](../plans/2026-05-13-tcc-infra-protocolos.md) (concluído, tag `v0.1.0-infra`)

---

## 1. Contexto e objetivo

A infraestrutura está pronta (scripts de screening, extração, análise, scaffolding LaTeX). O Plano 2 cobre a **fase F3 do cronograma**: executar as buscas nas bases definidas no protocolo, produzir o corpus bruto e prepará-lo para o screening (Plano 3).

### 1.1 Restrição-chave (decidida no brainstorming)

- **APIs com acesso:** OpenAlex (gratuita), Crossref (gratuita, opcional enriquecimento).
- **Sem acesso direto a API:** Web of Science e Scopus (acesso institucional só via interface web). SciELO também sem API moderna.
- **Estratégia:** workflow híbrido — API para OpenAlex, **export manual em BibTeX** para WoS/Scopus/SciELO.

### 1.2 Decisões fixadas

- Formato de export manual: **BibTeX** (parser robusto via `bibtexparser`).
- Estratégia de paginação manual: **uma consulta total, exportar em lotes** (até 500-1000 registros por arquivo .bib).
- Arquitetura: **fases independentes, base por base** (Approach B do brainstorming).

---

## 2. Arquitetura

Três componentes Python novos, cada um independente e testável, alimentam o pipeline existente do Plano 1.

```
┌─────────────────────────────┐   ┌────────────────────────────┐
│ openalex_search.py          │   │ import_bibtex.py           │
│ (API automatizada, 4 langs) │   │ (WoS/Scopus/SciELO .bib)   │
└─────────────┬───────────────┘   └─────────────┬──────────────┘
              │                                 │
              ▼                                 ▼
data/raw/searches/openalex_*.csv   data/raw/searches/{wos,scopus,scielo}_*.csv
              │                                 │
              └──────────────┬──────────────────┘
                             ▼
            (Pipeline existente do Plano 1)
            scripts.screening.consolidate
                    │
                    ▼
            scripts.screening.dedup
                    │
                    ▼
            data/processed/02_corpus_dedup.csv
                    │
                    ▼
            (Plano 3 — screening LLM)
```

### 2.1 Componentes novos

| Arquivo | Função |
|---------|--------|
| `scripts/search/openalex_search.py` | Query → paginate → flatten → CSV (uma execução por idioma) |
| `scripts/search/import_bibtex.py` | Parse .bib → normalize → CSV (acumula múltiplos lotes do mesmo source) |
| `scripts/search/snowball.py` | Forward/backward citation tracking via OpenAlex (código entregue, execução só após screening) |
| `scripts/search/summary.py` | Lê todos `.meta.json` em `data/raw/searches/` e gera relatório em LaTeX |

### 2.2 Outputs

Em `data/raw/searches/` (não versionado por design, `.gitignore` cobre):

```
data/raw/searches/
├── openalex_en_{YYYY-MM-DD}.csv      (+ .meta.json)
├── openalex_pt_{YYYY-MM-DD}.csv      (+ .meta.json)
├── openalex_es_{YYYY-MM-DD}.csv      (+ .meta.json)
├── openalex_fr_{YYYY-MM-DD}.csv      (+ .meta.json)
├── wos_{YYYY-MM-DD}.csv              (+ .meta.json)
├── scopus_{YYYY-MM-DD}.csv           (+ .meta.json)
├── scielo_{YYYY-MM-DD}.csv           (+ .meta.json)
└── manual/                           (input area para arquivos .bib brutos)
    ├── wos/*.bib
    ├── scopus/*.bib
    └── scielo/*.bib
```

`manual/` é input do `import_bibtex.py`. Os `.bib` brutos podem ficar locais (ignorados pelo git); o CSV consolidado é o "snapshot" de busca.

### 2.3 Esquema padrão do CSV

Mesmo schema do Plano 1 (`scripts/screening/consolidate.REQUIRED_COLUMNS`):

`source`, `doi`, `title`, `authors`, `year`, `abstract`, `venue`, `language`.

---

## 3. Componente: OpenAlex search

### 3.1 Interface

```python
def run(
    query_file: Path,                  # protocols/search_strings/{lang}.txt
    lang: str,                         # "en" | "pt" | "es" | "fr"
    date_from: str = "2013-01-01",
    date_to: str = "2025-12-31",
    output: Path,                      # data/raw/searches/openalex_{lang}_{YYYY-MM-DD}.csv
    meta_output: Path,                 # idem .meta.json
    email: str,                        # polite pool da OpenAlex
) -> None: ...
```

### 3.2 Lógica

1. **Conversão da string de busca.** As strings em `protocols/search_strings/*.txt` usam sintaxe estilo WoS (parênteses, `OR`, `AND`, wildcards `*`). OpenAlex aceita full-text via parâmetro `search` mas não tem booleano direto. Estratégia:
   - Extrair tokens do bloco IA (primeiro grupo OR) e tokens do bloco TRABALHO (segundo grupo OR).
   - Para cada par (token_IA, token_trabalho), rodar uma chamada à API com `search="token_IA token_trabalho"`.
   - Unir resultados; deduplicar por OpenAlex ID antes de gravar CSV.
   - Como fallback, opcionalmente reduzir para uma só query agregada com os termos mais distintivos (e.g., "artificial intelligence employment").

2. **Filtros API-side** (`filter=...`):
   - `from_publication_date:{date_from}` e `to_publication_date:{date_to}`.
   - `type:article|preprint|book-chapter`.
   - `language:{lang}` quando aplicável (campo nem sempre confiável; manter filtro pós-fato como backup).

3. **Paginação cursor-based** (`cursor=*` na primeira chamada, depois usar `meta.next_cursor`). `per_page=200` (máximo permitido).

4. **Rate limiting** — polite pool (com `email` no header `User-Agent` ou query string `mailto=`) permite ~10 req/s. Usar `tenacity` para retry exponential (3 tries) em 429/5xx.

5. **Flatten do JSON** para o schema padrão:

   | Schema | Source OpenAlex |
   |--------|------------------|
   | `source` | constante `"openalex"` |
   | `doi` | `doi` (string, sem URL prefix) |
   | `title` | `title` |
   | `authors` | `; `.join(`authorships[].author.display_name`) |
   | `year` | `publication_year` |
   | `abstract` | reconstruído a partir de `abstract_inverted_index` |
   | `venue` | `primary_location.source.display_name` (fallback `host_venue.display_name`) |
   | `language` | `language` |

6. **Filtragem pós-fato** — após receber o batch, manter só registros que matchem ao menos uma keyword de cada bloco (IA + TRABALHO) no `title` ou `abstract`. Reduz ruído sem precisar de booleano server-side.

7. **Metadata em `.meta.json`** — schema completo na seção 6.

### 3.3 Testes

- Mock de `requests.get` retornando JSON sintético com 1-3 records.
- Verifica:
  - Reconstrução correta do abstract a partir de `abstract_inverted_index`.
  - Flatten dos `authorships` em string `"Sobrenome, N.; ..."`.
  - Paginação multi-página (cursor).
  - Retry em 429 (mock retorna 429 uma vez, depois 200).
  - Filtragem pós-fato remove records sem keywords.

---

## 4. Componente: BibTeX importer

### 4.1 Interface

```python
def run(
    bibtex_files: list[Path],          # múltiplos .bib (lotes do mesmo source)
    source: str,                       # "wos" | "scopus" | "scielo"
    output: Path,                      # data/raw/searches/{source}_{YYYY-MM-DD}.csv
    meta_output: Path,                 # idem .meta.json
    query_string: str | None = None,   # texto da query, para log
) -> None: ...
```

### 4.2 Lógica

1. **Parsing** com `bibtexparser` v2 (UTF-8 robusto). Cada entry → dict.

2. **Mapeamento por source** — função separada por base, retorna dict no schema padrão:

   | Schema padrão | WoS BibTeX | Scopus BibTeX | SciELO BibTeX |
   |---------------|------------|---------------|---------------|
   | `doi` | `doi` | `doi` | `doi` |
   | `title` | `title` | `title` | `title` |
   | `authors` | `author` (split " and ", normalize "Sobrenome, N.") | idem | idem |
   | `year` | `year` | `year` | `year` |
   | `abstract` | `abstract` | `abstract` | `abstract` |
   | `venue` | `journal` ‖ `booktitle` | `journal` | `journal` |
   | `language` | `language` (default `"en"`) | `language` (default `"en"`) | inferir via `langdetect` se vazio |

3. **Limpeza** — remover chaves BibTeX literais `{...}` em valores, trim whitespace, lowercase DOI, strip URL prefixes de DOI.

4. **Dedup intra-source** — múltiplos lotes podem ter overlap (e.g., user baixou records 1-500 e 401-1000 por engano). Dedup por `(doi normalizado)` ou, se DOI vazio, por `(título normalizado + primeiro autor + ano)`. Reusa `scripts.utils.normalization` do Plano 1.

5. **Metadata em `.meta.json`** com `query_string`, `n_files`, `n_entries_raw`, `n_after_intra_dedup`.

### 4.3 Detecção de idioma

Usar `langdetect` (adicionar como dep). Aplicar a `title + " " + abstract`. Mapear códigos ISO (`pt`, `es`, `fr`, `en`) — outros idiomas marcam `language="other"` e o registro é mantido (será filtrado pelos critérios de inclusão depois, se necessário).

### 4.4 Convenção de uso

```bash
# Você baixa do WoS em lotes, salva em data/raw/searches/manual/wos/lote1.bib, etc.
python -m scripts.search.import_bibtex \
    --source wos \
    --files data/raw/searches/manual/wos/*.bib \
    --output data/raw/searches/wos_2026-05-15.csv \
    --meta-output data/raw/searches/wos_2026-05-15.meta.json \
    --query-string "$(cat protocols/search_strings/en.txt)"
```

### 4.5 Testes

- Fixtures sintéticos pequenos: 2-3 entries por source (WoS, Scopus, SciELO) representando formatos típicos.
- Verifica:
  - Mapeamento correto por source.
  - Acentos preservados no UTF-8 (português, francês, espanhol).
  - Autores normalizados de `"Smith, John and Doe, Jane"` para `"Smith, J.; Doe, J."`.
  - Dedup intra-source quando dois arquivos têm overlap.
  - Detecção de idioma quando campo BibTeX está vazio.

---

## 5. Componente: Snowballing

`scripts/search/snowball.py` — **código entregue no Plano 2, execução só depois do screening inicial** (Plano 3+).

### 5.1 Interface

```python
def backward(seed_dois: list[str], email: str, output: Path) -> None: ...
def forward(seed_dois: list[str], email: str, output: Path) -> None: ...
```

### 5.2 Lógica

1. **Backward** (refs citadas pelos seeds): para cada DOI, GET `https://api.openalex.org/works/doi:{doi}` → ler `referenced_works[]` → fetch metadata de cada (batch GET).
2. **Forward** (artigos que citam os seeds): para cada DOI, GET `https://api.openalex.org/works?filter=cites:W{id}` (paginar).
3. **Filtro temporal**: manter só refs com `publication_year ∈ [2013, 2025]`.
4. **Schema**: mesmo CSV padrão; `source = "snowball-backward"` ou `"snowball-forward"`.

### 5.3 Quando rodar

Após o screening inicial produzir o corpus de estudos incluídos, identificar os ~20 estudos mais centrais por centralidade em rede de citações (lógica no Plano 5 — análise). Esses viram seeds.

### 5.4 Testes

- Mock de OpenAlex API.
- Verifica: extração correta de `referenced_works`, paginação do forward, dedup contra corpus principal (não duplicar estudos já incluídos).

---

## 6. Metadados de busca e relatório

### 6.1 Schema da `.meta.json`

Toda execução grava um `.meta.json` com o mesmo prefixo do CSV:

```json
{
  "base": "openalex|wos|scopus|scielo",
  "lang": "en|pt|es|fr|null",
  "query_used": "string completa da query (multilinha OK)",
  "query_string_version": "1.0",
  "date_from": "2013-01-01",
  "date_to": "2025-12-31",
  "executed_at_utc": "ISO 8601 timestamp",
  "n_hits_raw": 2453,
  "n_after_filters": 2104,
  "csv_sha256": "hex digest dos bytes do CSV",
  "tool_version": "ai-impact 0.2.0",
  "notes": "texto livre opcional"
}
```

`csv_sha256` é computado pelo helper existente `scripts.utils.io.sha256_file` — garante que o CSV não foi modificado depois do registro.

### 6.2 Script de resumo

`scripts/search/summary.py`:

```python
def run(searches_dir: Path, output_table: Path) -> None: ...
```

Lê todos os `*.meta.json` em `searches_dir`, monta um DataFrame, e escreve uma tabela LaTeX em `text/tables/searches_summary.tex`:

| Base | Data | Idioma | n_brutos | n_filtrados |
|------|------|--------|----------|-------------|
| openalex | 2026-05-15 | en | 2453 | 2104 |
| ... | ... | ... | ... | ... |
| **Total** | | | **N** | **M** |

Essa tabela entra no capítulo de metodologia (`text/chapters/03_metodologia.tex`).

### 6.3 Testes

- Fixtures com 3 `.meta.json` sintéticos.
- Verifica: agrupamento por base, soma correta, output LaTeX bem formado.

---

## 7. Orquestração via Makefile

Novos targets:

```makefile
.PHONY: search-openalex
search-openalex:
	$(PYTHON) -m scripts.search.openalex_search --query-file protocols/search_strings/en.txt --lang en ...
	$(PYTHON) -m scripts.search.openalex_search --query-file protocols/search_strings/pt.txt --lang pt ...
	$(PYTHON) -m scripts.search.openalex_search --query-file protocols/search_strings/es.txt --lang es ...
	$(PYTHON) -m scripts.search.openalex_search --query-file protocols/search_strings/fr.txt --lang fr ...

.PHONY: import-wos import-scopus import-scielo
import-wos:
	$(PYTHON) -m scripts.search.import_bibtex --source wos --files data/raw/searches/manual/wos/*.bib ...

import-scopus:
	$(PYTHON) -m scripts.search.import_bibtex --source scopus --files data/raw/searches/manual/scopus/*.bib ...

import-scielo:
	$(PYTHON) -m scripts.search.import_bibtex --source scielo --files data/raw/searches/manual/scielo/*.bib ...

.PHONY: search-summary
search-summary:
	$(PYTHON) -m scripts.search.summary --searches-dir data/raw/searches --output-table text/tables/searches_summary.tex

.PHONY: search-all
search-all: search-openalex import-wos import-scopus import-scielo search-summary
```

`search-all` é informativo (depende de você ter baixado os `.bib`); o uso real será iterativo (rodar `import-wos` quando tiver os `.bib` do WoS, etc.).

---

## 8. Dependências novas

Adicionar ao `pyproject.toml`:

- `bibtexparser>=2.0` — parser BibTeX (versão 2.x da biblioteca, API nova).
- `langdetect>=1.0.9` — detecção de idioma para BibTeX sem campo `language`.

---

## 9. Critérios de sucesso

Todos devem ser satisfeitos para fechar o Plano 2:

1. **OpenAlex executado em 4 idiomas** — 4 pares `openalex_{en,pt,es,fr}_*.csv` + `.meta.json`.
2. **WoS, Scopus, SciELO importados** — 3 pares `{wos,scopus,scielo}_*.csv` + `.meta.json`.
3. **`scripts.screening.consolidate` lê todos os CSVs sem erro** → `data/processed/01_corpus_bruto.csv`.
4. **`scripts.screening.dedup --no-embeddings` roda** → `02_corpus_dedup.csv`.
5. **Volume esperado:** corpus bruto entre 1.500 e 10.000 records; dedup remove ≥10%.
6. **`search/summary.py`** gera `text/tables/searches_summary.tex`.
7. **`make test`** segue verde (testes novos passam; nenhum regredido).
8. **Tag `v0.2.0-busca`** criada após confirmar 1–7.

## 10. Riscos e mitigações

| Risco | Probabilidade | Mitigação |
|-------|---------------|-----------|
| OpenAlex retorna muito ruído | Alta | Filtros pós-API por keywords; iterar query antes do screening |
| BibTeX do Scopus tem campos quebrados (chaves escapadas, encoding) | Média | Testes com fixtures reais pequenos; fallback de encoding latin-1 |
| Volume excessivo (>10k) | Média | Refinar query antes do consolidate; relatório `n_hits_raw` alerta cedo |
| Volume insuficiente (<500) | Baixa | Indica problema na string — revisar antes de seguir |
| Você fica sem tempo para baixar os `.bib` | Média | `import-{wos,scopus,scielo}` aceita qualquer .bib que esteja na pasta; pode rodar iterativamente |
| Acentos perdidos no encoding | Média | UTF-8 forçado em todos I/O; testes com acentos |
| OpenAlex API muda formato do `abstract_inverted_index` | Baixa | Função de reconstrução isolada e testada |

## 11. Não-objetivos (escopo explicitamente fora)

- Busca em periódicos individuais (AER, JoLE, etc.) — deferred; só se OpenAlex não cobrir.
- **Execução** do snowballing — código entregue mas execução só após screening inicial (Plano 3+).
- Calibração do threshold de inclusão/exclusão do LLM-as-judge — Plano 3.
- Re-extração de queries antigas — cada execução é um snapshot; mudou a query, é uma nova execução.

---

## 12. Próximos passos

Após validação deste design pelo autor:

1. **Plano de implementação detalhado** via `writing-plans`, decomposto em tarefas executáveis (TDD).
2. **Execução** via `subagent-driven-development`.
3. **Validação do Plano 2** — quando todos os critérios de sucesso forem satisfeitos, criar tag `v0.2.0-busca` e seguir para Plano 3 (screening).
