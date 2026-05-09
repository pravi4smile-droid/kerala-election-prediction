#!/usr/bin/env python3
"""
Enrich data/2026/*.json with a candidates_2026 array (party, alliance, votes)
and winner_alliance_2026, making the schema consistent with data/2021/*.json.

Run after split_2026_round_results.py.
"""

import json
import os
import re

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_SCRIPT_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
DIR_2026 = os.path.join(DATA_DIR, "2026")
CANDS_FILE = os.path.join(DATA_DIR, "data_parsing", "candidates_2026.json")


def norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", (s or "").lower())


def name_score(a: str, b: str) -> int:
    an, bn = norm(a), norm(b)
    if not an or not bn:
        return 0
    score = 0
    for length in range(4, min(len(an), len(bn)) + 1):
        for i in range(len(an) - length + 1):
            if an[i : i + length] in bn:
                score = max(score, length)
    return score


# Full ECI party name substring → (abbreviated, alliance)
PARTY_ALLIANCE = [
    # LDF
    ("communist party of india (marxist)", "CPI(M)", "ldf"),
    ("communist party of india", "CPI", "ldf"),
    ("communist marxist party", "CMP", "ldf"),
    ("revolutionary socialist party", "RSP", "ldf"),
    ("loktantrik janata dal", "LJD", "ldf"),
    ("kerala socialist party", "KSP", "ldf"),
    ("all india forward bloc", "AIFB", "ldf"),
    ("janasabha", "JSP", "ldf"),
    # UDF
    ("indian national congress", "INC", "udf"),
    ("indian union muslim league", "IUML", "udf"),
    ("kerala congress (m)", "KC(M)", "udf"),
    ("kerala congress (b)", "KC(B)", "udf"),
    ("kerala congress (j)", "KC(J)", "udf"),
    ("kerala congress", "KC", "udf"),
    ("revolutionary marxist party", "RMPI", "udf"),
    ("indian national league", "INL", "udf"),
    ("nationalist congress party", "NCP", "udf"),
    # NDA
    ("bharatiya janata party", "BJP", "nda"),
    ("bharath dharma jana sena", "BDJS", "nda"),
]


def classify_party(full_name: str) -> tuple[str, str]:
    """Return (abbreviated_party, alliance) from a full ECI party name."""
    nl = full_name.lower()
    for substr, abbr, alliance in PARTY_ALLIANCE:
        if substr in nl:
            return abbr, alliance
    if "independent" in nl:
        return "IND", "other"
    return full_name, "other"


def build_candidates_2026(entry: dict, cands_meta: dict) -> tuple[list, str]:
    names = entry.get("candidates", [])
    parties_full = entry.get("parties", [])
    totals = entry.get("total", [0] * len(names))
    grand_total = sum(totals) or 1

    items = []
    for i, name in enumerate(names):
        full_party = parties_full[i] if i < len(parties_full) else ""
        abbr, alliance = classify_party(full_party)
        votes = totals[i] if i < len(totals) else 0
        items.append({
            "index": i,
            "name": name,
            "party": abbr,
            "alliance": alliance,
            "is_major_alliance": alliance in ("ldf", "udf", "nda"),
            "source": "ECI round results scraper",
            "actual_votes_2026": votes,
            "vote_pct_2026": f"{100 * votes / grand_total:.2f}",
        })

    # Override alliance/party for the three major candidates via name matching
    used: set[int] = set()
    for alliance in ("ldf", "udf", "nda"):
        cand_info = cands_meta.get(alliance, {})
        ref_name = cand_info.get("name", "")
        ref_party = cand_info.get("party", "")
        if not ref_name:
            continue
        best_i, best_score = None, 0
        for i, item in enumerate(items):
            if i in used:
                continue
            score = name_score(ref_name, item["name"])
            if score > best_score:
                best_i, best_score = i, score
        if best_i is not None and best_score >= 4:
            items[best_i]["alliance"] = alliance
            items[best_i]["is_major_alliance"] = True
            if ref_party:
                items[best_i]["party"] = ref_party
            used.add(best_i)

    # Derive winner alliance from major alliance candidates by vote count
    winner_alliance = ""
    best_votes = -1
    for item in items:
        if item["is_major_alliance"] and item["actual_votes_2026"] > best_votes:
            best_votes = item["actual_votes_2026"]
            winner_alliance = item["alliance"]

    # Fallback: overall winner if no major alliance data
    if not winner_alliance and totals:
        winner_alliance = items[totals.index(max(totals))]["alliance"]

    return items, winner_alliance


def main():
    with open(CANDS_FILE, encoding="utf-8") as f:
        cands_2026 = json.load(f)

    updated = 0
    for fname in sorted(os.listdir(DIR_2026)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(DIR_2026, fname)
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)

        const_no = entry["const_no"]
        cands_meta = cands_2026.get(str(const_no), {})

        enriched_cands, winner_alliance = build_candidates_2026(entry, cands_meta)

        out = {
            "const_no": const_no,
            "name": entry.get("name", ""),
            "source_year": 2026,
            "winner_alliance_2026": winner_alliance,
            "candidates": entry.get("candidates", []),
            "candidates_2026": enriched_cands,
            "rounds": entry.get("rounds", []),
            "total": entry.get("total", []),
        }
        if "fetched_at" in entry:
            out["fetched_at"] = entry["fetched_at"]

        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        updated += 1

    print(f"Enriched {updated} files in {DIR_2026}")


if __name__ == "__main__":
    main()
