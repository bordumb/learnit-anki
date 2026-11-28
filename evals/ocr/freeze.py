"""Export a reproducibility manifest and enable execution for audited cohorts."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path

import PIL
from PIL import features

from evals.ocr.audit import required_reviews
from evals.ocr.prepare import MAX_EDGE, REVISION, SEED
from evals.ocr.run import digest, records
from evals.transcription import normalize

UPSTREAM = "677ebdd627d9fbb3ea87693f24cc4e6d97c4a799"
SPLITS = ("pilot", "development", "heldout", "unused")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path)
    parser.add_argument("publication", type=Path)
    options = parser.parse_args()
    root, publication = options.study, options.publication
    inventory = records(root / "inventory.jsonl")
    audit_ids = required_reviews(inventory)
    excluded = records(root / "exclusions.jsonl")
    links = records(root / "related-pages.jsonl")
    tree = json.loads((root / "shards" / "tree.json").read_text(encoding="utf-8"))
    publication.mkdir(parents=True, exist_ok=True)
    lock = {
        "dataset": "llm-jp/jawildtext/handwriting_ocr",
        "revision": REVISION, "upstream_code_revision": UPSTREAM, "seed": SEED,
        "preprocessing": {"max_edge_px": MAX_EDGE, "jpeg_quality": 92, "exif_transpose": True,
                          "pillow": PIL.__version__, "jpeg_codec": features.version_codec("jpg")},
        "parquet_sha256": {Path(entry["path"]).name: entry["lfs"]["oid"]
                           for entry in tree if entry["path"].endswith(".parquet")},
        "source_rows": 1065, "eligible_rows": len(inventory), "related_pairs": len(links),
        "exclusions": dict(sorted(Counter(row["reason"] for row in excluded).items())),
        "splits": {},
    }
    seen_writers = {}
    seen_groups = {}
    seen_hashes = set()
    index_fields = (
        "id", "source_image_id", "source_filename", "split", "writer_id", "group", "writing_direction",
        "medium", "original_sha256", "sha256", "reference_sha256", "line_count",
        "flags", "review_required", "reviewed",
    )
    with (publication / "cases.csv").open("w", encoding="utf-8", newline="") as handle:
        index = csv.DictWriter(handle, fieldnames=index_fields, lineterminator="\n")
        index.writeheader()
        for split in SPLITS:
            file = root / f"{split}.jsonl"
            cases = records(file)
            lock["splits"][split] = {
                "manifest_sha256": digest(file), "pages": len(cases),
                "writers": len({case["writer_id"] for case in cases}),
                "groups": len({case["group"] for case in cases}),
                "by_direction": dict(sorted(Counter(case["writing_direction"] for case in cases).items())),
                "by_medium": dict(sorted(Counter(case["medium"] for case in cases).items())),
                "reference_characters": sum(len(normalize(case["reference"])) for case in cases),
                "incomplete_glyph_pages": sum(case["reference_has_incomplete_glyph"] for case in cases),
                "review_required": sum(case["id"] in audit_ids for case in cases),
                "reviewed": sum("reference_review" in case for case in cases),
                "review_complete": split in {"pilot", "heldout"} and bool(cases) and all(
                    "reference_review" in case for case in cases if case["id"] in audit_ids
                ),
            }
            for case in cases:
                pool = "development" if split == "pilot" else split
                if (seen_writers.setdefault(case["writer_id"], pool) != pool
                        or seen_groups.setdefault(case["group"], pool) != pool
                        or case["original_sha256"] in seen_hashes):
                    raise ValueError(f"Cohort overlap for {case['id']}")
                seen_hashes.add(case["original_sha256"])
                index.writerow({
                    **{k: case[k] for k in index_fields if k in case},
                    "reference_sha256": sha256(case["reference"].encode()).hexdigest(),
                    "flags": "|".join(case["flags"]), "review_required": case["id"] in audit_ids,
                    "reviewed": "reference_review" in case,
                })
    for filename, rows in (("exclusions", excluded), ("related-pages", links)):
        fields = ("id", "reason") if filename == "exclusions" else ("id", "related_id", "reason")
        with (publication / f"{filename}.csv").open("w", encoding="utf-8", newline="") as handle:
            output = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            output.writeheader()
            output.writerows(rows)
    data = json.dumps(lock, ensure_ascii=False, indent=2) + "\n"
    (publication / "cohort-lock.json").write_text(data, encoding="utf-8")
    pending = root / "cohort-lock.json.part"
    pending.write_text(data, encoding="utf-8")
    pending.replace(root / "cohort-lock.json")
    print(json.dumps(lock["splits"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
