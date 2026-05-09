#!/usr/bin/env python3
"""Parse selected Kerala Assembly by-election Form 20 PDFs into JSON files."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    local_deps = Path(__file__).resolve().parent / ".deps_pypdf"
    if local_deps.exists():
        sys.path.insert(0, str(local_deps))
    from pypdf import PdfReader


_SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = _SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"
SOURCE_PDF_DIR = _SCRIPT_DIR / "source_pdfs"


BY_ELECTIONS = [
    {
        "year": 2024,
        "dir_name": "2024_be",
        "const_no": 56,
        "name": "56-PALAKKAD Assembly Election",
        "electorate": 195021,
        "election_type": "assembly_by_election",
        "source_pdf": "https://www.ceo.kerala.gov.in/ceokerala/pdf/BYEELECTION2024/results/palakkad.pdf",
        "party_source_url": "https://results.eci.gov.in/ResultAcByeNov2024/ConstituencywiseS1156.htm",
        "candidates": [
            {"name": "C KRISHNAKUMAR", "party": "BJP", "alliance": "nda", "actual_votes": 39549},
            {"name": "RAHUL MAMKOOTATHIL", "party": "INC", "alliance": "udf", "actual_votes": 58389},
            {"name": "M. RAJESH", "party": "BSP", "alliance": "other", "actual_votes": 561},
            {"name": "ALATHUR RAHUL", "party": "IND", "alliance": "other", "actual_votes": 183},
            {"name": "R RAHUL", "party": "IND", "alliance": "other", "actual_votes": 157},
            {"name": "MANALAZHI N.S.K.PURAM SASIKUMAR", "party": "IND", "alliance": "other", "actual_votes": 98},
            {"name": "SELVAN S", "party": "IND", "alliance": "other", "actual_votes": 141},
            {"name": "B. SHAMEER", "party": "IND", "alliance": "other", "actual_votes": 246},
            {"name": "DR. P. SARIN", "party": "IND", "alliance": "ldf", "actual_votes": 37293},
            {"name": "ERUPPASSERY SIDDIK", "party": "IND", "alliance": "other", "actual_votes": 241},
        ],
    },
    {
        "year": 2024,
        "dir_name": "2024_be",
        "const_no": 61,
        "name": "61-CHELAKKARA (SC) Assembly Election",
        "electorate": 213418,
        "election_type": "assembly_by_election",
        "source_pdf": "https://www.ceo.kerala.gov.in/ceokerala/pdf/BYEELECTION2024/results/chelakkara.pdf",
        "party_source_url": "https://results.eci.gov.in/ResultAcByeNov2024/ConstituencywiseS1161.htm",
        "candidates": [
            {"name": "U R PRADEEP", "party": "CPI(M)", "alliance": "ldf", "actual_votes": 64827},
            {"name": "K BALAKRISHNAN", "party": "BJP", "alliance": "nda", "actual_votes": 33609},
            {"name": "RAMYA HARIDAS", "party": "INC", "alliance": "udf", "actual_votes": 52626},
            {"name": "LINDESH", "party": "IND", "alliance": "other", "actual_votes": 240},
            {"name": "K B SUDHEER", "party": "IND", "alliance": "other", "actual_votes": 3920},
            {"name": "N K HARIDASAN", "party": "IND", "alliance": "other", "actual_votes": 170},
        ],
    },
    *[
        {
            "year": 2024,
            "dir_name": "2024_be_ls",
            "const_no": const_no,
            "name": name,
            "electorate": electorate,
            "election_type": "lok_sabha_by_election",
            "candidates_key": "candidates_2024_ls",
            "source_pdf": f"https://www.ceo.kerala.gov.in/ceokerala/pdf/BYEELECTION2024/results/{slug}.pdf",
            "party_source_url": "https://results.eci.gov.in/ResultPcByeNov2024/ConstituencywiseS114.htm",
            "candidates": [
                {"name": "NAVYA HARIDAS", "party": "BJP", "alliance": "nda", "actual_votes": 0},
                {"name": "PRIYANKA GANDHI VADRA", "party": "INC", "alliance": "udf", "actual_votes": 0},
                {"name": "SATHYAN MOKERI", "party": "CPI", "alliance": "ldf", "actual_votes": 0},
                {"name": "GOPAL SWAROOP GANDHI", "party": "KMSP", "alliance": "other", "actual_votes": 0},
                {"name": "JAYENDRA K RATHOD", "party": "RTORP", "alliance": "other", "actual_votes": 0},
                {"name": "SHAIK JALEEL", "party": "NVP", "alliance": "other", "actual_votes": 0},
                {"name": "DUGGIRALA NAGESWARA RAO", "party": "JJSP", "alliance": "other", "actual_votes": 0},
                {"name": "A SEETHA", "party": "BDP", "alliance": "other", "actual_votes": 0},
                {"name": "AJITHKUMAR", "party": "IND", "alliance": "other", "actual_votes": 0},
                {"name": "ISMAIL ZABI ULLAH", "party": "IND", "alliance": "other", "actual_votes": 0},
                {"name": "A NOOR MUHAMAD", "party": "IND", "alliance": "other", "actual_votes": 0},
                {"name": "DR K PADMARAJAN", "party": "IND", "alliance": "other", "actual_votes": 0},
                {"name": "R RAJAN", "party": "IND", "alliance": "other", "actual_votes": 0},
                {"name": "RUKMINI", "party": "IND", "alliance": "other", "actual_votes": 0},
                {"name": "SANTHOSH PULICKAL", "party": "IND", "alliance": "other", "actual_votes": 0},
                {"name": "SONHU SINGH YADAV", "party": "IND", "alliance": "other", "actual_votes": 0},
            ],
        }
        for const_no, name, electorate, slug in [
            (17, "17-MANANTHAVADY (ST) Assembly Election", 203205, "mananthavady"),
            (18, "18-SULTHANBATHERY (ST) Assembly Election", 226863, "sulthanbathery"),
            (19, "19-KALPETTA Assembly Election", 206887, "kalpetta"),
            (32, "32-THIRUVAMBADY Assembly Election", 193797, "thiruvambady"),
            (34, "34-ERANAD Assembly Election", 188675, "eranad"),
            (35, "35-NILAMBUR Assembly Election", 228771, "nilambur"),
            (36, "36-WANDOOR (SC) Assembly Election", 234497, "wandoor"),
        ]
    ],
    {
        "year": 2025,
        "dir_name": "2025_be",
        "const_no": 35,
        "name": "35-NILAMBUR Assembly Election",
        "electorate": 232381,
        "source_pdf": "https://www.ceo.kerala.gov.in/ceokerala/pdf/BYEELECTION2025/Form20-S11_ac_no35_24-06-2025_1750753472.pdf",
        "election_type": "assembly_by_election",
        "party_source_url": "https://results.eci.gov.in/AcResultByeJun2025/candidateswise-S1135.htm",
        "candidates": [
            {"name": "ADV. MOHAN GEORGE", "party": "BJP", "alliance": "nda", "actual_votes": 8648},
            {"name": "ARYADAN SHOUKATH", "party": "INC", "alliance": "udf", "actual_votes": 77737},
            {"name": "M. SWARAJ", "party": "CPI(M)", "alliance": "ldf", "actual_votes": 66660},
            {"name": "ADV. SADIK NADUTHODI", "party": "SDPI", "alliance": "other", "actual_votes": 2075},
            {"name": "P.V. ANVAR", "party": "IND", "alliance": "other", "actual_votes": 19760},
            {"name": "N. JAYARAJAN", "party": "IND", "alliance": "other", "actual_votes": 52},
            {"name": "P. RADHAKRISHNAN NAMBOOTHIRIPPAD", "party": "IND", "alliance": "other", "actual_votes": 43},
            {"name": "VIJAYAN", "party": "IND", "alliance": "other", "actual_votes": 85},
            {"name": "SADEESH KUMAR. G", "party": "IND", "alliance": "other", "actual_votes": 114},
            {"name": "HARINARAYANAN", "party": "IND", "alliance": "other", "actual_votes": 185},
        ],
    }
]


def clean_int(value: str | int | None) -> int:
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    return int(digits) if digits else 0


def parse_booth_token(value: str) -> tuple[int, bool]:
    match = re.match(r"^(\d+)([A-Z]+)?$", value.strip(), flags=re.I)
    if not match:
        return 0, False
    return int(match.group(1)), bool(match.group(2))


def pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_booth_rows(text: str, candidate_count: int) -> list[dict]:
    booths = []
    seen = set()
    needed = candidate_count + 4
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not re.match(r"^\d", line):
            continue
        parts = line.split()
        row_prefix_len = 2
        serial_no = clean_int(parts[0]) if parts else 0
        booth_token = parts[1] if len(parts) > 1 else ""
        booth_no, is_aux = parse_booth_token(booth_token)
        if parts and re.match(r"^\d{2,6}[A-Z]+$", parts[0], flags=re.I):
            digits = re.match(r"^(\d+)", parts[0]).group(1)
            split_at = 3 if len(digits) > 4 else 2
            serial_no = int(parts[0][:split_at])
            booth_no, is_aux = parse_booth_token(parts[0][split_at:])
            row_prefix_len = 1
        elif not booth_no and parts:
            stuck = re.match(r"^(\d{1,3})(\d{1,3}[A-Z]+)$", parts[0], flags=re.I)
            if stuck:
                digits = re.match(r"^(\d+)", parts[0]).group(1)
                split_at = 3 if len(digits) > 4 else 2
                serial_no = int(parts[0][:split_at])
                booth_no, is_aux = parse_booth_token(parts[0][split_at:])
                row_prefix_len = 1
        nums = [clean_int(n) for n in parts[row_prefix_len:]]
        if len(nums) < needed:
            continue
        if not (1 <= serial_no <= 500 and 1 <= booth_no <= 500):
            continue
        votes = nums[:candidate_count]
        valid_total, rejected, nota, total = nums[candidate_count:candidate_count + 4]
        tendered = nums[candidate_count + 4] if len(nums) > candidate_count + 4 else 0
        if sum(votes) != valid_total or valid_total + rejected + nota != total:
            continue
        key = (serial_no, booth_no)
        if key in seen:
            continue
        seen.add(key)
        booths.append({
            "serial_no": serial_no,
            "main": booth_no,
            "is_aux": is_aux,
            "votes": votes,
            "valid_total": valid_total,
            "rejected": rejected,
            "nota": nota,
            "total": total,
            "tendered": tendered,
        })
    return booths


def parse_summary_line(text: str, label_pattern: str, candidate_count: int) -> dict:
    if re.search(rf"{label_pattern}\s*\(To be filled", text, flags=re.I):
        return {
            "candidate_totals": [0 for _ in range(candidate_count)],
            "valid_total": 0,
            "rejected": 0,
            "nota": 0,
            "total": 0,
            "tendered": 0,
        }
    match = re.search(
        rf"{label_pattern}\s+((?:\d+\s+){{{candidate_count + 5}}})",
        text,
        flags=re.I,
    )
    if not match:
        return {}
    nums = [clean_int(n) for n in re.findall(r"\d+", match.group(1))]
    return {
        "candidate_totals": nums[:candidate_count],
        "valid_total": nums[candidate_count],
        "rejected": nums[candidate_count + 1],
        "nota": nums[candidate_count + 2],
        "total": nums[candidate_count + 3],
        "tendered": nums[candidate_count + 4],
    }


def booth_summary(booths: list[dict], candidate_count: int) -> dict:
    totals = [
        sum(b["votes"][i] if i < len(b["votes"]) else 0 for b in booths)
        for i in range(candidate_count)
    ]
    return {
        "total_rows": len(booths),
        "main_booths": len({b["main"] for b in booths}),
        "auxiliary_rows": sum(1 for b in booths if b.get("is_aux")),
        "total_votes_in_candidate_columns": sum(totals),
        "candidate_totals": totals,
        "nota": sum(b.get("nota", 0) for b in booths),
        "rejected": sum(b.get("rejected", 0) for b in booths),
        "total_polled": sum(b.get("total", 0) for b in booths),
    }


def parse_one(config: dict) -> dict:
    year = config["year"]
    candidate_count = len(config["candidates"])
    path = SOURCE_PDF_DIR / config["dir_name"] / f"{config['const_no']:03d}.pdf"
    text = pdf_text(path)
    booths = parse_booth_rows(text, candidate_count)
    evm_summary = parse_summary_line(text, r"Total\s+EVM\s+Votes", candidate_count)
    postal_summary = parse_summary_line(text, r"Total\s+Postal\s+Ballot\s+Votes", candidate_count)
    final_summary = parse_summary_line(text, r"Total\s+Votes\s+Polled", candidate_count)
    calculated = booth_summary(booths, candidate_count)
    if evm_summary and calculated["candidate_totals"] != evm_summary["candidate_totals"]:
        raise ValueError(f"{path}: booth totals do not match Total EVM Votes")

    cands_key = config.get("candidates_key", f"candidates_{year}")
    candidates_meta = []
    final_totals = final_summary.get("candidate_totals", [])
    for index, cand in enumerate(config["candidates"]):
        actual_votes = final_totals[index] if index < len(final_totals) else cand.get("actual_votes", 0)
        candidates_meta.append({
            "index": index,
            "name": cand["name"],
            "party": cand["party"],
            "alliance": cand["alliance"],
            "is_major_alliance": cand["alliance"] in ("ldf", "udf", "nda"),
            "source": "ECI by-election result page and CEO Kerala Form 20",
            f"actual_votes_{year}": actual_votes,
            f"actual_votes_{year}_ls": actual_votes if cands_key.endswith("_ls") else None,
            f"vote_pct_{year}": f"{(actual_votes / final_summary['valid_total'] * 100):.2f}" if final_summary else "",
            "source_url": config["party_source_url"],
        })
        if not cands_key.endswith("_ls"):
            candidates_meta[-1].pop(f"actual_votes_{year}_ls")

    return {
        "const_no": config["const_no"],
        "name": config["name"],
        "source_year": year,
        "election_type": config.get("election_type", "assembly_by_election"),
        "source_pdf": config["source_pdf"],
        "party_source_url": config["party_source_url"],
        "electorate": config.get("electorate", 0),
        "nota_index": candidate_count,
        "candidates": [c["name"] for c in config["candidates"]],
        cands_key: candidates_meta,
        "booth_summary": calculated,
        "evm_summary": evm_summary,
        "postal_ballot_summary": postal_summary,
        "final_summary": final_summary,
        "booths": booths,
    }


def main() -> None:
    for config in BY_ELECTIONS:
        data = parse_one(config)
        out_dir = DATA_DIR / config["dir_name"]
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{config['const_no']:03d}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(
            f"{config['dir_name']}/{config['const_no']:03d}: "
            f"{len(data['booths'])} booths, "
            f"{data['booth_summary']['total_polled']} EVM votes, "
            f"{data['final_summary'].get('total', 0)} final votes"
        )


if __name__ == "__main__":
    main()
