#!/usr/bin/env python3
"""Patch 2011/2016 winner and runner-up metadata from Wikipedia result tables.

The official booth PDFs provide booth-level votes, while some parsed candidate
rows miss party/alliance metadata. Wikipedia's constituency result tables list
winner and runner-up party/alliance, so use those labels for matched candidates
and leave all other rows unchanged.
"""

import json
import os
import re
from difflib import SequenceMatcher

import requests
from bs4 import BeautifulSoup

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_SCRIPT_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")

SOURCES = {
    2011: "https://en.wikipedia.org/wiki/2011_Kerala_Legislative_Assembly_election",
    2016: "https://en.wikipedia.org/wiki/2016_Kerala_Legislative_Assembly_election",
}


def norm_name(value: str) -> str:
    value = re.sub(
        r"\b(mr|mrs|ms|dr|adv|advocate|prof|shri|smt)\b",
        "",
        (value or "").lower(),
    )
    return re.sub(r"[^a-z]", "", value)


def name_score(left: str, right: str) -> int:
    left_n = norm_name(left)
    right_n = norm_name(right)
    if not left_n or not right_n:
        return 0
    if left_n == right_n:
        return max(len(left_n), len(right_n)) + 10

    score = 0
    for length in range(4, min(len(left_n), len(right_n)) + 1):
        for i in range(len(left_n) - length + 1):
            if left_n[i:i + length] in right_n:
                score = max(score, length)
    if SequenceMatcher(None, left_n, right_n).ratio() >= 0.72:
        score = max(score, 5)
    return score


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ")).strip()


def to_int(value: str) -> int:
    digits = re.sub(r"[^0-9]", "", value or "")
    return int(digits) if digits else 0


def norm_alliance(value: str) -> str:
    upper = compact(value).upper()
    if upper in {"LDF", "UDF", "NDA"}:
        return upper.lower()
    return "other"


def table_cells(row) -> list[str]:
    return [
        text
        for cell in row.find_all(["td", "th"])
        if (text := compact(cell.get_text(" ", strip=True)))
    ]


def find_result_table(soup: BeautifulSoup):
    for table in soup.find_all("table"):
        text = compact(table.get_text(" ", strip=True))
        if (
            "Constituency" in text
            and "Winner" in text
            and "Runner-up" in text
            and "Margin" in text
        ):
            return table
    raise RuntimeError("Could not find constituency result table")


def fetch_wiki_results(year: int) -> dict[int, list[dict]]:
    url = SOURCES[year]
    response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    table = find_result_table(soup)

    rows: dict[int, list[dict]] = {}
    for tr in table.find_all("tr"):
        cells = table_cells(tr)
        if not cells or not cells[0].isdigit() or len(cells) < 12:
            continue

        const_no = int(cells[0])
        rows[const_no] = [
            {
                "role": "winner",
                "name": cells[2],
                "party": cells[3],
                "alliance": norm_alliance(cells[4]),
                "votes": to_int(cells[5]),
                "percent": cells[6],
                "source_url": url + "#Results_by_constituency",
            },
            {
                "role": "runner_up",
                "name": cells[7],
                "party": cells[8],
                "alliance": norm_alliance(cells[9]),
                "votes": to_int(cells[10]),
                "percent": cells[11],
                "source_url": url + "#Results_by_constituency",
            },
        ]
    return rows


def patch_file(year: int, const_no: int, wiki_rows: list[dict]) -> list[str]:
    path = os.path.join(DATA_DIR, str(year), f"{const_no:03d}.json")
    if not os.path.exists(path):
        return []

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    changed = []
    candidates = data.get(f"candidates_{year}", [])
    used = set()
    for wiki_row in wiki_rows:
        best_i, best_score = None, 0
        for i, candidate in enumerate(candidates):
            if i in used:
                continue
            score = name_score(wiki_row["name"], candidate.get("name", ""))
            if score > best_score:
                best_i, best_score = i, score
        if best_i is None or best_score < 4:
            continue

        candidate = candidates[best_i]
        old = (candidate.get("party", ""), candidate.get("alliance", ""))
        candidate.update({
            "party": wiki_row["party"],
            "alliance": wiki_row["alliance"],
            "is_major_alliance": wiki_row["alliance"] in {"ldf", "udf", "nda"},
            f"actual_votes_{year}": wiki_row["votes"],
            f"vote_pct_{year}": wiki_row["percent"],
            "source": f"Wikipedia {year} results by constituency",
            "source_url": wiki_row["source_url"],
            "result_role": wiki_row["role"],
        })
        new = (candidate.get("party", ""), candidate.get("alliance", ""))
        used.add(best_i)
        if old != new:
            changed.append(
                f"{wiki_row['role']}: {candidate.get('name')} {old[0]}/{old[1]} -> {new[0]}/{new[1]}"
            )

    if changed:
        data[f"wiki_result_source_{year}"] = SOURCES[year] + "#Results_by_constituency"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return changed


def main():
    total = 0
    for year in (2011, 2016):
        wiki_results = fetch_wiki_results(year)
        year_total = 0
        print(f"{year}: fetched {len(wiki_results)} constituency result rows")
        for const_no in range(1, 141):
            changed = patch_file(year, const_no, wiki_results.get(const_no, []))
            year_total += len(changed)
            if changed:
                print(f"{year} {const_no:03d}:")
                for item in changed:
                    print(f"  {item}")
        total += year_total
        print(f"{year}: patched {year_total} winner/runner-up labels")
    print(f"Patched {total} labels from Wikipedia result tables")


if __name__ == "__main__":
    main()
