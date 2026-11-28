"""Score a complete provider ledger against a fixed JaWildText manifest."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
from random import Random

from rapidfuzz.distance import Levenshtein

from evals.ocr.prepare import SEED
from evals.ocr.run import records
from evals.transcription import normalize

DRAWS = 10_000


def load_ledger(provider, path, cases, manifest_hash):
    predictions = {}
    settings = None
    for row in records(path):
        case_id = row["id"]
        if (row["provider"] != provider or row["manifest_sha256"] != manifest_hash
                or case_id not in cases or case_id in predictions
                or row["image_sha256"] != cases[case_id]["sha256"]
                or row["status"] not in {"ok", "empty", "provider_error"}):
            raise ValueError(f"Invalid {provider} ledger row: {case_id}")
        if settings is not None and settings != row["settings"]:
            raise ValueError(f"Inconsistent {provider} settings")
        settings = row["settings"]
        predictions[case_id] = row
    if predictions.keys() != cases.keys():
        raise ValueError(f"Incomplete {provider} ledger: {len(predictions)}/{len(cases)}")
    return predictions, settings


def percentile(values, probability):
    values = sorted(values)
    if not values:
        return None
    index = (len(values) - 1) * probability
    base = int(index)
    return values[base] + (index - base) * (values[min(base + 1, len(values) - 1)] - values[base])


def score_page(case, result):
    reference = normalize(case["reference"])
    prediction = normalize(result["prediction"]) if result["status"] == "ok" else ""
    if not reference:
        raise ValueError(f"Empty reference: {case['id']}")
    if result["status"] == "ok" and not prediction:
        raise ValueError(f"Non-text result marked successful: {case['id']}")
    edits = Levenshtein.distance(reference, prediction)
    return {
        "id": case["id"], "chars": len(reference), "edits": edits,
        "major": result["status"] != "ok" or edits >= len(reference),
        "exact": edits == 0, "status": result["status"],
        "latency": result["latency_seconds"], "attempt_count": result["attempt_count"],
        "first_in_session": result["first_in_session"],
        "attempt_timeouts": sum(attempt.get("timeout", False) for attempt in result["attempts"]),
    }


def summarize(cases, scores):
    output = {
        "pages": len(cases),
        "writers": len({case["writer_id"] for case in cases}),
        "groups": len({case["group"] for case in cases}),
        "reference_characters": sum(row["chars"] for row in scores),
    }
    if not cases:
        return output
    by_writer = defaultdict(Counter)
    for case, row in zip(cases, scores, strict=True):
        by_writer[case["writer_id"]].update(chars=row["chars"], edits=row["edits"])
    status = Counter(row["status"] for row in scores)
    warm = [row["latency"] for row in scores if not row["first_in_session"]]
    output.update({
        "edits": sum(row["edits"] for row in scores),
        "micro_cer": sum(row["edits"] for row in scores) / output["reference_characters"],
        "writer_macro_cer": sum(t["edits"] / t["chars"] for t in by_writer.values()) / len(by_writer),
        "exact": sum(row["exact"] for row in scores),
        "major": sum(row["major"] for row in scores),
        "ok": status["ok"], "empty": status["empty"], "provider_error": status["provider_error"],
        "attempts": sum(row["attempt_count"] for row in scores),
        "attempt_timeouts": sum(row["attempt_timeouts"] for row in scores),
        "page_cer_p50": percentile([row["edits"] / row["chars"] for row in scores], 0.5),
        "page_cer_p90": percentile([row["edits"] / row["chars"] for row in scores], 0.9),
        "latency_p50_seconds": percentile([row["latency"] for row in scores], 0.5),
        "latency_p95_seconds": percentile([row["latency"] for row in scores], 0.95),
        "warm_pages": len(warm),
        "warm_p50_seconds": percentile(warm, 0.5),
        "warm_p95_seconds": percentile(warm, 0.95),
    })
    return output


def paired(cases, apple, google):
    grouped = defaultdict(Counter)
    for case, left, right in zip(cases, apple, google, strict=True):
        grouped[case["group"]].update({
            "chars": left["chars"], "pages": 1, "edits": right["edits"] - left["edits"],
            "major": int(right["major"]) - int(left["major"]),
        })

    def effect(groups):
        return (
            sum(row["edits"] for row in groups) / sum(row["chars"] for row in groups),
            sum(row["major"] for row in groups) / sum(row["pages"] for row in groups),
        )

    groups = [grouped[key] for key in sorted(grouped)]
    rng = Random(SEED)
    cer, major = effect(groups)
    samples = [effect(rng.choices(groups, k=len(groups))) for _ in range(DRAWS)] if len(groups) > 1 else []
    intervals = [
        [percentile(values, 0.025), percentile(values, 0.975)]
        for values in zip(*samples)
    ] if samples else [None, None]
    successful_cases, successful_apple, successful_google = [], [], []
    for case, left, right in zip(cases, apple, google, strict=True):
        if left["status"] == right["status"] == "ok":
            successful_cases.append(case)
            successful_apple.append(left)
            successful_google.append(right)
    return {
        "pages": len(cases), "groups": len(groups), "bootstrap_draws": len(samples),
        "google_minus_apple_cer": cer, "cer_ci95": intervals[0],
        "google_minus_apple_major_failure_rate": major, "major_failure_rate_ci95": intervals[1],
        "both_successful": {
            "apple": summarize(successful_cases, successful_apple),
            "google": summarize(successful_cases, successful_google),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("summary", type=Path)
    parser.add_argument("--apple", type=Path)
    parser.add_argument("--google", type=Path)
    parser.add_argument("--page-scores", type=Path, help="Optional local metrics for error analysis")
    options = parser.parse_args()
    ledger_paths = {key: path for key, path in (("apple", options.apple), ("google", options.google)) if path}
    if not ledger_paths:
        parser.error("Provide at least one complete ledger")
    cases = records(options.manifest)
    indexed = {case["id"]: case for case in cases}
    if not cases or len(indexed) != len(cases):
        parser.error("Expected a nonempty manifest with unique IDs")
    lock_hash = sha256(options.manifest.read_bytes()).hexdigest()
    data = {"manifest_sha256": lock_hash, "providers": {}, "comparison": None}
    scores = {}
    for provider, path in ledger_paths.items():
        ledger, settings = load_ledger(provider, path, indexed, lock_hash)
        scores[provider] = [score_page(case, ledger[case["id"]]) for case in cases]
        summary = {
            "settings": settings, "overall": summarize(cases, scores[provider]),
            "without_incomplete_glyph": summarize(
                [case for case in cases if not case["reference_has_incomplete_glyph"]],
                [row for case, row in zip(cases, scores[provider], strict=True)
                 if not case["reference_has_incomplete_glyph"]],
            ),
        }
        for field in ("writing_direction", "medium", "layout", "length"):
            groups = defaultdict(list)
            for case, row in zip(cases, scores[provider], strict=True):
                if field == "layout":
                    bucket = "mixed" if "mixed_geometry" in case["flags"] else case["writing_direction"]
                elif field == "length":
                    bucket = "1–100" if row["chars"] <= 100 else "101–250" if row["chars"] <= 250 else "251+"
                else:
                    bucket = case[field]
                groups[bucket].append((case, row))
            summary[f"by_{field}"] = {
                key: summarize(*zip(*values)) for key, values in sorted(groups.items())
            }
        data["providers"][provider] = summary
    if scores.keys() == {"apple", "google"}:
        data["comparison"] = paired(cases, scores["apple"], scores["google"])
        for field in ("writing_direction", "medium"):
            strata = defaultdict(list)
            for case, left, right in zip(cases, scores["apple"], scores["google"], strict=True):
                strata[case[field]].append((case, left, right))
            data["comparison"][f"by_{field}"] = {
                key: paired(*zip(*values)) for key, values in sorted(strata.items())
            }
    options.summary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if options.page_scores:
        options.page_scores.write_text(json.dumps(scores, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
