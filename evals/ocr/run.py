"""Run one provider on a locked manifest and append resumable local results."""
import argparse
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import select
import subprocess
import time


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apple_prediction(process, path):
    process.stdin.write(os.fsencode(path) + b"\n")
    process.stdin.flush()
    if not select.select([process.stdout], [], [], 90)[0]:
        raise RuntimeError("Apple batch response timed out")
    line = process.stdout.readline()
    if not line:
        raise RuntimeError("Apple batch process exited")
    return json.loads(line)


def google_prediction(provider, path):
    try:
        text = asyncio.run(provider.transcribe(path, "ja"))
        return {"status": "ok" if text.strip() else "empty", "prediction": text}
    except Exception as error:
        return {"status": "provider_error", "prediction": "", "error_class": type(error).__name__,
                "cause_class": type(error.__cause__).__name__ if error.__cause__ else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=["apple", "google"])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("--media-root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--apple-cli", type=Path)
    parser.add_argument("--limit", type=int, help="Stop after this many new pages.")
    options = parser.parse_args()

    cases = records(options.manifest)
    ids = {case["id"] for case in cases}
    if not cases or len(ids) != len(cases):
        parser.error("manifest must have unique case IDs")
    if options.provider == "google" and not all(case["cloud_eligible"] for case in cases):
        parser.error("manifest contains a page without cloud eligibility")
    manifest_hash = digest(options.manifest)
    if options.provider == "apple":
        if not options.apple_cli:
            parser.error("--apple-cli is required for Apple")
        settings = {"level": "accurate", "language": "ja-JP", "language_correction": True,
                    "revision": int(subprocess.check_output([options.apple_cli.resolve(), "--revision"])),
                    "os": platform.mac_ver()[0], "host": platform.machine(),
                    "binary_sha256": digest(options.apple_cli)}
    else:
        from adapters.transcription.google_vision import GoogleVisionTranscriber
        from infrastructure.config.settings import Settings
        settings = {"feature": "DOCUMENT_TEXT_DETECTION", "language_hints": ["ja"],
                    "endpoint": GoogleVisionTranscriber.url, "timeout_seconds": [30, 60]}
        config = Settings(_env_file=options.env_file) if options.env_file else Settings()
        google = GoogleVisionTranscriber(config.google_application_credentials)

    random.Random(20261128).shuffle(cases)
    paths = {case["id"]: (options.media_root / case["media"]).resolve() for case in cases}
    for case in cases:
        if digest(paths[case["id"]]) != case["sha256"]:
            raise ValueError(f"Prepared image hash mismatch for {case['id']}")
    options.results.parent.mkdir(parents=True, exist_ok=True)
    options.results.touch(mode=0o600, exist_ok=True)
    with options.results.open("a+", encoding="utf-8") as output:
        fcntl.flock(output, fcntl.LOCK_EX | fcntl.LOCK_NB)
        output.seek(0)
        done = set()
        for line in output:
            row = json.loads(line)
            if (row["manifest_sha256"] != manifest_hash or row["settings"] != settings
                    or row["provider"] != options.provider or row["id"] not in ids or row["id"] in done):
                raise ValueError("Existing results do not match this manifest and setup")
            done.add(row["id"])
        pending = [case for case in cases if case["id"] not in done]
        if not pending:
            print(f"{len(done)}/{len(cases)} complete")
            return
        if options.limit is not None:
            pending = pending[:options.limit]
        stderr = options.results.with_suffix(".stderr.log")
        with stderr.open("ab") as error_log:
            process = None
            if options.provider == "apple":
                process = subprocess.Popen([options.apple_cli.resolve()], stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=error_log)
            def recognize(path):
                start = time.monotonic()
                result = apple_prediction(process, path) if process else google_prediction(google, path)
                result.setdefault("latency_seconds", time.monotonic() - start)
                return result
            try:
                # A provider-wide failure invalidates this run. Keep its preflight
                # outside the result ledger so it cannot be scored as a page miss.
                first = recognize(paths[pending[0]["id"]])
                preflight_record = dict(first, id=pending[0]["id"], settings=settings)
                preflight = options.results.with_suffix(".preflight.json")
                preflight.write_text(json.dumps(preflight_record, ensure_ascii=False) + "\n")
                if first["status"] != "ok":
                    raise SystemExit(f"Provider preflight did not return text ({first['status']}).")
                for index, case in enumerate(pending):
                    attempts = [first if index == 0 else recognize(paths[case["id"]])]
                    if attempts[-1]["status"] == "provider_error":
                        attempts.append(recognize(paths[case["id"]]))
                    result = dict(attempts[-1], id=case["id"], provider=options.provider,
                                  manifest_sha256=manifest_hash, settings=settings, image_sha256=case["sha256"],
                                  attempt_count=len(attempts),
                                  latency_seconds=sum(row["latency_seconds"] for row in attempts),
                                  attempts=attempts)
                    output.write(json.dumps(result, ensure_ascii=False) + "\n")
                    output.flush()
                    os.fsync(output.fileno())
                    done.add(case["id"])
                    if len(done) % 10 == 0 or index + 1 == len(pending):
                        print(f"{options.provider}: {len(done)}/{len(cases)}", flush=True)
            finally:
                if process:
                    process.stdin.close()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


if __name__ == "__main__":
    main()
