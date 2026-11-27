"""Evaluate the same image and audio transcription ports used by the application."""

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from time import perf_counter
import unicodedata


GOLDEN = Path(__file__).resolve().parents[1] / "data" / "golden" / "ja"
OUTPUT = Path(__file__).resolve().parents[1] / "output" / "transcription-evals"


@dataclass(frozen=True)
class Case:
    id: str
    kind: str
    category: str
    media: Path
    reference: str
    language: str
    group: str


def load_cases(manifests: list[Path]) -> list[Case]:
    cases = []
    ids = set()
    for manifest in manifests:
        folder = manifest.parent.resolve()
        for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                kind = row.get("kind") or row.get("modality") or (
                    "image" if folder.name == "handwriting" else folder.name
                )
                media = (folder / row["media"]).resolve()
                if kind not in {"image", "audio"} or not media.is_relative_to(folder) or not media.is_file():
                    raise ValueError("expected an image or audio file inside the manifest directory")
                if row["id"] in ids:
                    raise ValueError(f'duplicate ID {row["id"]}')
                for field in ("id", "reference", "language", "group", "source_url", "license"):
                    if not isinstance(row[field], str) or not row[field].strip():
                        raise ValueError(f"{field} must be a non-empty string")
                cases.append(Case(
                    id=row["id"], kind=kind, category=row.get("category", kind),
                    media=media, reference=row["reference"],
                    language=row["language"], group=row["group"],
                ))
                ids.add(row["id"])
            except (TypeError, ValueError, KeyError) as error:
                raise ValueError(f"{manifest}:{number}: {error}") from error
    if not cases:
        raise ValueError("No applicable golden cases found.")
    return cases


def normalize(text: str) -> str:
    # Canonically equivalent Unicode and layout whitespace are interchangeable.
    # Preserve punctuation, kana, kanji, and orthographic differences.
    return "".join(unicodedata.normalize("NFC", text).split())


def edit_distance(reference: str, prediction: str) -> int:
    previous = list(range(len(prediction) + 1))
    for i, expected in enumerate(reference, 1):
        current = [i]
        for j, actual in enumerate(prediction, 1):
            current.append(min(current[j - 1] + 1, previous[j] + 1,
                               previous[j - 1] + (expected != actual)))
        previous = current
    return previous[-1]


def score(case: Case, prediction: str, seconds: float | None) -> dict:
    reference = normalize(case.reference)
    candidate = normalize(prediction)
    return {
        "id": case.id, "kind": case.kind, "category": case.category, "group": case.group,
        "reference": case.reference, "prediction": prediction,
        "character_edits": edit_distance(reference, candidate),
        "reference_characters": len(reference), "exact_match": reference == candidate,
        "latency_seconds": seconds,
    }


def summarize(rows: list[dict]) -> dict:
    scored = [row for row in rows if "error" not in row]
    times = [row["latency_seconds"] for row in scored if row["latency_seconds"] is not None]
    chars = sum(row["reference_characters"] for row in scored)
    return {
        "cases": len(rows),
        "scored": len(scored),
        "errors": len(rows) - len(scored),
        "exact_match_rate": sum(row["exact_match"] for row in scored) / len(scored) if scored else None,
        "character_error_rate": sum(row["character_edits"] for row in scored) / chars if chars else None,
        "median_latency_seconds": median(times) if times else None,
    }


async def run_live(cases: list[Case], env_file: Path | None = None) -> list[dict]:
    from infrastructure.config.dependency_injection import ServiceContainer
    from infrastructure.config.settings import Settings

    settings = Settings(_env_file=env_file) if env_file is not None else Settings()
    container = ServiceContainer(settings)
    factories = {"image": container.create_image_transcriber, "audio": container.create_audio_transcriber}
    transcribers = {kind: factories[kind]() for kind in dict.fromkeys(case.kind for case in cases)}
    rows = []
    for case in cases:
        start = perf_counter()
        try:
            draft = await transcribers[case.kind].execute(case.media, case.language)
            rows.append(score(case, draft.text, perf_counter() - start))
        except Exception as error:
            rows.append({"id": case.id, "kind": case.kind, "category": case.category,
                         "group": case.group, "error": str(error)})
    return rows


def score_predictions(cases: list[Case], path: Path) -> list[dict]:
    predictions = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row["id"] in predictions:
                raise ValueError(f'Duplicate prediction ID {row["id"]}')
            predictions[row["id"]] = row
    if set(predictions) != {case.id for case in cases}:
        raise ValueError("Prediction IDs must match the selected golden cases exactly.")
    return [score(case, predictions[case.id]["prediction"], predictions[case.id].get("latency_seconds"))
            for case in cases]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, action="append", help="JSONL manifest. Can be repeated.")
    parser.add_argument("--kind", choices=["image", "audio"], help="Evaluate a single modality.")
    parser.add_argument("--validate-only", action="store_true", help="Check the golden manifest and files offline.")
    parser.add_argument("--predictions", type=Path, help="Score saved JSONL predictions without invoking providers.")
    parser.add_argument("--env-file", type=Path, help="Load provider settings from this env file for a live run.")
    parser.add_argument("--output", type=Path, help="Write run details, provenance and scores here.")
    args = parser.parse_args()
    manifests = args.manifest or sorted(GOLDEN.glob("*/cases.jsonl"))
    try:
        cases = load_cases(manifests)
        if args.kind:
            cases = [case for case in cases if case.kind == args.kind]
        if not cases:
            raise ValueError("No golden cases match the requested modality.")
        if args.validate_only:
            print(json.dumps({"validated": len(cases), "by_kind": {
                kind: sum(case.kind == kind for case in cases)
                for kind in sorted({case.kind for case in cases})
            }}, ensure_ascii=False))
            return 0
        rows = (
            score_predictions(cases, args.predictions) if args.predictions
            else asyncio.run(run_live(cases, args.env_file))
        )
    except (OSError, TypeError, ValueError, KeyError) as error:
        parser.exit(2, f"{error}\n")

    by_category = {}
    for kind, category in sorted({(row["kind"], row["category"]) for row in rows}):
        by_category[f"{kind}/{category}"] = summarize([
            row for row in rows if (row["kind"], row["category"]) == (kind, category)
        ])
    report = {
        "mode": "saved-predictions" if args.predictions else "live",
        "manifests": [str(path) for path in manifests],
        "summary": summarize(rows),
        "by_kind": {kind: summarize([row for row in rows if row["kind"] == kind])
                    for kind in sorted({row["kind"] for row in rows})},
        "by_category": by_category,
        "cases": rows,
    }
    target = args.output or OUTPUT / "results.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(target), "summary": report["summary"]}, ensure_ascii=False))
    return int(any("error" in row for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
