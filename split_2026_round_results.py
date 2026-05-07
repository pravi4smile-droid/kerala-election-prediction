#!/usr/bin/env python3
"""
Split data/round_results.json into one 2026 round-result file per constituency.

Output: data/2026/001.json ... data/2026/140.json
Then run: python enrich_2026_data.py
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
INPUT_FILE = os.path.join(DATA_DIR, "data_parsing", "round_results.json")
OUTPUT_DIR = os.path.join(DATA_DIR, "2026")


def main():
    if not os.path.exists(INPUT_FILE):
        raise SystemExit(f"Missing {INPUT_FILE}. Run scrape_round_results.py first.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    written = 0
    for const_no_str, entry in data.items():
        const_no = int(const_no_str)
        out = {"const_no": const_no, "source_year": 2026, **entry}
        out_path = os.path.join(OUTPUT_DIR, f"{const_no:03d}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        written += 1

    print(f"Wrote {written} files to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
