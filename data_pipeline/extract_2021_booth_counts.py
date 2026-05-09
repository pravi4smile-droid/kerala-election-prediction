#!/usr/bin/env python3
"""
Extract and save 2021 booth counts from data/2021/*.json split files.
"""

import json
import os

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_SCRIPT_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
PARSED_2021_DIR = os.path.join(DATA_DIR, "2021")
BOOTHS_2021_FILE = os.path.join(DATA_DIR, "data_parsing", "booths_2021.json")


def load_2021_data() -> dict:
    data = {}
    if os.path.isdir(PARSED_2021_DIR):
        for fname in os.listdir(PARSED_2021_DIR):
            if fname.endswith(".json"):
                with open(os.path.join(PARSED_2021_DIR, fname), encoding="utf-8") as f:
                    entry = json.load(f)
                data[str(entry["const_no"])] = entry
    return data


def main():
    print("=" * 60)
    print("  Kerala Election 2021 - Booth Count Extractor")
    print("=" * 60)

    data = load_2021_data()
    if not data:
        print("\nNo 2021 parsed booth data found.")
        print("Run: python parse_pdfs.py && python split_2021_booth_data.py")
        return

    booths_2021 = {}
    for const_no_str, const_data in data.items():
        booths = const_data.get("booths", [])
        main_booths = {b["main"] for b in booths if not b.get("is_aux", False)}
        booths_2021[const_no_str] = len(main_booths)

    with open(BOOTHS_2021_FILE, "w", encoding="utf-8") as f:
        json.dump(booths_2021, f, indent=2)

    print(f"Extracted booth counts for {len(booths_2021)} constituencies")
    print(f"Saved to {BOOTHS_2021_FILE}")
    print("\nSample (first 5 constituencies):")
    for const_no in sorted(int(k) for k in booths_2021.keys())[:5]:
        print(f"  Const {const_no}: {booths_2021[str(const_no)]} booths")


if __name__ == "__main__":
    main()
