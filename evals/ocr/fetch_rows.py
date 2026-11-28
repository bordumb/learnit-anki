"""Fetch the pinned JaWildText handwriting inventory through the HF viewer."""
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode, urlsplit
import sys

REVISION = "627ca7ea7c224ffe1accff8737991fc2240784fa"
BASE = "https://datasets-server.huggingface.co/rows"
TOTAL = 1065


def download(url: str, path: Path) -> None:
    pending = path.with_suffix(path.suffix + ".part")
    subprocess.run(
        ["curl", "--fail", "--location", "--silent", "--show-error",
         "--retry", "2", "--connect-timeout", "15", "--max-time", "120",
         "--output", str(pending), url],
        check=True,
    )
    pending.replace(path)


def fetch_inventory(root: Path) -> list[dict]:
    root.mkdir(parents=True, exist_ok=True)

    def fetch_block(offset: int) -> list[dict]:
        path = root / f"part-{offset:04d}.json"
        params = urlencode({
            "dataset": "llm-jp/jawildtext",
            "config": "handwriting_ocr",
            "split": "train",
            "offset": offset,
            "length": min(100, TOTAL - offset),
        })
        if not path.exists():
            download(f"{BASE}?{params}", path)
        obj = json.loads(path.read_text())
        if obj["num_rows_total"] != TOTAL:
            raise ValueError("unexpected number of source rows")
        return obj["rows"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = [row for block in pool.map(fetch_block, range(0, TOTAL, 100)) for row in block]
    if [row["row_idx"] for row in rows] != list(range(TOTAL)):
        raise ValueError("source rows do not cover the complete inventory")
    if len({entry["row"]["image_id"] for entry in rows}) != TOTAL:
        raise ValueError("source image IDs must be unique")
    for entry in rows:
        url = urlsplit(entry["row"]["image"]["src"])
        if url.hostname != "datasets-server.huggingface.co" or f"/--/{REVISION}/--/" not in url.path:
            raise ValueError("source image URL does not point to the locked revision")
    return rows


if __name__ == "__main__":
    root = Path(sys.argv[1])
    rows = fetch_inventory(root / "inventory")
    print(f"Loaded {len(rows)} source rows from the pinned viewer revision.")
