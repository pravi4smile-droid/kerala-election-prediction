#!/usr/bin/env python3
"""Download Kerala 2016 Form 20 PDFs into data/2016/booth_wise."""

import os
import time

import requests

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "source_pdfs", "2016")
URLS = [
    "https://www.ceo.kerala.gov.in/pdf/BOOTH_WISE_RESULTS/GE2016/{n:03d}.pdf",
    "https://www.ceo.kerala.gov.in/pdf/BOOTH_WISE_RESULTS/GE2016/{n:03d}.PDF",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/pdf,*/*",
}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ok, failed = 0, []
    session = requests.Session()
    session.headers.update(HEADERS)

    for n in range(1, 141):
        dest = os.path.join(OUT_DIR, f"{n:03d}.pdf")
        if os.path.exists(dest) and os.path.getsize(dest) > 3000:
            print(f"{n:03d}: exists")
            ok += 1
            continue
        downloaded = False
        last_status = ""
        for pattern in URLS:
            try:
                res = session.get(pattern.format(n=n), timeout=30)
                last_status = f"HTTP {res.status_code}"
                if res.status_code == 200 and len(res.content) > 3000:
                    with open(dest, "wb") as f:
                        f.write(res.content)
                    print(f"{n:03d}: {len(res.content)//1024} KB")
                    ok += 1
                    downloaded = True
                    break
            except Exception as exc:
                last_status = str(exc)
        if not downloaded:
            print(f"{n:03d}: {last_status}")
            failed.append(n)
        time.sleep(0.15)

    print(f"Downloaded {ok}/140")
    if failed:
        print("Failed:", failed)


if __name__ == "__main__":
    main()
