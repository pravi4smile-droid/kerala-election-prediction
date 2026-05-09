#!/usr/bin/env python3
"""Patch 2021 LDF/UDF/NDA alliance labels from the Wikipedia candidate table.

The Kerala Assembly result pages provide party/vote rows, but some front-backed
or Kerala Congress candidates are hard to classify from party code alone.  The
Wikipedia candidate list has explicit LDF/UDF/NDA columns, so use it only for
alliance assignment while preserving official vote totals from the result page.
"""

import json
import os
import re
from difflib import SequenceMatcher

import requests
from bs4 import BeautifulSoup

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_SCRIPT_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data", "2021")
WIKI_URL = "https://en.wikipedia.org/wiki/List_of_candidates_in_the_2021_Kerala_Legislative_Assembly_election"


def norm_name(s: str) -> str:
    s = re.sub(r"\b(mr|mrs|ms|dr|adv|advocate|prof|shri|smt)\b", "", (s or "").lower())
    return re.sub(r"[^a-z]", "", s)


def name_score(a: str, b: str) -> int:
    an = norm_name(a)
    bn = norm_name(b)
    if not an or not bn:
        return 0
    if an == bn:
        return max(len(an), len(bn)) + 10
    score = 0
    for length in range(4, min(len(an), len(bn)) + 1):
        for i in range(len(an) - length + 1):
            if an[i:i + length] in bn:
                score = max(score, length)
    if SequenceMatcher(None, an, bn).ratio() >= 0.72:
        score = max(score, 5)
    return score


def compact_cells(tr) -> list[str]:
    return [
        c.get_text(" ", strip=True)
        for c in tr.find_all(["td", "th"])
        if c.get_text(" ", strip=True)
    ]


def fetch_wiki_rows() -> dict[int, dict]:
    res = requests.get(WIKI_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    table = soup.find("table")
    rows = {}
    for tr in table.find_all("tr"):
        cells = compact_cells(tr)
        if not cells or cells[0] in {"District", "No."}:
            continue
        if cells[0].isdigit():
            values = cells
        elif len(cells) > 1 and cells[1].isdigit():
            values = cells[1:]
        else:
            continue
        if len(values) < 8 or not values[0].isdigit():
            continue
        no = int(values[0])
        rows[no] = {
            "name": values[1],
            "ldf": {"party": values[2], "candidate": values[3]},
            "udf": {"party": values[4], "candidate": values[5]},
            "nda": {"party": values[6], "candidate": values[7]},
        }
    return rows


def patch_file(path: str, wiki: dict) -> tuple[int, list[str]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cands = data.get("candidates_2021", [])
    changed = []
    for alliance in ("ldf", "udf", "nda"):
        expected = wiki.get(alliance, {})
        expected_name = expected.get("candidate", "")
        expected_party = expected.get("party", "")
        if not expected_name or expected_name.lower() == "did not contest":
            continue
        best = None
        best_score = 0
        for cand in cands:
            score = name_score(expected_name, cand.get("name", ""))
            if score > best_score:
                best = cand
                best_score = score
        if best is None or best_score < 4:
            continue
        old_alliance = best.get("alliance")
        old_party = best.get("party")
        if old_alliance != alliance or not old_party:
            best["alliance"] = alliance
            best["is_major_alliance"] = True
            if expected_party:
                best["party"] = expected_party
            best["alliance_source"] = "Wikipedia 2021 candidate list"
            best["alliance_source_url"] = WIKI_URL
            changed.append(
                f"{alliance.upper()}: {best.get('name')} {old_party}/{old_alliance} -> {best.get('party')}/{alliance}"
            )
    if changed:
        data["wiki_candidate_source_2021"] = WIKI_URL
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return len(changed), changed


def main():
    wiki_rows = fetch_wiki_rows()
    total = 0
    for no in range(1, 141):
        path = os.path.join(DATA_DIR, f"{no:03d}.json")
        if not os.path.exists(path) or no not in wiki_rows:
            continue
        count, changed = patch_file(path, wiki_rows[no])
        total += count
        if changed:
            print(f"{no:03d} {wiki_rows[no]['name']}:")
            for item in changed:
                print(f"  {item}")
    print(f"Patched {total} alliance labels from Wikipedia")


if __name__ == "__main__":
    main()
