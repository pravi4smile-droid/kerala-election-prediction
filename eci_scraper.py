#!/usr/bin/env python3
"""
ECI Live Results Scraper for Kerala 2026
- Phase 1: Fetch 7 statewise pages (statewiseS11{1-7}.htm) → round & margin data for all 140
- Phase 2: Fetch candidateswise pages for active constituencies → per-candidate vote totals
- Uses curl-cffi to bypass Akamai CDN bot protection
"""

import os, json, time, sys, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    print("Installing curl-cffi...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "curl-cffi", "-q"])
    from curl_cffi import requests as cffi_requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Installing beautifulsoup4...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "beautifulsoup4", "-q"])
    from bs4 import BeautifulSoup

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "data")
OUT_FILE    = os.path.join(DATA_DIR, "data_parsing", "live_results.json")
LOG_FILE    = os.path.join(DATA_DIR, "data_parsing", "scraper_log.json")

ECI_BASE    = "https://results.eci.gov.in/ResultAcGenMay2026"
INDEX_URL   = f"{ECI_BASE}/index.htm"
STATE_CODE  = "S11"           # Kerala in ECI May 2026 (confirmed via image path)
STATEWISE_PAGES = 7           # statewiseS111..statewiseS117.htm
MAX_WORKERS = 10              # concurrent requests for candidateswise pages


def make_session() -> cffi_requests.Session:
    s = cffi_requests.Session(impersonate="chrome124")
    s.headers.update({
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
    })
    # Warm up session with index page (gets cookies)
    try:
        s.get(INDEX_URL, timeout=15)
        s.headers.update({"Referer": INDEX_URL})
    except Exception:
        pass
    return s


# ── Phase 1: parse statewise overview pages ───────────────────────────────────

def parse_statewise_page(html: str) -> list[dict]:
    """Extract constituency summary rows from one statewiseS11N.htm page."""
    soup = BeautifulSoup(html, "html.parser")
    main_table = soup.find("table", class_="table-striped")
    if not main_table:
        return []

    results = []
    for tr in main_table.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 2:
            continue

        # Strip nested tables from name/number cells
        c0 = BeautifulSoup(str(tds[0]), "html.parser")
        for t in c0.find_all("table"):
            t.decompose()
        name = c0.get_text(strip=True)
        cno_txt = tds[1].get_text(strip=True)

        if not (name and cno_txt.isdigit()):
            continue
        cno = int(cno_txt)
        if not 1 <= cno <= 140:
            continue

        # Optional extended data (9+ tds → active constituency)
        lead_cand = trail_cand = margin_str = round_str = status = ""
        if len(tds) >= 9:
            for cell_idx, key in [(2, "l"), (4, "t"), (6, "m"), (7, "r"), (8, "s")]:
                cell = BeautifulSoup(str(tds[cell_idx]), "html.parser")
                for t in cell.find_all("table"):
                    t.decompose()
                val = cell.get_text(strip=True)
                if key == "l":   lead_cand  = val
                elif key == "t": trail_cand = val
                elif key == "m": margin_str = val
                elif key == "r": round_str  = val
                elif key == "s": status     = val

        # Parse round "2/16" → current=2, total=16
        cur_round = tot_rounds = 0
        m = re.match(r"(\d+)/(\d+)", round_str)
        if m:
            cur_round, tot_rounds = int(m.group(1)), int(m.group(2))

        margin = 0
        try:
            margin = int(margin_str.replace(",", "")) if margin_str not in ("-", "") else 0
        except ValueError:
            pass

        results.append({
            "const_no":    cno,
            "name":        name,
            "lead_cand":   lead_cand,
            "trail_cand":  trail_cand,
            "margin":      margin,
            "round_str":   round_str,
            "cur_round":   cur_round,
            "tot_rounds":  tot_rounds,
            "status":      status,
            "active":      cur_round > 0,
        })
    return results


def fetch_all_statewise(session: cffi_requests.Session, verbose: bool = True) -> dict[int, dict]:
    """Fetch all 7 statewise pages and return merged dict keyed by const_no."""
    merged: dict[int, dict] = {}
    for page_no in range(1, STATEWISE_PAGES + 1):
        url = f"{ECI_BASE}/statewise{STATE_CODE}{page_no}.htm"
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                if verbose:
                    print(f"  Statewise page {page_no}: HTTP {resp.status_code}")
                continue
            rows = parse_statewise_page(resp.text)
            for row in rows:
                merged[row["const_no"]] = row
            if verbose:
                active = sum(1 for r in rows if r["active"])
                print(f"  Statewise page {page_no}: {len(rows)} constituencies, {active} active")
        except Exception as e:
            if verbose:
                print(f"  Statewise page {page_no}: ERROR {e}")
        time.sleep(0.3)
    return merged


