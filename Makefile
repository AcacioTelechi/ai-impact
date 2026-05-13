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
