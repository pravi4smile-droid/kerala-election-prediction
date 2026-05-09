#!/usr/bin/env python3
"""
Scrape per-round candidate votes from ECI Kerala 2026 result pages.

URL pattern:  .../RoundwiseS11{CONST_NO}.htm?ac=1
Saves:        data/round_results.json
Then run:     python split_2026_round_results.py

Each constituency entry:
  {
    "name": "...",
    "candidates": ["NAME A", ...],
    "parties":    ["PARTY A", ...],
    "rounds": [
      {"round": 1, "increment": [v0, v1, ...], "cumulative": [v0, v1, ...]},
      ...
    ],
    "total":      [final_v0, final_v1, ...],
    "fetched_at": "ISO-datetime"
  }
"""

import os, json, time, sys, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "curl-cffi", "-q"])
    from curl_cffi import requests as cffi_requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "beautifulsoup4", "-q"])
    from bs4 import BeautifulSoup

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR   = os.path.dirname(_SCRIPT_DIR)
DATA_DIR   = os.path.join(BASE_DIR, "data")
OUT_FILE   = os.path.join(DATA_DIR, "data_parsing", "round_results.json")
LIVE_FILE  = os.path.join(DATA_DIR, "live_results.json")

ECI_BASE   = "https://results.eci.gov.in/ResultAcGenMay2026"
INDEX_URL  = f"{ECI_BASE}/index.htm"
STATE_CODE = "S11"
MAX_WORKERS = 12


def make_session() -> cffi_requests.Session:
    s = cffi_requests.Session(impersonate="chrome124")
    s.headers.update({
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
    })
    try:
        s.get(INDEX_URL, timeout=15)
        s.headers.update({"Referer": INDEX_URL})
    except Exception:
        pass
    return s


def parse_roundwise(html: str) -> dict | None:
    """
    Parse ECI RoundwiseS11N.htm page.

    Page layout: one <table> per round, each table has rows for each candidate:
      Candidate | Party | Votes from Prev Rounds | Current Round | Total
    """
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return None

    candidates = None
    parties    = None
    rounds     = []

    for tbl in tables:
        # Check header row for "Round N (EVM Votes)" title nearby
        rows = tbl.find_all("tr")
        if len(rows) < 2:
            continue

        # Skip tables that don't look like round data
        first_text = tbl.get_text(" ", strip=True)
        if not re.search(r"round\s+\d+", first_text, re.IGNORECASE):
            continue

        # Find round number from the page text near this table
        rnum_match = re.search(r"Round\s+(\d+)", first_text, re.IGNORECASE)
        if not rnum_match:
            continue
        rnum = int(rnum_match.group(1))

        # Skip postal ballot tables (EVM tables have "EVM Votes" in heading)
        if "postal" in first_text[:80].lower():
            continue

        # Parse candidate rows
        cand_names = []
        cand_parties = []
        cand_prev = []
        cand_curr = []
        cand_total = []

        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue
            texts = [c.get_text(" ", strip=True).replace(",", "") for c in cells]

            # Skip header-like rows (containing "Candidate" or "Party" keywords)
            if any(kw in texts[0].lower() for kw in ["candidate", "party", "round"]):
                continue
            # Skip NOTA row
            if "nota" in texts[0].lower():
                continue
            # Need a name and numeric vote columns
            if not texts[0].strip():
                continue

            # Try to parse last 3 numeric columns as prev/curr/total
            nums = []
            for t in reversed(texts[1:]):
                t_clean = t.strip()
                if re.match(r"^\d+$", t_clean):
                    nums.append(int(t_clean))
                    if len(nums) == 3:
                        break
                else:
                    break

            if len(nums) < 3:
                continue

            total_v, curr_v, prev_v = nums[0], nums[1], nums[2]

            # Candidate name is texts[0], party is texts[1] (if exists)
            name = texts[0].strip()
            party = texts[1].strip() if len(texts) > 1 else ""

            cand_names.append(name)
            cand_parties.append(party)
            cand_prev.append(prev_v)
            cand_curr.append(curr_v)
            cand_total.append(total_v)

        if not cand_names:
            continue

        # First round: lock in candidate order
        if candidates is None:
            candidates = cand_names
            parties    = cand_parties
        else:
            # Align to established candidate order (names may reorder in later rounds)
            name_idx = {n: i for i, n in enumerate(cand_names)}
            aligned_curr  = []
            aligned_total = []
            for cn in candidates:
                idx = name_idx.get(cn)
                if idx is not None:
                    aligned_curr.append(cand_curr[idx])
                    aligned_total.append(cand_total[idx])
                else:
                    aligned_curr.append(0)
                    aligned_total.append(0)
            cand_curr  = aligned_curr
            cand_total = aligned_total

        rounds.append({
            "round":      rnum,
            "increment":  cand_curr,
            "cumulative": cand_total,
        })

    if not rounds or candidates is None:
        return None

    # Sort rounds in order
    rounds.sort(key=lambda r: r["round"])
    total = rounds[-1]["cumulative"]

    return {
        "candidates": candidates,
        "parties":    parties,
        "rounds":     rounds,
        "total":      total,
    }


def fetch_one(session: cffi_requests.Session, const_no: int) -> tuple[int, dict | None]:
    url = f"{ECI_BASE}/Roundwise{STATE_CODE}{const_no}.htm?ac=1"
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            return const_no, None
        result = parse_roundwise(resp.text)
        return const_no, result
    except Exception:
        return const_no, None


def run(const_nos: list[int] | None = None, force: bool = False):
    ts = datetime.now().isoformat()

    # Determine which constituencies to fetch
    if const_nos is None:
        if os.path.exists(LIVE_FILE):
            with open(LIVE_FILE, encoding="utf-8") as f:
                live = json.load(f)
            const_nos = [int(k) for k in live.keys()]
        else:
            const_nos = list(range(1, 141))

    # Load existing results to merge / skip already-fetched
    existing = {}
    if os.path.exists(OUT_FILE) and not force:
        with open(OUT_FILE, encoding="utf-8") as f:
            existing = json.load(f)

    # Skip ones we already have (unless force)
    to_fetch = [no for no in const_nos if force or str(no) not in existing]
    already  = len(const_nos) - len(to_fetch)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Round-wise scrape: "
          f"{len(to_fetch)} to fetch, {already} already cached.")

    # Load live_results for constituency names
    live_names = {}
    if os.path.exists(LIVE_FILE):
        with open(LIVE_FILE, encoding="utf-8") as f:
            for k, v in json.load(f).items():
                live_names[int(k)] = v.get("name", "")

    session = make_session()
    results = dict(existing)

    ok_count = fail_count = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_one, session, no): no for no in to_fetch}
        for i, future in enumerate(as_completed(futures), 1):
            no, data = future.result()
            if data:
                data["name"] = live_names.get(no, "")
                data["fetched_at"] = ts
                results[str(no)] = data
                ok_count += 1
                n_rounds = len(data["rounds"])
                n_cands  = len(data["candidates"])
                print(f"  [{i:3d}/{len(to_fetch)}] #{no:>3} {data['name']:<22} "
                      f"{n_cands} cands × {n_rounds} rounds")
            else:
                fail_count += 1
                print(f"  [{i:3d}/{len(to_fetch)}] #{no:>3}  — no data")

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n  Fetched OK: {ok_count}  |  Failed: {fail_count}  |  Cached total: {len(results)}")
    print(f"  Saved -> {OUT_FILE}")
    return results


if __name__ == "__main__":
    args = sys.argv[1:]
    force = "--force" in args
    nos = [int(x) for x in args if x.isdigit()] or None
    run(nos, force=force)
