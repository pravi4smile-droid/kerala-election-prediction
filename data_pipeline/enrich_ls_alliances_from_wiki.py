#!/usr/bin/env python3
"""Enrich 2019/2024 LS split JSON with UDF/LDF/NDA candidate metadata.

Source tables:
- https://en.wikipedia.org/wiki/2019_Indian_general_election_in_Kerala#Constituency_candidates
- https://en.wikipedia.org/wiki/2024_Indian_general_election_in_Kerala#Candidates
"""

from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher

import pdfplumber

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_SCRIPT_DIR)


LS_2019 = [
    ("Kasaragod", ("INC", "Rajmohan Unnithan"), ("CPI(M)", "K. P. Satheesh Chandran"), ("BJP", "Raveesh Thanthri Kuntar")),
    ("Kannur", ("INC", "K. Sudhakaran"), ("CPI(M)", "P. K. Sreemathy"), ("BJP", "C. K. Padmanabhan")),
    ("Vatakara", ("INC", "K. Muraleedharan"), ("CPI(M)", "P. Jayarajan"), ("BJP", "V. K. Sajeevan")),
    ("Wayanad", ("INC", "Rahul Gandhi"), ("CPI", "P. P. Suneer"), ("BDJS", "Thushar Vellapally")),
    ("Kozhikode", ("INC", "M. K. Raghavan"), ("CPI(M)", "A. Pradeepkumar"), ("BJP", "K. P. Prakash Babu")),
    ("Malappuram", ("IUML", "P. K. Kunhalikutty"), ("CPI(M)", "V. P. Sanu"), ("BJP", "Unnikrishnan Master")),
    ("Ponnani", ("IUML", "E. T. Mohammed Basheer"), ("IND", "P. V. Anvar"), ("BJP", "V. T. Rema")),
    ("Palakkad", ("INC", "V. K. Sreekandan"), ("CPI(M)", "M. B. Rajesh"), ("BJP", "C. Krishnakumar")),
    ("Alathur", ("INC", "Remya Haridas"), ("CPI(M)", "P. K. Biju"), ("BDJS", "T. V. Babu")),
    ("Thrissur", ("INC", "T. N. Prathapan"), ("CPI", "Rajaji Mathew Thomas"), ("BJP", "Suresh Gopi")),
    ("Chalakudy", ("INC", "Benny Behanan"), ("CPI(M)", "Innocent Vareed Thekkethala"), ("BJP", "A. N. Radhakrishnan")),
    ("Ernakulam", ("INC", "Hibi Eden"), ("CPI(M)", "P. Rajeev"), ("BJP", "Alphons Kannanthanam")),
    ("Idukki", ("INC", "Dean Kuriakose"), ("IND", "Joice George"), ("BDJS", "Biju Krishnan")),
    ("Kottayam", ("KC(M)", "Thomas Chazhikadan"), ("CPI(M)", "V. N. Vasavan"), ("KC(T)", "P. C. Thomas")),
    ("Alappuzha", ("INC", "Shanimol Usman"), ("CPI(M)", "A. M. Ariff"), ("BJP", "K. S. Radhakrishnan")),
    ("Mavelikkara", ("INC", "Kodikunnil Suresh"), ("CPI", "Chittayam Gopakumar"), ("BDJS", "Thazhava Sahadevan")),
    ("Pathanamthitta", ("INC", "Anto Antony"), ("CPI(M)", "Veena George"), ("BJP", "K. Surendran")),
    ("Kollam", ("RSP", "N. K. Premachandran"), ("CPI(M)", "K. N. Balagopal"), ("BJP", "K. V. Sabu")),
    ("Attingal", ("INC", "Adoor Prakash"), ("CPI(M)", "A. Sampath"), ("BJP", "Shobha Surendran")),
    ("Thiruvananthapuram", ("INC", "Shashi Tharoor"), ("CPI", "C. Divakaran"), ("BJP", "Kummanam Rajasekharan")),
]

