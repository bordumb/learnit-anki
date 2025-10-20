# Makefile
.PHONY: install test add batch clean help

install:
	poetry install
	mkdir -p output storage/audio cache

test:
	poetry run python infrastructure/cli/main.py test

add:
	@echo "Usage: make add SENTENCE='Your French sentence here'"
	poetry run python infrastructure/cli/main.py add "$(SENTENCE)"

batch:
	@echo "Usage: make batch FILE=sentences.txt DECK='Deck Name'"
	poetry run python infrastructure/cli/main.py batch $(FILE) --deck-name "$(DECK)"

clean:
	rm -rf output/*.apkg
	rm -rf cache/*
	rm -rf storage/audio/*

help:
	@echo "French Flashcard Generator"
	@echo ""
	@echo "Commands:"
	@echo "  make install              Install dependencies"
	@echo "  make test                 Test configuration"
	@echo "  make add SENTENCE='...'   Generate single card"
	@echo "  make batch FILE=...       Generate deck from file"
	@echo "  make clean                Clean output files"