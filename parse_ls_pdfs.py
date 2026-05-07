#!/usr/bin/env python3
"""Parse 2019/2024 Lok Sabha LAC-wise Form 20 PDFs into split JSON files."""

import json
import os
import re

import pdfplumber
from pypdf import PdfReader

try:
    import fitz
except ImportError:  # pragma: no cover - only needed when parsing 2024 PDFs.
    fitz = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def clean_num(value) -> int:
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    return int(digits) if digits else 0


def clean_name(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\n", " ")).strip(" ,")


def parse_booth_label(value) -> int | None:
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    return int(digits) if digits else None


def parse_constituency_name(text: str, const_no: int) -> str:
    patterns = [
        r"Name of Assembly/segment\s*\.*\s*(\d+\s*-\s*.+?Assembly Election)",
        r"(\d+\s*-\s*.+?Assembly Segment)\s*-\s*ROUND",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "", flags=re.I)
        if match:
            name = clean_name(match.group(1))
            name = re.sub(r"\s+-\s+ROUND.*$", "", name, flags=re.I)
            if "," in name:
                name = clean_name(name.split(",")[-1])
            return name
    return f"{const_no:03d}"


def parse_electorate(text: str) -> int:
    match = re.search(
        r"Total No\.?\s*(?::\s*of Electors.*?:|of Electors.*?\.*)\s*([0-9,]+)",
        text or "",
        flags=re.I,
    )
    return clean_num(match.group(1)) if match else 0


def candidate_key_2019(text: str) -> tuple[list[str], int | None]:
    matches = re.findall(
        r"\b([A-U])\s*-\s*(.*?)(?=,\s*[A-U]\s*-|\n\s*Place\b|\n\s*Date\b|$)",
        text or "",
        flags=re.S,
    )
    by_letter = {letter: clean_name(name) for letter, name in matches}
    candidates = []
    nota_index = None
    for i in range(21):
        letter = chr(ord("A") + i)
        name = by_letter.get(letter, "")
        if not name:
            continue
        if name.upper() == "NOTA":
            nota_index = i
            continue
        candidates.append(name)
    return candidates, nota_index


def candidate_header_2024(all_rows: list[list[str]]) -> tuple[list[str], int | None]:
    for row in all_rows:
        cells = [clean_name(c) for c in row]
        if len(cells) < 8:
            continue
        names = []
        for cell in cells[2:]:
            low = cell.lower()
            if not cell:
                break
            if low.startswith("total") or "rejected" in low or "nota" in low or "tendered" in low:
                break
            names.append(cell)
        if len(names) >= 3 and not all(re.fullmatch(r"[A-U]", n) for n in names):
            return names, None
    return [], None


def extract_rows_2024(all_rows: list[list[str]], candidate_count: int) -> list[dict]:
    booths = []
    for row in all_rows:
        if len(row) < 2 + candidate_count:
            continue
        booth_no = parse_booth_label(row[1])
        if booth_no is None or booth_no > 500:
            continue
        votes = [clean_num(v) for v in row[2:2 + candidate_count]]
        if not votes or sum(votes) <= 0:
            continue
        booths.append({"main": booth_no, "is_aux": False, "votes": votes})
    return booths


def extract_rows_2024_text(text: str, candidate_count: int) -> list[dict]:
    booths = []
    seen = set()
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or not re.match(r"^\d", stripped):
            continue
        nums_text = re.findall(r"\d+", stripped)
        if len(nums_text) < candidate_count + 1:
            continue

        first = nums_text[0]
        if len(first) >= 4 and len(first) % 2 == 0 and first[:len(first)//2] == first[len(first)//2:]:
            booth_no = int(first[:len(first)//2])
            vote_start = 1
        else:
            if len(nums_text) < candidate_count + 2:
                continue
            booth_no = int(nums_text[1])
            vote_start = 2

        if booth_no <= 0 or booth_no > 500 or booth_no in seen:
            continue
        votes = [int(x) for x in nums_text[vote_start:vote_start + candidate_count]]
        if len(votes) != candidate_count or sum(votes) <= 0:
            continue
        booths.append({"main": booth_no, "is_aux": False, "votes": votes})
        seen.add(booth_no)
    return booths


def first_numeric_row_2024(words: list[tuple]) -> tuple[float, list[tuple[float, int]]]:
    rows: dict[float, list[tuple[float, int]]] = {}
    for word in words:
        x0, y0, _x1, _y1, text, *_rest = word
        if not re.fullmatch(r"\d+", str(text)):
            continue
        y_key = round(float(y0), 1)
        rows.setdefault(y_key, []).append((float(x0), int(text)))

    for y_key in sorted(rows):
        nums = sorted(rows[y_key])
        values = [value for _x, value in nums]
        if len(values) >= 10 and values[0] == 1 and values[1] == 1:
            return y_key, nums
    return 0.0, []


def infer_2024_candidate_count(first_row: list[tuple[float, int]]) -> int:
    values = [value for _x, value in first_row]
    for count in range(3, max(3, len(values) - 6)):
        valid_total_index = 2 + count
        if valid_total_index >= len(values):
            break
        if sum(values[2:valid_total_index]) == values[valid_total_index]:
            return count
    return 0


def candidate_header_2024_words(words: list[tuple], candidate_count: int) -> list[str]:
    if not candidate_count:
        return []
    data_y, first_row = first_numeric_row_2024(words)
    if not first_row:
        return []

    centers = [x for x, _value in first_row[2:2 + candidate_count]]
    if not centers:
        return []

    fixed_words = {
        "serial", "no", "of", "polling", "station", "valid", "votes", "cast",
        "in", "favour", "total", "rejected", "nota", "tendered", "for",
    }
    max_gap = max(18.0, min(
        (centers[i + 1] - centers[i]) / 2 for i in range(len(centers) - 1)
    ) + 8.0) if len(centers) > 1 else 60.0
    columns: list[list[tuple[float, float, str]]] = [[] for _ in centers]

    for word in words:
        x0, y0, _x1, _y1, text, *_rest = word
        token = clean_name(str(text))
        if not token or re.fullmatch(r"\d+", token):
            continue
        if token.lower().strip(".") in fixed_words:
            continue
        if not (data_y - 70 <= float(y0) < data_y - 3):
            continue
        nearest_index = min(range(len(centers)), key=lambda i: abs(float(x0) - centers[i]))
        if abs(float(x0) - centers[nearest_index]) <= max_gap:
            columns[nearest_index].append((float(y0), float(x0), token))

    candidates = []
    for column in columns:
        parts = [text for _y, _x, text in sorted(column)]
        candidates.append(clean_name(" ".join(parts)))
    return candidates


def parse_pdf_2024_fast(path: str) -> tuple[str, list[str], list[dict]]:
    if fitz is None:
        raise RuntimeError("PyMuPDF is required to parse 2024 LS PDFs")
    with fitz.open(path) as doc:
        first_text = doc[0].get_text()
        first_words = doc[0].get_text("words")
        all_words = [page.get_text("words") for page in doc]

    with pdfplumber.open(path) as pdf:
        first_rows = []
        for table in pdf.pages[0].extract_tables():
            for row in table or []:
                first_rows.append([str(c).strip() if c else "" for c in row])
    candidates, _nota_index = candidate_header_2024(first_rows)

    _data_y, first_row = first_numeric_row_2024(first_words)
    if not candidates:
        candidate_count = infer_2024_candidate_count(first_row)
        candidates = candidate_header_2024_words(first_words, candidate_count)
    booths = extract_rows_2024_words(all_words, len(candidates))
    return first_text, candidates, booths


def extract_rows_2024_words(pages_words: list[list[tuple]], candidate_count: int) -> list[dict]:
    booths = []
    seen = set()
    if not candidate_count:
        return booths

    for words in pages_words:
        rows: dict[float, list[tuple[float, int]]] = {}
        for word in words:
            x0, y0, _x1, _y1, text, *_rest = word
            if not re.fullmatch(r"\d+", str(text)):
                continue
            y_key = round(float(y0), 1)
            rows.setdefault(y_key, []).append((float(x0), int(text)))

        for y_key in sorted(rows):
            nums = sorted(rows[y_key])
            values = [value for _x, value in nums]
            if len(values) < candidate_count + 5:
                continue
            booth_no = values[1] if len(values) > 1 else 0
            if booth_no <= 0 or booth_no > 500 or booth_no in seen:
                continue
            votes = values[2:2 + candidate_count]
            valid_total_index = 2 + candidate_count
            if valid_total_index < len(values) and sum(votes) != values[valid_total_index]:
                continue
            if sum(votes) <= 0:
                continue
            booths.append({"main": booth_no, "is_aux": False, "votes": votes})
            seen.add(booth_no)
    return booths


def extract_rows_2019(tables, candidate_count: int) -> list[dict]:
    booths = []
    for table in tables:
        for row in table or []:
            if len(row) < 2 or not row[0] or not row[1]:
                continue
            labels = [x.strip() for x in str(row[0]).splitlines() if x.strip()]
            vote_lines = [
                x.strip()
                for x in str(row[1]).splitlines()
                if x.strip() and re.search(r"\d", x)
            ]
            if not labels or len(labels) != len(vote_lines):
                continue
            for label, vote_line in zip(labels, vote_lines):
                booth_no = parse_booth_label(label)
                if booth_no is None or booth_no > 500:
                    continue
                nums = [int(x) for x in re.findall(r"\d+", vote_line)]
                if len(nums) < candidate_count:
                    continue
                votes = nums[:candidate_count]
                if sum(votes) <= 0:
                    continue
                booths.append({"main": booth_no, "is_aux": False, "votes": votes})
    return booths


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


def parse_pdf(path: str, const_no: int, year: int) -> dict:
    if year == 2024:
        first_text, candidates, booths = parse_pdf_2024_fast(path)
        nota_index = None
    else:
        with pdfplumber.open(path) as pdf:
            first_text = pdf.pages[0].extract_text() or ""
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            all_tables = []
            for page in pdf.pages:
                for table in page.extract_tables():
                    all_tables.append(table)

        candidates, nota_index = candidate_key_2019(full_text)
        booths = extract_rows_2019(all_tables, len(candidates))

    source_pdf_no = str(const_no) if year == 2024 and const_no == 90 else f"{const_no:03d}"

    return {
        "const_no": const_no,
        "name": parse_constituency_name(first_text, const_no),
        "source_year": year,
        "election_type": "lok_sabha",
        "source_pdf": f"https://www.ceo.kerala.gov.in/ceokerala/pdf/GE-{year}/LAC_WISE_RESULTS/{source_pdf_no}.pdf",
        "electorate": parse_electorate(first_text),
        "nota_index": nota_index,
        "candidates": candidates,
        f"candidates_{year}_ls": [
            {
                "index": i,
                "name": name,
                "party": "",
                "alliance": "other",
                "is_major_alliance": False,
                "source": f"ceo_kerala_ge_{year}_lac_wise_form20",
            }
            for i, name in enumerate(candidates)
        ],
        "booth_summary": booth_summary(booths, len(candidates)),
        "booths": booths,
    }


def parse_year(year: int):
    data_dir = os.path.join(BASE_DIR, "data", f"{year}_ls")
    pdf_dir = os.path.join(data_dir, "booth_wise")
    written = 0
    for const_no in range(1, 141):
        path = os.path.join(pdf_dir, f"{const_no:03d}.pdf")
        if not os.path.exists(path):
            print(f"{year} {const_no:03d}: missing PDF")
            continue
        data = parse_pdf(path, const_no, year)
        out_path = os.path.join(data_dir, f"{const_no:03d}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(
            f"{year} {const_no:03d}: {len(data['candidates'])} candidates, "
            f"{data['booth_summary']['main_booths']} booths, "
            f"{data['booth_summary']['total_votes_in_candidate_columns']} votes"
        )
        written += 1
    print(f"{year}: wrote {written} files to {data_dir}")


def main():
    for year in (2019, 2024):
        parse_year(year)


if __name__ == "__main__":
    main()
