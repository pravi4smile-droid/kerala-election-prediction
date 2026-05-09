#!/usr/bin/env python3
"""Download 2019 and 2024 Lok Sabha LAC-wise Form 20 PDFs."""

import os
import time

import requests

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_SCRIPT_DIR)
YEARS = {
    2019: "https://www.ceo.kerala.gov.in/ceokerala/pdf/GE-2019/LAC_WISE_RESULTS/{n:03d}.pdf",
    2024: "https://www.ceo.kerala.gov.in/ceokerala/pdf/GE-2024/LAC_WISE_RESULTS/{n:03d}.pdf",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/pdf,*/*",
}


def download_year(year: int) -> tuple[int, list[int]]:
    out_dir = os.path.join(_SCRIPT_DIR, "source_pdfs", f"{year}_ls")
    os.makedirs(out_dir, exist_ok=True)
    ok, failed = 0, []
    session = requests.Session()
    session.headers.update(HEADERS)

    for n in range(1, 141):
        dest = os.path.join(out_dir, f"{n:03d}.pdf")
        if os.path.exists(dest) and os.path.getsize(dest) > 3000:
            print(f"{year} {n:03d}: exists")
            ok += 1
            continue
        try:
            res = session.get(YEARS[year].format(n=n), timeout=40)
            if res.status_code == 200 and res.content.startswith(b"%PDF") and len(res.content) > 3000:
                with open(dest, "wb") as f:
                    f.write(res.content)
                print(f"{year} {n:03d}: {len(res.content)//1024} KB")
                ok += 1
            else:
                print(f"{year} {n:03d}: HTTP {res.status_code}, {len(res.content)} bytes")
                failed.append(n)
        except Exception as exc:
            print(f"{year} {n:03d}: {exc}")
            failed.append(n)
        time.sleep(0.08)
    return ok, failed


def main():
    for year in (2019, 2024):
        ok, failed = download_year(year)
        print(f"{year}: downloaded {ok}/140")
        if failed:
            print(f"{year}: failed {failed}")


if __name__ == "__main__":
    main()
