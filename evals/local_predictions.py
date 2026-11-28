"""Generate scoreable predictions with offline Whisper or Tesseract."""

import argparse
import json
from hashlib import file_digest
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter

from evals.transcription import Case, GOLDEN, SUITES, load_cases


def whisper_prediction(case: Case, binary: str, model: Path, folder: Path) -> str:
    audio = folder / "input.wav"
    prefix = folder / "prediction"
    prefix.with_suffix(".txt").unlink(missing_ok=True)
    subprocess.run([
        "ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(case.media),
        "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio),
    ], check=True, capture_output=True, text=True)
    subprocess.run([
        binary, "--no-gpu", "--threads", "4", "--language", case.language, "--model", str(model),
        "--no-timestamps", "--output-txt", "--output-file", str(prefix), str(audio),
    ], check=True, capture_output=True, text=True)
    return prefix.with_suffix(".txt").read_text(encoding="utf-8")


def tesseract_prediction(case: Case, tessdata: Path) -> str:
    vertical = case.writing_direction == "vertical_right_to_left"
    return subprocess.run([
        "tesseract", str(case.media), "stdout", "--tessdata-dir", str(tessdata),
        "-l", "jpn_vert" if vertical else "jpn", "--oem", "1", "--psm", "5" if vertical else "6",
    ], check=True, capture_output=True, text=True).stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", choices=("whisper", "tesseract"))
    parser.add_argument("--suite", choices=SUITES, default="passages")
    parser.add_argument("--manifest", type=Path, action="append", help="Override the built-in manifests.")
    parser.add_argument("--whisper-cli", default="whisper-cli")
    parser.add_argument("--whisper-model", type=Path)
    parser.add_argument("--tessdata", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    use_whisper = args.engine == "whisper"
    if use_whisper and (args.whisper_model is None or not args.whisper_model.is_file()):
        parser.error("Whisper requires --whisper-model with a local GGML model file.")
    if not use_whisper and (args.tessdata is None or not args.tessdata.is_dir()):
        parser.error("Tesseract requires --tessdata with the Japanese language data directory.")

    kind = "audio" if use_whisper else "image"
    try:
        cases = [case for case in load_cases(args.manifest or sorted(GOLDEN.glob("*/cases.jsonl")))
                 if case.kind == kind and case.suite == args.suite]
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    if not cases:
        parser.error("No golden cases match the selected engine and suite.")

    if use_whisper:
        with args.whisper_model.open("rb") as model_file:
            checksum = file_digest(model_file, "sha256").hexdigest()
        model = {"engine": "whisper.cpp", "file": args.whisper_model.name,
                 "sha256": checksum, "threads": 4, "gpu": False}
    else:
        languages = {"jpn_vert" if case.writing_direction == "vertical_right_to_left" else "jpn"
                     for case in cases}
        checksums = {}
        for language in sorted(languages):
            data_file = args.tessdata / f"{language}.traineddata"
            if not data_file.is_file():
                parser.error(f"Missing Tesseract language data: {data_file}")
            with data_file.open("rb") as data:
                checksums[language] = file_digest(data, "sha256").hexdigest()
        model = {"engine": "tesseract", "traineddata_sha256": checksums}

    predictions = []
    with TemporaryDirectory() as directory:
        for case in cases:
            start = perf_counter()
            try:
                prediction = (whisper_prediction(case, args.whisper_cli, args.whisper_model, Path(directory))
                              if use_whisper else tesseract_prediction(case, args.tessdata))
            except subprocess.CalledProcessError as error:
                parser.exit(1, f"{case.id}: {error.stderr.strip()}\n")
            except OSError as error:
                parser.exit(1, f"{case.id}: {error}\n")
            predictions.append({
                "id": case.id, "model": model, "prediction": prediction.strip(), "latency_seconds": perf_counter() - start,
            })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        output.writelines(json.dumps(row, ensure_ascii=False) + "\n" for row in predictions)
    print(f"Wrote {len(predictions)} predictions to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
