#!/usr/bin/env bash
set -euo pipefail

ROOT="learnit-anki"

# --- Directories ---
dirs=(
  "$ROOT/core/domain"
  "$ROOT/core/use_cases"
  "$ROOT/adapters/translation"
  "$ROOT/adapters/audio"
  "$ROOT/adapters/dictionary"
  "$ROOT/adapters/storage"
  "$ROOT/adapters/anki"
  "$ROOT/infrastructure/cli"
  "$ROOT/infrastructure/api/routes"
  "$ROOT/infrastructure/config"
  "$ROOT/infrastructure/monitoring"
  "$ROOT/tests/unit"
  "$ROOT/tests/integration"
  "$ROOT/tests/e2e"
  "$ROOT/docker"
)

echo "📁 Creating directory structure..."
for d in "${dirs[@]}"; do
  mkdir -p "$d"
done

# --- Empty files ---
files=(
  "$ROOT/core/domain/models.py"
  "$ROOT/core/domain/interfaces.py"
  "$ROOT/core/domain/services.py"
  "$ROOT/core/use_cases/generate_card.py"
  "$ROOT/core/use_cases/generate_deck.py"
  "$ROOT/core/use_cases/search_sentences.py"

  "$ROOT/adapters/translation/deepl_adapter.py"
  "$ROOT/adapters/translation/openai_adapter.py"
  "$ROOT/adapters/translation/mock_adapter.py"

  "$ROOT/adapters/audio/google_tts_adapter.py"
  "$ROOT/adapters/audio/elevenlabs_adapter.py"
  "$ROOT/adapters/audio/cached_audio_adapter.py"

  "$ROOT/adapters/dictionary/wordreference_adapter.py"
  "$ROOT/adapters/dictionary/openai_dictionary_adapter.py"
  "$ROOT/adapters/dictionary/cached_dictionary_adapter.py"

  "$ROOT/adapters/storage/local_file_storage.py"
  "$ROOT/adapters/storage/s3_storage.py"

  "$ROOT/adapters/anki/genanki_exporter.py"

  "$ROOT/infrastructure/cli/main.py"
  "$ROOT/infrastructure/cli/commands.py"

  "$ROOT/infrastructure/api/main.py"
  "$ROOT/infrastructure/config/settings.py"
  "$ROOT/infrastructure/config/dependency_injection.py"
  "$ROOT/infrastructure/monitoring/logger.py"
  "$ROOT/infrastructure/monitoring/metrics.py"

  "$ROOT/docker/Dockerfile.local"
  "$ROOT/docker/Dockerfile.prod"

  "$ROOT/.env.example"
  "$ROOT/pyproject.toml"
  "$ROOT/README.md"
  "$ROOT/Makefile"
)

echo "📝 Creating empty files..."
for f in "${files[@]}"; do
  touch "$f"
done

echo "✅ Project scaffold created at: $ROOT"
