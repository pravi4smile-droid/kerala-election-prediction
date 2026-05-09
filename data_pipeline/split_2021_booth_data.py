#!/usr/bin/env python3
"""
Split data/booth_wise_parsed.json into one enriched file per constituency.

Output: data/2021/001.json ... data/2021/140.json
"""

import ast
import json
import os
import re

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_SCRIPT_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
INPUT_FILE = os.path.join(DATA_DIR, "data_parsing", "booth_wise_parsed.json")
OUTPUT_DIR = os.path.join(DATA_DIR, "2021")
APP_FILE = os.path.join(BASE_DIR, "app.py")


def norm_name(s: str) -> str:
    return re.sub(r"[^a-z]", "", (s or "").lower())


def name_score(a: str, b: str) -> int:
    an = norm_name(a)
    bn = norm_name(b)
    if not an or not bn:
        return 0
    score = 0
    for length in range(4, min(len(an), len(bn)) + 1):
        for i in range(len(an) - length + 1):
            if an[i:i + length] in bn:
                score = max(score, length)
    return score


def load_raw_meta() -> dict[int, list]:
    with open(APP_FILE, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=APP_FILE)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "RAW_META":
                    rows = ast.literal_eval(node.value)
                    return {row[0]: row for row in rows}
    return {}


def clean_booths(booths: list[dict]) -> list[dict]:
    return [b for b in booths if 1 <= int(b.get("main", 0)) <= 500]


def enrich_candidates(const_no: int, names: list[str], raw_meta: dict[int, list]) -> list[dict]:
    enriched = [
        {
            "index": i,
            "name": name,
            "party": "",
            "alliance": "other",
            "is_major_alliance": False,
            "source": "parsed_2021_pdf_name_only",
        }
        for i, name in enumerate(names)
    ]

    row = raw_meta.get(const_no)
    if not row:
        return enriched

    alliance_rows = {
        "ldf": row[3],
        "udf": row[4],
        "nda": row[5],
    }
    used = set()
    for alliance, cand in alliance_rows.items():
        cand_name, party, votes = cand
        best_i, best_score = None, 0
        for i, name in enumerate(names):
            if i in used:
                continue
            score = name_score(cand_name, name)
            if score > best_score:
                best_i, best_score = i, score
        if best_i is not None and best_score >= 4:
            enriched[best_i].update({
                "party": party,
                "alliance": alliance,
                "is_major_alliance": True,
                "actual_votes_2021": votes,
                "source": "app.py RAW_META",
            })
            used.add(best_i)

    return enriched


def booth_summary(booths: list[dict], candidate_count: int) -> dict:
    main_booths = sorted({b["main"] for b in booths if not b.get("is_aux", False)})
    totals = [
        sum(b.get("votes", [])[i] if i < len(b.get("votes", [])) else 0 for b in booths)
        for i in range(candidate_count)
    ]
    return {
        "total_rows": len(booths),
        "main_booths": len(main_booths),
        "auxiliary_rows": sum(1 for b in booths if b.get("is_aux", False)),
        "total_votes_in_candidate_columns": sum(totals),
        "candidate_totals": totals,
    }


def main():
    if not os.path.exists(INPUT_FILE):
        raise SystemExit(f"Missing {INPUT_FILE}. Run parse_pdfs.py first.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(INPUT_FILE, encoding="utf-8") as f:
        parsed = json.load(f)

    raw_meta = load_raw_meta()
    written = 0
    for const_no_str, data in parsed.items():
        const_no = int(const_no_str)
        names = data.get("candidates", [])
        booths = clean_booths(data.get("booths", []))
        row = raw_meta.get(const_no)

        enriched = {
            "const_no": const_no,
            "name": data.get("name", ""),
            "source_year": 2021,
            "winner_alliance_2021": row[6] if row else "",
            "candidates": names,
            "candidates_2021": enrich_candidates(const_no, names, raw_meta),
            "booth_summary": booth_summary(booths, len(names)),
            "booths": booths,
        }

        out_path = os.path.join(OUTPUT_DIR, f"{const_no:03d}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(enriched, f, ensure_ascii=False, indent=2)
        written += 1

    print(f"Wrote {written} files to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
