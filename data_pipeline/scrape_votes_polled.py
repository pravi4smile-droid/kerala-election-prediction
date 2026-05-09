#!/usr/bin/env python3
"""
Fetch total electorate + votes polled per constituency from janavidhi.com
and merge into data/2026/*.json as a "turnout" object.

Source: https://janavidhi.com/pages/votes_polled.html
Data is embedded as a JS DATA array in the page.
"""

import os, json, re, sys

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "curl-cffi", "-q"])
    from curl_cffi import requests as cffi_requests

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR   = os.path.dirname(_SCRIPT_DIR)
DATA_DIR   = os.path.join(BASE_DIR, "data")
DIR_2026   = os.path.join(DATA_DIR, "2026")
SOURCE_URL = "https://janavidhi.com/pages/votes_polled.html"


def fetch_and_parse() -> dict:
    session = cffi_requests.Session(impersonate="chrome124")
    session.headers.update({
        "Accept": "text/html,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
    })

    print(f"Fetching {SOURCE_URL} …")
    resp = session.get(SOURCE_URL, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}")

    html = resp.text
    m = re.search(r"var DATA\s*=\s*(\[.*?\]);", html, re.DOTALL)
    if not m:
        raise RuntimeError("DATA array not found in page")

    raw = m.group(1)
    # Strip JS line comments and trailing commas
    raw = re.sub(r"//[^\n]*", "", raw)
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    # Quote bare JS object keys
    raw = re.sub(r"(\b[a-zA-Z_]\w*)\s*:", r'"\1":', raw)

    records = json.loads(raw)
    print(f"Parsed {len(records)} constituencies.")

    out = {}
    for d in records:
        cid = d["id"]
        elec = d["elec"]
        pct  = d["pct"]
        male   = d["male"]
        female = d["female"]
        out[str(cid)] = {
            "id":             cid,
            "name":           d["name"],
            "district":       d["dist"],
            "electorate":     elec,
            "male":           male,
            "female":         female,
            "turnout_pct":    pct,
            "votes_polled":   round(elec   * pct / 100),
            "male_polled":    round(male   * pct / 100),
            "female_polled":  round(female * pct / 100),
            "confirmed":      d["conf"],
        }
    return out


if __name__ == "__main__":
    data = fetch_and_parse()

    updated = 0
    for cno_str, vp in data.items():
        path = os.path.join(DIR_2026, f"{int(cno_str):03d}.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)
        entry["turnout"] = {
            "electorate":   vp["electorate"],
            "male":         vp["male"],
            "female":       vp["female"],
            "votes_polled": vp["votes_polled"],
            "turnout_pct":  vp["turnout_pct"],
            "confirmed":    vp.get("confirmed", False),
            "male_polled":  vp.get("male_polled", 0),
            "female_polled":vp.get("female_polled", 0),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)
        updated += 1

    print(f"Updated turnout in {updated} files in {DIR_2026}")

    total_elec   = sum(v["electorate"]   for v in data.values())
    total_polled = sum(v["votes_polled"] for v in data.values())
    print(f"Total electorate: {total_elec:,}  |  Estimated polled: {total_polled:,}  |  Avg turnout: {total_polled/total_elec*100:.2f}%")
