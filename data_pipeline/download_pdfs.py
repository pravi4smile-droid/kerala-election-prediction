#!/usr/bin/env python3
"""
Kerala Election 2021 — Booth-wise PDF Downloader
Tries multiple URL patterns to find the working one automatically.

Usage:  python download_pdfs.py
Needs:  pip install requests
"""

import os, sys, time

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "source_pdfs", "2021")
os.makedirs(OUT_DIR, exist_ok=True)

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system(f"{sys.executable} -m pip install requests --quiet")
    import requests

BASE = "https://www.ceo.kerala.gov.in/ceokerala/pdf/BOOTH_WISE_RESULTS/GE2021"

# URL patterns to try (001.pdf confirmed working, 1.pdf as fallback)
PATTERNS = [
    "{base}/{n:03d}.pdf",    # 001.pdf ← CONFIRMED WORKING
    "{base}/{n}.pdf",        # 1.pdf   fallback
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer":    "https://www.ceo.kerala.gov.in/detailedResultsGE2021",
    "Accept":     "application/pdf,*/*",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def probe_pattern():
    """Try constituency 126 (Chathannur) — known to exist — to find working pattern."""
    print("Probing URL patterns using constituency 126 (Chathannur)...")
    for pat in PATTERNS:
        url = pat.format(base=BASE, n=126)
        try:
            r = SESSION.head(url, timeout=10, allow_redirects=True)
            if r.status_code == 200:
                ct = r.headers.get("Content-Type", "")
                if "pdf" in ct.lower() or int(r.headers.get("Content-Length", "0")) > 3000:
                    print(f"  ✓  Working pattern: {url}")
                    return pat
                else:
                    print(f"  ?  {url} → 200 but Content-Type={ct}")
            else:
                print(f"  ✗  {url} → HTTP {r.status_code}")
        except Exception as e:
            print(f"  ✗  {url} → {e}")
    return None


def download_one(pattern, n, dest):
    url = pattern.format(base=BASE, n=n)
    try:
        r = SESSION.get(url, timeout=30)
        if r.status_code == 200 and len(r.content) > 3000:
            with open(dest, "wb") as f:
                f.write(r.content)
            return len(r.content), url
        else:
            return None, f"HTTP {r.status_code}"
    except Exception as e:
        return None, str(e)


def main():
    print("=" * 60)
    print("  Kerala GE2021 Booth-wise PDF Downloader")
    print("=" * 60)

    pattern = probe_pattern()

    if not pattern:
        print("\n⚠  Could not auto-detect a working URL pattern.")
        print("   Please open each of these in your browser and tell me which works:\n")
        for pat in PATTERNS:
            print(f"   {pat.format(base=BASE, n=126)}")
        print("\n   Then paste the working URL here and I will update the script.")
        sys.exit(1)

    print(f"\nDownloading 140 PDFs...")
    print(f"Saving to: {OUT_DIR}\n")

    ok, fail = 0, []
    for i in range(1, 141):
        dest = os.path.join(OUT_DIR, f"{i}.pdf")
        if os.path.exists(dest) and os.path.getsize(dest) > 5000:
            print(f"  [{i:3d}/140] already exists — skip")
            ok += 1
            continue

        size, info = download_one(pattern, i, dest)
        if size:
            print(f"  [{i:3d}/140] ✓  {size//1024} KB")
            ok += 1
        else:
            print(f"  [{i:3d}/140] ✗  {info}")
            fail.append(i)

        time.sleep(0.35)

    print(f"\n{'='*60}")
    print(f"  Done. {ok}/140 downloaded.")
    if fail:
        print(f"  Failed constituencies: {fail}")
        print(f"\n  If all failed, the site needs a browser session.")
        print(f"  Try: python download_pdfs_selenium.py")
    else:
        print("  All 140 PDFs downloaded! Next: python parse_pdfs.py")


if __name__ == "__main__":
    main()
