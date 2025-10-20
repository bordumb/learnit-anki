#!/usr/bin/env bash
set -euo pipefail

OUTPUT_FILE="all_code.txt"
rm -f "$OUTPUT_FILE"

echo "Collecting text files..."

# Find all files except known junk / binary dirs and Xcode project files
find . \
  -type f \
  ! -path "./.git/*" \
  ! -path "./node_modules/*" \
  ! -path "./.idea/*" \
  ! -path "./.vscode/*" \
  ! -path "./build/*" \
  ! -path "./dist/*" \
  ! -path "./target/*" \
  ! -path "./venv/*" \
  ! -path "./.venv/*" \
  ! -path "./__pycache__/*" \
  ! -path "./DerivedData/*" \
  ! -path "*/.DS_Store" \
  ! -path "*/xcuserdata/*" \
  ! -path "*/xcshareddata/*" \
  ! -path "*/.swiftpm/*" \
  ! -path "*/Package.resolved" \
  ! -path "*/learnit.xcodeproj*" \
  ! -path "*/.xcodeproj/*" \
  ! -path "*/.xcworkspace/*" \
  ! -path "./$OUTPUT_FILE" \
  ! -name "*.sh" \
  ! -name "poetry.lock" \
  ! -name ".env" \
  | sort \
  | while read -r file; do
      # Only include readable text/code files
      if file "$file" | grep -qE 'text|JSON|XML|script|source'; then
        echo "----- FILE: $file -----" >> "$OUTPUT_FILE"
        cat "$file" >> "$OUTPUT_FILE"
        echo -e "\n\n" >> "$OUTPUT_FILE"
      fi
    done

echo "✅ Finished! Plain text concatenated into $OUTPUT_FILE"