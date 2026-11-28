#!/usr/bin/env bash
# Publish only after Pandoc and both XeLaTeX passes succeed.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
mkdir -p build/local/attempts
attempt="$(mktemp -d build/local/attempts/main.XXXXXXXX)"
trap 'status=$?; if (( status != 0 )); then echo "Build logs: $PWD/$attempt" >&2; fi' EXIT

pandoc manuscript/main.md --standalone \
  --from markdown+raw_tex+tex_math_single_backslash --to latex \
  --include-in-header=preamble.tex --citeproc --fail-if-warnings \
  --bibliography=bib/references.bib --number-sections \
  -V documentclass:article -V papersize:a4 -V fontsize=11pt \
  -V geometry:top=25mm,bottom=25mm,left=27mm,right=27mm \
  -V colorlinks=true -V linkcolor=inkblue -V citecolor=inkblue -V urlcolor=inkblue \
  --output="$attempt/main.tex"

for pass in 1 2; do
  xelatex -interaction=nonstopmode -halt-on-error -file-line-error \
    -output-directory="$attempt" "$attempt/main.tex" >"$attempt/pass$pass.log" 2>&1 || {
      tail -60 "$attempt/pass$pass.log" >&2
      exit 1
    }
done
if grep -Eq 'Missing character|Overfull \\[hv]box|Undefined control sequence|undefined references' "$attempt/main.log"; then
  grep -En 'Missing character|Overfull \\[hv]box|Undefined control sequence|undefined references' "$attempt/main.log" >&2
  exit 1
fi
[[ -s "$attempt/main.pdf" ]]
mv "$attempt/main.pdf" japanese-handwriting-ocr.pdf
printf '%s/japanese-handwriting-ocr.pdf\n' "$PWD"
