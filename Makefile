# Makefile
# Provides convenient shortcuts for common development tasks.

.PHONY: install test add batch clean help

# Default variables (can be overridden from command line)
FILE ?= sentences.txt
DECK ?= "French Batch"
SENTENCE ?= "Bonjour"
SOURCE_LANG ?= fr
TARGET_LANG ?= en
COLUMN ?= sentence
ARGS =

# --- Core Commands ---

install: ## Install dependencies using Poetry and create necessary directories
	poetry install
	mkdir -p output storage/audio cache logs

test: ## Run configuration tests
	poetry run python infrastructure/cli/main.py test

add: ## Generate a single flashcard (Usage: make add SENTENCE="..." [SOURCE_LANG=fr TARGET_LANG=en])
	@echo "Generating single card for: $(SENTENCE)"
	poetry run python infrastructure/cli/main.py add "$(SENTENCE)" --deck-name "$(DECK)" -s $(SOURCE_LANG) -t $(TARGET_LANG) $(ARGS)

batch: ## Generate a deck from a file (Usage: make batch FILE=... [DECK="..." SOURCE_LANG=fr TARGET_LANG=en COLUMN=sentence])
	@echo "Generating deck '$(DECK)' from file: $(FILE)"
	poetry run python infrastructure/cli/main.py batch $(FILE) --deck-name "$(DECK)" --column $(COLUMN) -s $(SOURCE_LANG) -t $(TARGET_LANG) $(ARGS)

clean: ## Remove generated output files, cached items, and logs
	rm -rf output/*
	rm -rf cache/*
	rm -rf storage/audio/*
	# Optionally clean logs, be careful if logs are important
	# rm -f logs/*.log

# --- Help ---

help: ## Show this help message
	@echo "Anki Card Generator Makefile"
	@echo ""
	@echo "Usage: make [command] [VARIABLE=value ...]"
	@echo ""
	@echo "Commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Variables for 'add' and 'batch':"
	@echo "  SENTENCE       (for add)   The source sentence (default: 'Bonjour')"
	@echo "  FILE           (for batch) Path to the input file (default: 'sentences.txt')"
	@echo "  DECK           (for add/batch) Name of the Anki deck (default: 'French Practice'/'French Batch')"
	@echo "  SOURCE_LANG    (for add/batch) Source language code (default: 'fr')"
	@echo "  TARGET_LANG    (for add/batch) Target language code (default: 'en')"
	@echo "  COLUMN         (for batch)   CSV column name if using CSV (default: 'sentence')"
	@echo "  ARGS           (for add/batch) Extra CLI arguments (e.g., ARGS='--audio --no-grammar')"
	@echo ""
	@echo "Examples:"
	@echo "  make install"
	@echo "  make test"
	@echo "  make add SENTENCE='Guten Tag' SOURCE_LANG=de TARGET_LANG=en DECK='German Greetings'"
	@echo "  make batch FILE=german_words.csv DECK='German Vocab' SOURCE_LANG=de COLUMN='GermanWord' ARGS='--no-grammar'"
	@echo "  make clean"

# Prevent .PHONY targets from interfering with files of the same name
.DELETE_ON_ERROR:
