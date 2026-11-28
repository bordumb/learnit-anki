"""Make local proof sheets of the proposed line order without reading predictions."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from random import Random
import re

from PIL import Image, ImageDraw, ImageFont

from evals.ocr.prepare import SEED
from evals.ocr.run import records

GRID_COLUMNS = 3
GRID_ROWS = 4
CELL = (370, 280)
WATCH = {"mixed_geometry", "source_direction_mismatch", "exif_rotation"}
MARGIN_LABEL = re.compile(r"(?:[0-9０-９]{1,2}|(?i:No\.?|Date:?|Page|KOKUYO.*)|[NEWS])")


def required_reviews(cases):
    active = [case for case in cases if case["split"] in {"pilot", "heldout"}]
    selected = {case["id"] for case in active if WATCH.intersection(case["flags"])
                or case["writing_direction"] == "vertical"}
    strata = defaultdict(list)
    for case in active:
        if case["id"] not in selected:
            strata[case["split"], case["writing_direction"], case["medium"]].append(case["id"])
    rng = Random(SEED)
    for key, ids in sorted(strata.items()):
        selected.update(rng.sample(sorted(ids), min(len(ids), 4 if key[0] == "pilot" else 6)))
    for case in active:
        direction = Path(case["source_filename"]).stem.rsplit("_", 1)[-1]
        if (direction != case["writing_direction"][0]
                or any(MARGIN_LABEL.fullmatch(line["text"].strip()) for line in case["lines"])):
            selected.add(case["id"])
    return selected


def draw_page(case, root, canvas, offset, font):
    with Image.open(root / case["media"]) as image:
        image.thumbnail((CELL[0] - 8, CELL[1] - 32))
        x = offset[0] + (CELL[0] - image.width) // 2
        y = offset[1] + 20
        canvas.paste(image, (x, y))
        original_width, original_height = case["original_size"]
        source_ratio = original_width / original_height
        image_ratio = image.width / image.height
        if "exif_rotation" in case["flags"] and abs(source_ratio - image_ratio) > 0.1:
            original_width, original_height = original_height, original_width
        scale_x = image.width / original_width
        scale_y = image.height / original_height
    draw = ImageDraw.Draw(canvas)
    draw.text((offset[0] + 4, offset[1] + 2),
              f"{case['source_filename']} | {case['writing_direction'][0].upper()} | {case['line_count']}",
              fill="#132a42", font=font)
    for index, line in enumerate(case["lines"], 1):
        poly = [(x + px * scale_x, y + py * scale_y) for px, py in line["polygon"]]
        if not all(x - 2 <= px <= x + image.width + 2 and y - 2 <= py <= y + image.height + 2 for px, py in poly):
            continue
        draw.line(poly + [poly[0]], fill="#2188c6", width=2)
        px, py = min(pos[0] for pos in poly), min(pos[1] for pos in poly)
        tx, ty = px, max(y, py - 13)
        label = str(index)
        draw.rectangle((tx, ty, tx + 9 * len(label) + 4, ty + 13), fill="#132a42")
        draw.text((tx + 2, ty - 1), label, fill="white", font=font)
    bottom = f"{case['id'].removeprefix('jawildtext-')} / {', '.join(case['flags'])}"
    draw.text((offset[0] + 4, offset[1] + CELL[1] - 14), bottom, fill="#132a42", font=font)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path)
    parser.add_argument("split", choices=("pilot", "heldout"))
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--skip-index", type=Path, help="Omit pages already present in an earlier sheet index")
    options = parser.parse_args()
    root = options.study
    inventory = records(root / "inventory.jsonl")
    required = required_reviews(inventory)
    if options.skip_index:
        existing = json.loads(options.skip_index.read_text())
        required.difference_update(page["id"] for sheet in existing for page in sheet["pages"])
    cases = [case for case in inventory if case["split"] == options.split and case["id"] in required]
    cases.sort(key=lambda case: (not bool(WATCH.intersection(case["flags"])), case["id"]))
    cases = cases[:options.max_pages]
    output = root / "audit" / (f"{options.split}-supplement" if options.skip_index else options.split)
    output.mkdir(parents=True, exist_ok=True)
    sheets = []
    font = ImageFont.load_default(size=13)
    pages_per_sheet = GRID_COLUMNS * GRID_ROWS
    for start in range(0, len(cases), pages_per_sheet):
        rows = cases[start:start + pages_per_sheet]
        sheet = Image.new("RGB", (CELL[0] * GRID_COLUMNS, CELL[1] * GRID_ROWS), "#fafafb")
        for i, case in enumerate(rows):
            offset = (i % GRID_COLUMNS * CELL[0], i // GRID_COLUMNS * CELL[1])
            draw_page(case, root, sheet, offset, font)
        name = f"sheet-{start // pages_per_sheet + 1:02d}.png"
        sheet.save(output / name)
        sheets.append({
            "sheet": name,
            "pages": [{"id": case["id"], "order": [line["polygon_id"] for line in case["lines"]],
                       "flags": case["flags"]} for case in rows],
        })
    (output / "index.json").write_text(json.dumps(sheets, ensure_ascii=False, indent=2) + "\n")
    print(f"{options.split}: {len(cases)} pages on {len(sheets)} sheets")


if __name__ == "__main__":
    main()
