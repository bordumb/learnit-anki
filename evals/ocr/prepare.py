"""Prepare writer-separated JaWildText cases from the pinned Parquet shards."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from io import BytesIO
import json
from pathlib import Path
import random

from PIL import Image, ImageOps
import pyarrow.parquet as pq

from evals.transcription import normalize as compact

REVISION = "627ca7ea7c224ffe1accff8737991fc2240784fa"
SEED = 20261128
KNOWN_WRITERS = {2, 3, 4, 7, 28, 35, 46}
SOURCE = f"https://huggingface.co/datasets/llm-jp/jawildtext/tree/{REVISION}"
STRATA = ("horizontal", "vertical")
MAX_EDGE = 2200


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    tmp = path.with_suffix(path.suffix + ".part")
    with tmp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(path)


def geometry(record: dict) -> tuple[list[dict], str, list[str]]:
    lines = []
    flags = []
    for row in record["polygons"]:
        if not row["polygon"] or not row["text"]:
            continue
        x, y = zip(*row["polygon"])
        width, height = max(x) - min(x), max(y) - min(y)
        lines.append({
            "x": sum(x) / len(x), "y": sum(y) / len(y),
            "vertical": height > width, "polygon": row["polygon"],
            "polygon_id": row["polygon_id"], "text": row["text"],
            "source_direction": row["direction"],
        })
    vertical_count = sum(line["vertical"] for line in lines)
    vertical = vertical_count > len(lines) / 2
    if 0 < vertical_count < len(lines):
        flags.append("mixed_geometry")
    direction = "vertical" if vertical else "horizontal"
    if any(line["source_direction"] in STRATA and
           line["source_direction"] != ("vertical" if line["vertical"] else "horizontal")
           for line in lines):
        flags.append("source_direction_mismatch")
    if vertical:
        lines.sort(key=lambda line: (-line["x"], line["y"]))
    else:
        lines.sort(key=lambda line: (line["y"], line["x"]))
    return lines, direction, flags


def pitch_hash(image: Image.Image) -> int:
    pixels = list(image.convert("L").resize((9, 8), Image.Resampling.LANCZOS).get_flattened_data())
    return sum(
        (pixels[y * 9 + x] > pixels[y * 9 + x + 1]) << (y * 8 + x)
        for y in range(8) for x in range(8)
    )


def read_candidates(shards: Path, root: Path) -> tuple[list[dict], list[dict]]:
    candidates, exclusions = [], []
    seen_ids = set()
    seen_bytes = set()
    seen_pixels = set()
    media = root / "media"
    media.mkdir(exist_ok=True)
    tree = json.loads((shards / "tree.json").read_text())
    for entry in tree:
        if not entry["path"].endswith(".parquet"):
            continue
        path = shards / Path(entry["path"]).name
        with path.open("rb") as handle:
            actual = hashlib.file_digest(handle, "sha256").hexdigest()
        if actual != entry["lfs"]["oid"]:
            raise ValueError(f"unexpected Parquet digest: {path.name}")
        for batch in pq.ParquetFile(path).iter_batches(
            batch_size=8, columns=["image_id", "filename", "writer_id", "tool", "polygons", "image"],
        ):
            for record in batch.to_pylist():
                source_id = record["image_id"]
                filename = record["filename"]
                case_id = f"jawildtext-{Path(filename).stem}"
                if case_id in seen_ids:
                    raise ValueError(f"duplicate filename-derived case ID {case_id}")
                seen_ids.add(case_id)
                writer = record["writer_id"]
                lines, direction, flags = geometry(record)
                reference = "\n".join(line["text"] for line in lines)
                if writer is None or writer < 0 or not compact(reference):
                    exclusions.append({"id": case_id, "reason": "missing_writer_or_reference"})
                    continue
                raw = record["image"]["bytes"]
                raw_hash = digest(raw)
                with Image.open(BytesIO(raw)) as source:
                    original_size = source.size
                    orientation = source.getexif().get(274, 1)
                    image = ImageOps.exif_transpose(source).convert("RGB")
                    pixel_hash = digest(f"{image.size}:".encode() + image.tobytes())
                if raw_hash in seen_bytes or pixel_hash in seen_pixels:
                    exclusions.append({"id": case_id, "reason": "exact_image_duplicate"})
                    continue
                seen_bytes.add(raw_hash)
                seen_pixels.add(pixel_hash)
                if orientation not in (None, 1):
                    flags.append("exif_rotation")
                perceptual = pitch_hash(image)
                image.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
                encoded = BytesIO()
                image.save(encoded, format="JPEG", quality=92)
                data = encoded.getvalue()
                image_path = media / f"{case_id}.jpg"
                image_path.write_bytes(data)
                candidates.append({
                    "id": case_id, "kind": "image", "language": "ja", "suite": "passages",
                    "category": "handwriting", "media": str(image_path.relative_to(root)),
                    "source_image_id": source_id, "source_filename": filename,
                    "source_url": SOURCE, "source_revision": REVISION, "license": "Apache-2.0",
                    "writer_id": writer, "reference": reference, "writing_direction": direction,
                    "medium": {"whilte_bord": "whiteboard"}.get(record["tool"], record["tool"]) or "unknown",
                    "sha256": digest(data),
                    "original_sha256": raw_hash, "original_size": original_size,
                    "prepared_size": image.size, "original_pixel_sha256": pixel_hash,
                    "perceptual_hash": f"{perceptual:016x}", "line_count": len(lines),
                    "reference_has_incomplete_glyph": "□" in reference,
                    "cloud_eligible": True, "flags": flags, "lines": lines,
                })
    if len(seen_ids) != 1065:
        raise ValueError(f"expected 1065 pinned images, got {len(seen_ids)}")
    return candidates, exclusions


def split_cases(candidates: list[dict], exclusions: list[dict]) -> list[dict]:
    # Near-duplicate pixels alone can match two different, similarly framed sheets.
    # Link groups on exact substantial text or jointly close pixels and text.
    from rapidfuzz.distance import Levenshtein

    writers = {case["writer_id"] for case in candidates}
    parents = {writer: writer for writer in writers}

    def group(writer: int) -> int:
        while parents[writer] != writer:
            writer = parents[writer]
        return writer

    similar = []
    texts = {case["id"]: compact(case["reference"]) for case in candidates}
    for index, left in enumerate(candidates):
        left_text = texts[left["id"]]
        left_hash = int(left["perceptual_hash"], 16)
        for right in candidates[:index]:
            distance = (left_hash ^ int(right["perceptual_hash"], 16)).bit_count()
            right_text = texts[right["id"]]
            repeated = len(left_text) >= 30 and left_text == right_text
            close = distance <= 5 and Levenshtein.normalized_similarity(left_text, right_text) >= 0.85
            if repeated or close:
                a, b = group(left["writer_id"]), group(right["writer_id"])
                parents[max(a, b)] = min(a, b)
                similar.append({
                    "id": left["id"], "related_id": right["id"],
                    "reason": "repeat_text" if repeated else "near_image_and_transcript",
                })

    for case in candidates:
        case["group"] = f"writer-{group(case['writer_id']):02d}"
    counts = Counter(case["group"] for case in candidates)
    forced = {case["group"] for case in candidates if case["writer_id"] in KNOWN_WRITERS}
    groups = sorted(counts.keys() - forced)
    rng = random.Random(SEED)
    rng.shuffle(groups)

    def choose(pool: list[str], target: int, upper: int) -> set[str]:
        possibilities: dict[int, tuple[str, ...]] = {0: ()}
        for key in pool:
            fresh = {size + counts[key]: bundle + (key,) for size, bundle in possibilities.items()
                     if size + counts[key] <= upper and size + counts[key] not in possibilities}
            possibilities.update(fresh)
        count = min(possibilities, key=lambda n: (abs(n - target), -n))
        return set(possibilities[count])

    forced_count = sum(counts[key] for key in forced)
    remaining_dev = max(0, 200 - forced_count)
    dev = forced | choose(groups, remaining_dev, remaining_dev + 4)
    test_target = min(800, 1000 - sum(counts[key] for key in dev))
    heldout = choose([key for key in groups if key not in dev], test_target, test_target)
    dev_cases = [case for case in candidates if case["group"] in dev]
    rng.shuffle(dev_cases)
    strata = {}
    for case in dev_cases:
        key = case["writing_direction"], case["medium"]
        strata.setdefault(key, []).append(case)
    pilot = [case for cases in strata.values() for case in cases[:min(4, len(cases))]]
    seen = {case["id"] for case in pilot}
    pilot.extend(case for case in dev_cases if case["id"] not in seen)
    pilot_ids = {case["id"] for case in pilot[:100]}
    for case in candidates:
        if case["group"] in dev:
            case["split"] = "pilot" if case["id"] in pilot_ids else "development"
        elif case["group"] in heldout:
            case["split"] = "heldout"
        else:
            case["split"] = "unused"
            exclusions.append({"id": case["id"], "reason": "writer_group_outside_study_cap"})
    return similar


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--reference-order", type=Path)
    options = parser.parse_args()
    root = options.root
    cache = root / "inventory.jsonl"
    reference_overrides = (json.loads(options.reference_order.read_text())
                           if options.reference_order else {})
    if cache.exists():
        all_rows = [json.loads(line) for line in cache.read_text().splitlines()]
    else:
        all_rows, exclusions = read_candidates(root / "shards", root)
        links = split_cases(all_rows, exclusions)
        write_jsonl(root / "exclusions.jsonl", exclusions)
        write_jsonl(root / "related-pages.jsonl", links)
        write_jsonl(cache, all_rows)
    reviewed = set()
    for row in all_rows:
        if row["id"] not in reference_overrides:
            continue
        review = reference_overrides[row["id"]]
        order = review["order"]
        by_id = {line["polygon_id"]: line for line in row["lines"]}
        if len(order) != len(by_id) or set(order) != set(by_id) or not review["reason"].strip():
            raise ValueError(f"invalid reference review for {row['id']}")
        row["reference"] = "\n".join(by_id[key]["text"] for key in order)
        row["reference_review"] = review
        reviewed.add(row["id"])
    if reviewed != reference_overrides.keys():
        raise ValueError("reference review contains unknown IDs")
    for split in ("pilot", "development", "heldout", "unused"):
        cohort = [r for r in all_rows if r["split"] == split]
        write_jsonl(root / f"{split}.jsonl", [{k: v for k, v in r.items() if k != "lines"} for r in cohort])
        print(split, len(cohort), "pages,", len({r["writer_id"] for r in cohort}), "writers,",
              len({r["group"] for r in cohort}), "groups",
              dict(Counter(r["writing_direction"] for r in cohort)))
    smoke = next(row for row in all_rows if row["source_filename"] == "0004_01_4_0_0_v.jpg")
    if smoke["split"] != "unused":
        raise ValueError("Provider preflight writer must be outside the scored cohorts")
    write_jsonl(root / "prepared-smoke.jsonl", [{key: smoke[key] for key in
                ("id", "media", "sha256", "cloud_eligible")}])


if __name__ == "__main__":
    main()