# ── Phase 2: parse individual candidateswise pages ────────────────────────────

def parse_candidateswise(html: str, const_no: int) -> list[dict]:
    """Parse a candidateswise-S11N.htm page → list of candidate dicts."""
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for box in soup.find_all(class_="cand-box"):
        # Name
        h5 = box.find("h5")
        name = h5.get_text(strip=True) if h5 else ""
        # Party
        h6 = box.find("h6")
        party = h6.get_text(strip=True) if h6 else ""
        # Status div: "leading" / "trailing" / "won"
        status_div = box.find(class_="status")
        status = ""
        votes = 0
        margin = 0
        if status_div:
            divs = status_div.find_all("div")
            if divs:
                status = divs[0].get_text(strip=True).lower()
            if len(divs) > 1:
                # "4041 (+ 1181)"
                txt = divs[1].get_text(strip=True)
                m = re.match(r"([\d,]+)", txt.replace("\xa0", " "))
                if m:
                    try:
                        votes = int(m.group(1).replace(",", ""))
                    except ValueError:
                        pass
                mg = re.search(r"([+-]?\s*[\d,]+)\s*\)", txt)
                if mg:
                    try:
                        margin = int(mg.group(1).replace(",", "").replace(" ", ""))
                    except ValueError:
                        pass

        if name and name.upper() != "NOTA":
            candidates.append({
                "name":   name,
                "party":  party,
                "status": status,
                "votes":  votes,
                "margin": margin,
            })
    return candidates


def fetch_candidateswise(session: cffi_requests.Session, const_no: int) -> list[dict] | None:
    url = f"{ECI_BASE}/candidateswise-{STATE_CODE}{const_no}.htm"
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            return parse_candidateswise(resp.text, const_no)
        return None
    except Exception:
        return None


def fetch_all_candidateswise(session: cffi_requests.Session,
                             active_const: list[int],
                             verbose: bool = True) -> dict[int, list[dict]]:
    """Fetch candidateswise pages concurrently for active constituencies."""
    results: dict[int, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_to_no = {pool.submit(fetch_candidateswise, session, no): no
                        for no in active_const}
        for future in as_completed(future_to_no):
            no = future_to_no[future]
            cands = future.result()
            if cands:
                results[no] = cands
            elif verbose:
                pass  # silently skip failed fetches
    if verbose:
        print(f"  Candidateswise: {len(results)}/{len(active_const)} fetched")
    return results


# ── Main scrape function ──────────────────────────────────────────────────────

def scrape_all(const_list: list[int] | None = None, verbose: bool = True) -> dict:
    """
    Full scrape cycle. Returns dict keyed by str(const_no) with:
      {const_no, name, cur_round, tot_rounds, margin, status,
       lead_cand, trail_cand, candidates: [...], fetched_at}
    """
    ts = datetime.now().isoformat()
    if verbose:
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] Starting ECI scrape...")

    session = make_session()

    # Phase 1: get overview (all 140)
    if verbose:
        print("  Phase 1: fetching statewise overview pages...")
    overview = fetch_all_statewise(session, verbose=verbose)

    # Phase 2: fetch per-candidate data for active (or requested) constituencies
    if const_list:
        active_nos = const_list
    else:
        active_nos = [no for no, d in overview.items() if d["active"]]

    if verbose:
        print(f"  Phase 2: fetching {len(active_nos)} candidateswise pages (concurrent)...")
    cand_data = fetch_all_candidateswise(session, active_nos, verbose=verbose)

    # Merge
    merged: dict[str, dict] = {}
    for no, ov in overview.items():
        entry = dict(ov)
        entry["candidates"] = cand_data.get(no, [])
        entry["rounds_completed"] = ov["cur_round"]
        entry["fetched_at"] = ts
        merged[str(no)] = entry

    # Fill in entries for non-overview constituencies (const_list override)
    for no in (const_list or []):
        if str(no) not in merged:
            merged[str(no)] = {
                "const_no": no, "name": "", "cur_round": 0, "tot_rounds": 0,
                "margin": 0, "status": "", "active": False,
                "candidates": cand_data.get(no, []),
                "rounds_completed": 0, "fetched_at": ts,
            }

    # Persist
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    active_count  = sum(1 for v in merged.values() if v.get("active"))
    cand_filled   = sum(1 for v in merged.values() if v.get("candidates"))

    log = {
        "last_run":      ts,
        "total":         len(merged),
        "active":        active_count,
        "with_cand_data": cand_filled,
    }
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f"  Done: {active_count} active, {cand_filled} with candidate data -> {OUT_FILE}")
    return merged


if __name__ == "__main__":
    import sys
    print(f"ECI Scraper  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if len(sys.argv) > 1:
        scrape_all([int(x) for x in sys.argv[1:]])
    else:
        scrape_all()
