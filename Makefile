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
TODAY := $(shell date +%Y-%m-%d)

# ============ Plano 2 — Busca ============

.PHONY: search-openalex
search-openalex:
	@for LANG in en pt es fr; do \
	    echo "→ OpenAlex $$LANG"; \
	    $(PYTHON) -m scripts.search.openalex_search \
	        --query-file protocols/search_strings/$$LANG.txt \
	        --lang $$LANG \
	        --output $(DATA_RAW)/openalex_$${LANG}_$(TODAY).csv \
	        --meta-output $(DATA_RAW)/openalex_$${LANG}_$(TODAY).meta.json \
	        --email $(EMAIL); \
	done

.PHONY: import-wos
import-wos:
	$(PYTHON) -m scripts.search.import_bibtex \
	    --source wos \
	    --files $(DATA_RAW)/manual/wos/*.bib \
	    --output $(DATA_RAW)/wos_$(TODAY).csv \
	    --meta-output $(DATA_RAW)/wos_$(TODAY).meta.json \
	    --query-string "$$(cat protocols/search_strings/en.txt)"

.PHONY: import-scopus
import-scopus:
	$(PYTHON) -m scripts.search.import_bibtex \
	    --source scopus \
	    --files $(DATA_RAW)/manual/scopus/*.bib \
	    --output $(DATA_RAW)/scopus_$(TODAY).csv \
	    --meta-output $(DATA_RAW)/scopus_$(TODAY).meta.json \
	    --query-string "$$(cat protocols/search_strings/en.txt)"

.PHONY: import-scielo
import-scielo:
	$(PYTHON) -m scripts.search.import_bibtex \
	    --source scielo \
	    --files $(DATA_RAW)/manual/scielo/*.bib \
	    --output $(DATA_RAW)/scielo_$(TODAY).csv \
	    --meta-output $(DATA_RAW)/scielo_$(TODAY).meta.json \
	    --query-string "$$(cat protocols/search_strings/pt.txt)"

.PHONY: search-summary
search-summary:
	$(PYTHON) -m scripts.search.summary \
	    --searches-dir $(DATA_RAW) \
	    --output-table $(TAB_DIR)/searches_summary.tex

.PHONY: search-all
search-all: import-wos import-scopus import-scielo search-summary
	@echo "✓ Busca completa. Próximo: make consolidate && make dedup"
	@echo "  Nota: OpenAlex descartado (ver protocols/slr_protocol.md §6)"

# Manter o target antigo `search` como alias do novo workflow completo.
.PHONY: search
search: search-all

# ============ Pipeline ============

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
