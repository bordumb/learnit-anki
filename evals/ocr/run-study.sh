#!/usr/bin/env bash
# Run the frozen cohorts in a normal macOS Terminal.
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo"
study="${1:?usage: run-study.sh <study-directory> [python]}"
python="${2:-.venv/bin/python}"
study="$(cd "$study" && pwd)"
lock="$study/cohort-lock.json"
logs="$study/terminal-runs"
mkdir -p "$logs"
smoke_default="$study/prepared-smoke.jsonl"
if [[ -f "$study/smoke.jsonl" ]]; then
  smoke_default="$study/smoke.jsonl"
fi

run_cohort() {
  local provider="$1" split="$2" smoke="$3"
  local args=()
  if [[ "$provider" == apple ]]; then
    args=(--apple-cli "$study/apple-ocr")
  fi
  local checks=0
  until "$python" -c '
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
if not path.is_file():
    sys.exit(1)
cohort = json.loads(path.read_text())["splits"][sys.argv[2]]
sys.exit(not cohort["review_complete"])
' "$lock" "$split"; do
    if (( ++checks > 180 )); then
      echo "$provider/$split: reference review did not finish within 90 minutes"
      return 75
    fi
    sleep 30
  done
  "$python" -m evals.ocr.run "$provider" "$study/$split.jsonl" "$logs/$provider-$split.jsonl" \
    --media-root "$study" --smoke-manifest "$smoke" --lock "$lock" "${args[@]}"
}

run_google() {
  run_cohort google pilot "$smoke_default" &&
    run_cohort google heldout "$smoke_default"
}
run_apple() {
  local smoke
  for smoke in "$study"/apple-diagnostic-*.jsonl "$smoke_default"; do
    [[ -f "$smoke" ]] || continue
    if "$python" -m evals.ocr.run apple "$smoke" "$logs/apple-$(basename "$smoke")" \
      --media-root "$study" --apple-cli "$study/apple-ocr" --limit 1; then
      run_cohort apple pilot "$smoke" && run_cohort apple heldout "$smoke"
      return $?
    fi
  done
  echo 'Apple Vision did not return text on the preflight pages.'
  return 69
}

echo 'Waiting for the reviewed study manifests. Results will be saved after each page.'
run_google &
google_pid=$!
run_apple &
apple_pid=$!
status=0
wait "$apple_pid" || status=$?
wait "$google_pid" || status=$?
exit "$status"