LS_2024 = [
    ("Kasaragod", ("INC", "Rajmohan Unnithan"), ("CPI(M)", "M. V. Balakrishnan"), ("BJP", "M. L. Ashwini")),
    ("Kannur", ("INC", "K. Sudhakaran"), ("CPI(M)", "MV Jayarajan"), ("BJP", "C. Raghunath")),
    ("Vatakara", ("INC", "Shafi Parambil"), ("CPI(M)", "K. K. Shailaja"), ("BJP", "Prafulla Krishna")),
    ("Wayanad", ("INC", "Rahul Gandhi"), ("CPI", "Annie Raja"), ("BJP", "K. Surendran")),
    ("Kozhikode", ("INC", "M. K. Raghavan"), ("CPI(M)", "Elamaram Kareem"), ("BJP", "M. T. Ramesh")),
    ("Malappuram", ("IUML", "E. T. Mohammed Basheer"), ("CPI(M)", "V. Vaseef"), ("BJP", "M. Abdul Salam")),
    ("Ponnani", ("IUML", "Abdussamad Samadani"), ("CPI(M)", "K. S. Hamza"), ("BJP", "Niveditha Subramanian")),
    ("Palakkad", ("INC", "V. K. Sreekandan"), ("CPI(M)", "A. Vijayaraghavan"), ("BJP", "C. Krishnakumar")),
    ("Alathur", ("INC", "Ramya Haridas"), ("CPI(M)", "K. Radhakrishnan"), ("BJP", "T. N. Sarasu")),
    ("Thrissur", ("INC", "K Muraleedharan"), ("CPI", "V. S. Sunil Kumar"), ("BJP", "Suresh Gopi")),
    ("Chalakudy", ("INC", "Benny Behanan"), ("CPI(M)", "C. Raveendranath"), ("BDJS", "K. A. Unnikrishnan")),
    ("Ernakulam", ("INC", "Hibi Eden"), ("CPI(M)", "K. J. Shine"), ("BJP", "K. S. Radhakrishnan")),
    ("Idukki", ("INC", "Dean Kuriakose"), ("CPI(M)", "Joice George"), ("BDJS", "Sangeetha Vishwanathan")),
    ("Kottayam", ("KEC", "Francis George"), ("KC(M)", "Thomas Chazhikadan"), ("BDJS", "Thushar Vellapally")),
    ("Alappuzha", ("INC", "K. C. Venugopal"), ("CPI(M)", "A. M. Ariff"), ("BJP", "Sobha Surendran")),
    ("Mavelikara", ("INC", "Kodikunnil Suresh"), ("CPI", "C. A. Arun Kumar"), ("BDJS", "Baiju Kalasala")),
    ("Pathanamthitta", ("INC", "Anto Antony"), ("CPI(M)", "Thomas Issac"), ("BJP", "Anil Antony")),
    ("Kollam", ("RSP", "N. K. Premachandran"), ("CPI(M)", "Mukesh"), ("BJP", "G. Krishnakumar")),
    ("Attingal", ("INC", "Adoor Prakash"), ("CPI(M)", "V. Joy"), ("BJP", "V. Muraleedharan")),
    ("Thiruvananthapuram", ("INC", "Shashi Tharoor"), ("CPI", "Panniyan Raveendran"), ("BJP", "Rajeev Chandrasekhar")),
]


def compact_constituency(name: str) -> str:
    compacted = re.sub(r"[^A-Z0-9]", "", name.upper().replace("(SC)", ""))
    return {
        "MALAPURAM": "MALAPPURAM",
        "CHALAKKUDY": "CHALAKUDY",
        "MAVELIKKARA": "MAVELIKARA",
    }.get(compacted, compacted)


def normalize_name(name: str) -> str:
    name = name.upper()
    name = re.sub(r"\b(ADV|ADVOCATE|DR|PROF|MASTER|TEACHER|S/O)\b", " ", name)
    name = re.sub(r"[^A-Z0-9]+", " ", name)
    tokens = [token for token in name.split() if len(token) > 1]
    return " ".join(tokens)


MATCH_ALIASES = {
    "Innocent Vareed Thekkethala": ["Innocent"],
    "Niveditha Subramanian": ["Nivedida"],
}


def base_match_score(expected: str, actual: str) -> float:
    exp = normalize_name(expected)
    act = normalize_name(actual)
    if not exp or not act:
        return 0.0
    exp_joined = exp.replace(" ", "")
    act_joined = act.replace(" ", "")
    if exp == act or exp_joined == act_joined:
        return 1.0
    shorter = min(len(exp_joined), len(act_joined))
    longer = max(len(exp_joined), len(act_joined))
    if (exp in act or act in exp) and shorter / max(longer, 1) >= 0.55:
        return 0.96
    exp_tokens = set(exp.split())
    act_tokens = set(act.split())
    token_score = len(exp_tokens & act_tokens) / max(len(exp_tokens), 1)
    seq_score = SequenceMatcher(None, exp_joined, act_joined).ratio()
    return max(token_score, seq_score)


