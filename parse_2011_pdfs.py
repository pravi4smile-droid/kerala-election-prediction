#!/usr/bin/env python3
"""Parse Kerala 2011 Form 20 PDFs into data/2011/001.json ... 140.json."""

import json
import os
import re

import pdfplumber

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", "2011")
PDF_DIR = os.path.join(DATA_DIR, "booth_wise")


def clean_num(s: str) -> int:
    digits = re.sub(r"[^0-9]", "", s or "")
    return int(digits) if digits else 0


def clean_booth_label(label: str) -> int | None:
    digits = re.sub(r"[^0-9]", "", label or "")
    return int(digits) if digits else None


def parse_candidate_key(text: str) -> list[str]:
    matches = re.findall(
        r"\b([A-U])\s*-\s*(.*?)(?=,\s*[A-U]\s*-|\n\s*Place\b|$)",
        text or "",
        flags=re.S,
    )
    if not matches:
        return []
    by_letter = {
        letter: re.sub(r"\s+", " ", name).strip(" ,")
        for letter, name in matches
    }
    letters = [chr(ord("A") + i) for i in range(21)]
    names = []
    for letter in letters:
        name = by_letter.get(letter, "")
        if name:
            names.append(name)
    return names


def parse_constituency_name(text: str, const_no: int) -> str:
    m = re.search(r"Election to the\s+(.+?)\s+Assembly Constituency", text or "", re.I)
    if m:
        return f"{const_no:03d}-{m.group(1).strip()}"
    return f"{const_no:03d}"


def parse_table_rows(table, candidate_count: int) -> list[dict]:
    rows = []
    for row in table or []:
        if len(row) < 2 or not row[0] or not row[1]:
            continue
        labels = [x.strip() for x in str(row[0]).splitlines() if x.strip()]
        vote_lines = [x.strip() for x in str(row[1]).splitlines() if x.strip()]
        if not labels or not vote_lines or len(labels) != len(vote_lines):
            continue
        for label, vote_line in zip(labels, vote_lines):
            if not re.fullmatch(r"\d+", label):
                continue
            booth_no = clean_booth_label(label)
            nums = [int(x) for x in re.findall(r"\d+", vote_line)]
            if booth_no is None or len(nums) < candidate_count:
                continue
            rows.append({
                "main": booth_no,
                "is_aux": False,
                "votes": nums[:candidate_count],
            })
    return rows


def booth_summary(booths: list[dict], candidate_count: int) -> dict:
    totals = [
        sum(b["votes"][i] if i < len(b["votes"]) else 0 for b in booths)
        for i in range(candidate_count)
    ]
    return {
        "total_rows": len(booths),
        "main_booths": len({b["main"] for b in booths}),
        "auxiliary_rows": 0,
        "total_votes_in_candidate_columns": sum(totals),
        "candidate_totals": totals,
    }


def parse_pdf(path: str, const_no: int) -> dict:
    with pdfplumber.open(path) as pdf:
        first_text = pdf.pages[0].extract_text() or ""
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        candidates = parse_candidate_key(full_text)
        booths = []
        for page in pdf.pages:
            for table in page.extract_tables():
                booths.extend(parse_table_rows(table, len(candidates)))

    return {
        "const_no": const_no,
        "name": parse_constituency_name(first_text, const_no),
        "source_year": 2011,
        "source_pdf": f"https://www.ceo.kerala.gov.in/pdf/form20/{const_no:03d}.pdf",
        "candidates": candidates,
        "candidates_2011": [
            {
                "index": i,
                "name": name,
                "party": "",
                "alliance": "other",
                "is_major_alliance": False,
                "source": "ceo_kerala_form20_candidate_key",
            }
            for i, name in enumerate(candidates)
        ],
        "booth_summary": booth_summary(booths, len(candidates)),
        "booths": booths,
    }


def main():
    written = 0
    for const_no in range(1, 141):
        path = os.path.join(PDF_DIR, f"{const_no:03d}.pdf")
        if not os.path.exists(path):
            print(f"{const_no:03d}: missing PDF")
            continue
        data = parse_pdf(path, const_no)
        out_path = os.path.join(DATA_DIR, f"{const_no:03d}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"{const_no:03d}: {len(data['candidates'])} candidates, {len(data['booths'])} booths")
        written += 1
    print(f"Wrote {written} files to {DATA_DIR}")


if __name__ == "__main__":
    main()
