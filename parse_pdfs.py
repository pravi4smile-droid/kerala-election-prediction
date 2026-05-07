#!/usr/bin/env python3
"""
Step 2 — PDF parser.
Reads each booth-wise PDF and extracts:
  - Constituency name & number
  - Candidate names (columns)
  - Per-row: booth number, is_auxiliary, votes per candidate
Auxiliary booths (1A, 2A …) are tagged and attached to their main booth.
Only main booth numbers count toward "round" boundaries (every 14 mains = 1 round).

Output: data/booth_wise_parsed.json
"""

import os, re, json, sys

try:
    import pdfplumber
except ImportError:
    print("Installing pdfplumber …")
    os.system(f"{sys.executable} -m pip install pdfplumber --quiet")
    import pdfplumber

PDF_DIR  = os.path.join(os.path.dirname(__file__), "data", "booth_wise")
OUT_FILE = os.path.join(os.path.dirname(__file__), "data", "data_parsing", "booth_wise_parsed.json")

# ── helpers ─────────────────────────────────────────────────────────────────

def is_number(s):
    try:
        int(s.replace(",", ""))
        return True
    except ValueError:
        return False

def clean_num(s):
    try:
        return int(s.replace(",", "").strip())
    except:
        return 0

def parse_booth_label(label):
    """
    '1'    -> (1, False)
    '1(A)' -> (1, True)
    '16(A)'-> (16, True)
    Returns (main_booth_no: int, is_aux: bool) or None if not a booth label.
    """
    label = str(label).strip()
    m = re.fullmatch(r"(\d+)(\([Aa]\))?", label)
    if m:
        return int(m.group(1)), bool(m.group(2))
    return None

# ── core parser ──────────────────────────────────────────────────────────────

def parse_pdf(path, const_no):
    result = {
        "const_no":   const_no,
        "name":       "",
        "candidates": [],   # list of strings
        "booths":     [],   # list of booth dicts
    }

    with pdfplumber.open(path) as pdf:
        all_rows = []
        candidate_names = []
        name_found = False

        for page in pdf.pages:
            # 1. extract constituency name from first page
            if not name_found:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    m = re.search(r"(\d+-[A-Z\s()]+Assembly Election)", line)
                    if m:
                        result["name"] = m.group(1).strip()
                        name_found = True
                        break

            # 2. extract table
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                for row in table:
                    clean = [str(c).strip() if c else "" for c in row]
                    # skip totally empty
                    if all(v == "" for v in clean):
                        continue
                    all_rows.append(clean)

        # 3. find header row — look for row whose cells are candidate names
        #    (they sit between fixed columns: Serial, Booth No, ..., Total, Rejected, NOTA, ...)
        header_idx = None
        for i, row in enumerate(all_rows):
            # header rows have many non-numeric, non-empty cells and no numbers
            non_empty = [c for c in row if c]
            if len(non_empty) >= 2 and not any(is_number(c) for c in non_empty[2:]):
                # check if next row is a data row
                if i + 1 < len(all_rows):
                    nxt = all_rows[i + 1]
                    booth_part = parse_booth_label(nxt[1]) if len(nxt) > 1 else None
                    if booth_part:
                        header_idx = i
                        break

        # Extract candidate names from header
        if header_idx is not None:
            hrow = all_rows[header_idx]
            # columns: [Serial, Booth No, cand1, cand2, ..., Total, Rejected, NOTA, Grand Total, Tendered]
            # we want everything from col2 up to but not including 'Total'
            raw_names = []
            for cell in hrow[2:]:
                if cell.lower() in ("total", "no. of valid votes", "valid votes",
                                    "rejected", "nota", "tendered", "grand total", ""):
                    break
                raw_names.append(cell.replace("\n", " ").strip())
            candidate_names = raw_names
        else:
            # fallback — try to infer candidate count from first data row
            candidate_names = []

        result["candidates"] = candidate_names
        n_cands = len(candidate_names)

        # 4. extract data rows
        for row in all_rows[header_idx + 1 if header_idx is not None else 0:]:
            if len(row) < 3:
                continue
            # col 0: serial,  col 1: booth label,  col 2..n_cands+1: votes
            booth_info = parse_booth_label(row[1]) if len(row) > 1 else None
            if booth_info is None:
                continue
            main_no, is_aux = booth_info
            if main_no > 500:
                continue

            # extract vote columns
            vote_cols = row[2:2 + n_cands] if n_cands else row[2:-4]
            votes = [clean_num(v) for v in vote_cols]

            # pad / trim to n_cands
            if n_cands:
                votes = votes[:n_cands] + [0] * max(0, n_cands - len(votes))

            result["booths"].append({
                "main":   main_no,
                "is_aux": is_aux,
                "votes":  votes,
            })

    return result

# ── main ─────────────────────────────────────────────────────────────────────

def main():
    all_data = {}
    pdf_files = sorted(
        [f for f in os.listdir(PDF_DIR) if f.endswith(".pdf")],
        key=lambda f: int(f.replace(".pdf", ""))
    )

    if not pdf_files:
        print(f"No PDFs found in {PDF_DIR}. Run download_pdfs.py first.")
        return

    print(f"Parsing {len(pdf_files)} PDFs …\n")
    for fname in pdf_files:
        no = int(fname.replace(".pdf", ""))
        path = os.path.join(PDF_DIR, fname)
        try:
            data = parse_pdf(path, no)
            all_data[no] = data

            # compute round summary
            main_booths_seen = sorted({b["main"] for b in data["booths"] if not b["is_aux"]})
            total_main = len(main_booths_seen)
            total_rounds = (total_main + 13) // 14

            print(f"  [{no:3d}] {data['name'] or '?':40s}  "
                  f"{len(data['candidates'])} cands  "
                  f"{total_main} main booths  "
                  f"{total_rounds} rounds")
        except Exception as e:
            print(f"  [{no:3d}] ERROR: {e}")
            all_data[no] = {"const_no": no, "name": "", "candidates": [], "booths": [], "error": str(e)}

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Saved to {OUT_FILE}")

if __name__ == "__main__":
    main()