def match_score(expected: str, actual: str) -> float:
    options = [expected, *MATCH_ALIASES.get(expected, [])]
    return max(base_match_score(option, actual) for option in options)


def load_2019_pc_map() -> dict[int, str]:
    mapping = {}
    pdf_dir = os.path.join(_SCRIPT_DIR, "source_pdfs", "2019_ls")
    pattern = re.compile(r"Election to the\s+(?:\d+\s*-\s*)?(.+?)\s+Parliamentry Constituency", re.I)
    fallback = [row[0] for row in LS_2019]
    for const_no in range(1, 141):
        path = os.path.join(pdf_dir, f"{const_no:03d}.pdf")
        with pdfplumber.open(path) as pdf:
            text = pdf.pages[0].extract_text() or ""
        match = pattern.search(text)
        if match:
            mapping[const_no] = re.sub(r"\s+", " ", match.group(1)).strip().title()
        else:
            mapping[const_no] = fallback[(const_no - 1) // 7]
    return mapping


def table_by_constituency(year: int) -> dict[str, dict[str, tuple[str, str]]]:
    rows = LS_2019 if year == 2019 else LS_2024
    table = {}
    for no, (constituency, udf, ldf, nda) in enumerate(rows, start=1):
        table[compact_constituency(constituency)] = {
            "constituency_no": no,
            "constituency": constituency,
            "UDF": udf,
            "LDF": ldf,
            "NDA": nda,
        }
    return table


def identify_constituency(candidate_meta: list[dict], table: dict[str, dict]) -> tuple[dict, float]:
    scored_rows = []
    for row in table.values():
        alliance_scores = []
        for alliance in ("UDF", "LDF", "NDA"):
            _party, expected_name = row[alliance]
            alliance_scores.append(
                max(match_score(expected_name, candidate["name"]) for candidate in candidate_meta)
            )
        scored_rows.append((sum(alliance_scores) / 3, row))
    return max(scored_rows, key=lambda item: item[0])[1], max(scored_rows, key=lambda item: item[0])[0]


def enrich_year(year: int) -> tuple[int, list[str]]:
    table = table_by_constituency(year)
    data_dir = os.path.join(BASE_DIR, "data", f"{year}_ls")
    total_updates = 0
    warnings = []

    for const_no in range(1, 141):
        path = os.path.join(data_dir, f"{const_no:03d}.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        meta_key = f"candidates_{year}_ls"
        candidate_meta = data[meta_key]
        row, row_score = identify_constituency(candidate_meta, table)
        if row_score < 0.72:
            warnings.append(
                f"{year} {const_no:03d}: low constituency match "
                f"{row['constituency']} ({row_score:.2f})"
            )

        for candidate in candidate_meta:
            candidate["party"] = ""
            candidate["alliance"] = "other"
            candidate["is_major_alliance"] = False
            candidate.pop("source_candidate_name", None)

        used_indexes = set()
        for alliance in ("UDF", "LDF", "NDA"):
            party, expected_name = row[alliance]
            scored = [
                (match_score(expected_name, candidate["name"]), i, candidate)
                for i, candidate in enumerate(candidate_meta)
                if i not in used_indexes
            ]
            score, index, candidate = max(scored, key=lambda item: item[0])
            if score < 0.66:
                warnings.append(
                    f"{year} {const_no:03d} {row['constituency']} {alliance}: "
                    f"expected {expected_name}, best {candidate['name']} ({score:.2f})"
                )
                continue
            candidate["party"] = party
            candidate["alliance"] = alliance
            candidate["is_major_alliance"] = True
            candidate["source"] = f"wikipedia_{year}_kerala_ls_candidates"
            candidate["source_candidate_name"] = expected_name
            used_indexes.add(index)
            total_updates += 1

        data["lok_sabha_constituency"] = row["constituency"]
        data["lok_sabha_constituency_no"] = row["constituency_no"]

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    return total_updates, warnings


def main():
    for year in (2019, 2024):
        updates, warnings = enrich_year(year)
        print(f"{year}: updated {updates} major-alliance candidate records")
        if warnings:
            print(f"{year}: {len(warnings)} warnings")
            for warning in warnings[:50]:
                print("  " + warning)


if __name__ == "__main__":
    main()
