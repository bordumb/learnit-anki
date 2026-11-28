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
import re
import select
import subprocess
import time


def records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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
        causes = []
        cause = error
        while cause is not None:
            causes.append(type(cause).__name__)
            cause = cause.__cause__
        response = getattr(error, "response", None)
        match = re.match(r"Google Cloud Vision \((\d{3})\b", str(error))
        http_status = response.status_code if response is not None else (int(match[1]) if match else None)
        timeout = any(item in {"Timeout", "ReadTimeout", "ConnectTimeout"} for item in causes)
        environment = bool(set(causes) & {"TransportError", "ConnectionError", "RefreshError",
                                          "DefaultCredentialsError", "FileNotFoundError"})
        return {"status": "provider_error", "prediction": "", "error_class": type(error).__name__,
                "cause_class": causes[1] if len(causes) > 1 else None, "http_status": http_status,
                "timeout": timeout, "retryable": timeout or http_status in {429, 500, 502, 503, 504},
                "environment_error": (environment and not timeout) or http_status in {401, 403}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=["apple", "google"])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("--media-root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--apple-cli", type=Path)
    parser.add_argument("--limit", type=int, help="Stop after this many new pages.")
    parser.add_argument("--smoke-manifest", type=Path, help="One known page outside the scored cohort")
    parser.add_argument("--lock", type=Path, help="Reviewed cohort metadata from freeze.py")
    options = parser.parse_args()

    cases = records(options.manifest)
    ids = {case["id"] for case in cases}
    if not cases or len(ids) != len(cases):
        parser.error("manifest must have unique case IDs")
    if options.limit is not None and options.limit < 1:
        parser.error("--limit must be positive")
    if options.provider == "google" and not all(case["cloud_eligible"] for case in cases):
        parser.error("manifest contains a page without cloud eligibility")
    manifest_hash = digest(options.manifest)
    if any("split" in case for case in cases):
        if not options.lock or not options.smoke_manifest:
            parser.error("study cohorts require --lock and a separate --smoke-manifest")
        cohort = cases[0]["split"]
        lock = json.loads(options.lock.read_text(encoding="utf-8"))
        locked = lock["splits"].get(cohort, {})
        if (not locked.get("review_complete") or locked["manifest_sha256"] != manifest_hash
                or cohort not in {"pilot", "heldout"}):
            parser.error("cohort must match a reviewed pilot or heldout lock")
    smoke = records(options.smoke_manifest) if options.smoke_manifest else []
    if options.smoke_manifest and (len(smoke) != 1 or smoke[0]["id"] in ids):
        parser.error("--smoke-manifest must contain one independent case")
    if options.provider == "google" and smoke and not smoke[0]["cloud_eligible"]:
        parser.error("preflight case must be cloud eligible for Google")
    if options.provider == "apple":
        if not options.apple_cli:
            parser.error("--apple-cli is required for Apple")
        settings = {"level": "accurate", "language": "ja-JP", "language_correction": True,
                    "revision": int(subprocess.check_output([options.apple_cli.resolve(), "--revision"])),
                    "os": platform.mac_ver()[0], "host": platform.machine(),
                    "os_build": subprocess.check_output(["sw_vers", "-buildVersion"], text=True).strip(),
                    "binary_sha256": digest(options.apple_cli)}
    else:
        from adapters.transcription.google_vision import GoogleVisionTranscriber
        from infrastructure.config.settings import Settings
        settings = {"feature": "DOCUMENT_TEXT_DETECTION", "language_hints": ["ja"],
                    "endpoint": GoogleVisionTranscriber.url, "timeout_seconds": [30, 60],
                    "adapter_sha256": digest(Path(__file__).resolve().parents[2] /
                                             "adapters/transcription/google_vision.py")}
        config = Settings(_env_file=options.env_file) if options.env_file else Settings()
        google = GoogleVisionTranscriber(config.google_application_credentials)

    random.Random(20261128).shuffle(cases)
    media_root = options.media_root.resolve()
    paths = {case["id"]: (media_root / case["media"]).resolve() for case in cases + smoke}
    for case in cases + smoke:
        if not paths[case["id"]].is_relative_to(media_root):
            raise ValueError(f"Image outside media root for {case['id']}")
        if digest(paths[case["id"]]) != case["sha256"]:
            raise ValueError(f"Prepared image hash mismatch for {case['id']}")
    options.results.parent.mkdir(parents=True, exist_ok=True)
    options.results.touch(mode=0o600, exist_ok=True)
    with options.results.open("a+b") as output:
        fcntl.flock(output, fcntl.LOCK_EX | fcntl.LOCK_NB)
        output.seek(0)
        done = set()
        while line := output.readline():
            if not line.endswith(b"\n"):
                # A killed writer can leave an incomplete final record.
                output.truncate(output.tell() - len(line))
                break
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
                result["latency_seconds"] = time.monotonic() - start
                return result
            try:
                # A provider-wide failure invalidates this run. Keep its preflight
                # outside the result ledger so it cannot be scored as a page miss.
                first_case = smoke[0] if smoke else pending[0]
                first = recognize(paths[first_case["id"]])
                preflight_record = dict(first, id=first_case["id"], settings=settings)
                preflight = options.results.with_suffix(".preflight.json")
                preflight.write_text(json.dumps(preflight_record, ensure_ascii=False) + "\n")
                if first["status"] != "ok":
                    raise SystemExit(f"Provider preflight did not return text ({first['status']}).")
                for index, case in enumerate(pending):
                    attempts = [first if not smoke and index == 0 else recognize(paths[case["id"]])]
                    if attempts[-1].get("retryable"):
                        attempts.append(recognize(paths[case["id"]]))
                    if attempts[-1].get("environment_error"):
                        raise SystemExit(f"Provider environment failed at {case['id']}; resume after recovery.")
                    result = dict(attempts[-1], id=case["id"], provider=options.provider,
                                  manifest_sha256=manifest_hash, settings=settings, image_sha256=case["sha256"],
                                  attempt_count=len(attempts),
                                  latency_seconds=sum(row["latency_seconds"] for row in attempts),
                                  first_in_session=not smoke and index == 0,
                                  attempts=attempts)
                    output.write((json.dumps(result, ensure_ascii=False) + "\n").encode("utf-8"))
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
