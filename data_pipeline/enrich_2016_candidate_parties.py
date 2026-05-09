#!/usr/bin/env python3
"""Enrich data/2016/*.json candidate rows from Kerala Assembly 2016 result pages."""

import json
import os
import re
import time
from difflib import SequenceMatcher

import requests
from bs4 import BeautifulSoup

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_SCRIPT_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data", "2016")
SOURCE_URL = "http://www.keralaassembly.org/election/assembly_poll.php?no={no}&year=2016"

LDF_PARTIES = {
    "CPIM", "CPI(M)", "CPI", "JD(S)", "JDS", "NCP", "KC(M)", "KC(B)", "RSP",
    "CON(S)", "CS", "LDF", "INL", "CMP", "KCM",
}
UDF_PARTIES = {
    "INC", "IUML", "ML", "KC", "KC(J)", "KEC", "SJD", "JDU", "UDF", "RSP",
}
NDA_PARTIES = {"BJP", "BDJS", "AIADMK", "NDA"}


def norm_name(s: str) -> str:
    s = re.sub(r"\b(mr|mrs|ms|dr|adv|advocate|prof|shri|smt)\b", "", (s or "").lower())
    return re.sub(r"[^a-z]", "", s)


def name_tokens(s: str) -> list[str]:
    s = re.sub(r"\b(mr|mrs|ms|dr|adv|advocate|prof|shri|smt)\b", "", (s or "").lower())
    return re.findall(r"[a-z]+", s)


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
        score = max(score, 4)
    a_tokens = name_tokens(a)
    b_tokens = name_tokens(b)
    token_hits = 0
    for at in a_tokens:
        if any(SequenceMatcher(None, at, bt).ratio() >= 0.75 for bt in b_tokens):
            token_hits += 1
    if token_hits >= 1 and len(a_tokens) <= 2:
        score = max(score, 4)
    if token_hits >= 2:
        score = max(score, 5)
    return score


def clean_party(party: str) -> str:
    return re.sub(r"\s+", " ", (party or "").strip())


def classify_alliance(party: str) -> str:
    p = clean_party(party).upper().replace(".", "")
    if p in {x.replace(".", "") for x in NDA_PARTIES}:
        return "nda"
    if p in {x.replace(".", "") for x in LDF_PARTIES}:
        return "ldf"
    if p in {x.replace(".", "") for x in UDF_PARTIES}:
        return "udf"
    if "COMMUNIST PARTY OF INDIA" in p:
        return "ldf"
    if "INDIAN NATIONAL CONGRESS" in p or "INDIAN UNION MUSLIM LEAGUE" in p:
        return "udf"
    if "BHARATIYA JANATA" in p or "BHARATH DHARMA" in p:
        return "nda"
    return "other"


def to_int(s: str) -> int:
    digits = re.sub(r"[^0-9]", "", s or "")
    return int(digits) if digits else 0


def fetch_candidates(const_no: int) -> list[dict]:
    url = SOURCE_URL.format(no=const_no)
    res = requests.get(url, timeout=20, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 4:
            continue
        if "Name of the Candidate" in cells[0] or cells[0].lower() == "total":
            continue
        votes = to_int(cells[2])
        if votes <= 0:
            continue
        rows.append({
            "name": cells[0],
            "party": clean_party(cells[1]),
            "votes": votes,
            "percentage": cells[3],
            "source_url": url,
        })
    return rows


def enrich_file(path: str, source_rows: list[dict]) -> int:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if not data.get("candidates_2016") and source_rows:
        data["candidates"] = [row["name"] for row in source_rows]
        data["candidates_2016"] = [
            {
                "index": i,
                "name": row["name"],
                "party": row["party"],
                "alliance": classify_alliance(row["party"]),
                "is_major_alliance": classify_alliance(row["party"]) in {"ldf", "udf", "nda"},
                "actual_votes_2016": row["votes"],
                "vote_pct_2016": row["percentage"],
                "source": "keralaassembly.org 2016 result page",
                "source_url": row["source_url"],
            }
            for i, row in enumerate(source_rows)
        ]
        data["public_source_2016"] = SOURCE_URL.format(no=data["const_no"])
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return len(source_rows)

    matched = 0
    used = set()
    for cand in data.get("candidates_2016", []):
        best_i, best_score = None, 0
        for i, row in enumerate(source_rows):
            if i in used:
                continue
            score = name_score(cand.get("name", ""), row["name"])
            if score > best_score:
                best_i, best_score = i, score
        if best_i is None or best_score < 4:
            continue
        row = source_rows[best_i]
        cand.update({
            "party": row["party"],
            "alliance": classify_alliance(row["party"]),
            "actual_votes_2016": row["votes"],
            "vote_pct_2016": row["percentage"],
            "source": "keralaassembly.org 2016 result page",
            "source_url": row["source_url"],
        })
        cand["is_major_alliance"] = cand["alliance"] in {"ldf", "udf", "nda"}
        used.add(best_i)
        matched += 1

    data["public_source_2016"] = SOURCE_URL.format(no=data["const_no"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return matched


def main():
    total = 0
    for const_no in range(1, 141):
        path = os.path.join(DATA_DIR, f"{const_no:03d}.json")
        if not os.path.exists(path):
            continue
        rows = fetch_candidates(const_no)
        matched = enrich_file(path, rows)
        total += matched
        print(f"{const_no:03d}: public rows {len(rows)}, matched {matched}")
        time.sleep(0.1)
    print(f"Enriched {total} candidate rows")


if __name__ == "__main__":
    main()
