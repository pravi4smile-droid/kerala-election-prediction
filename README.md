# Kerala Election Live Predictor

Predict assembly election winners in real time as booth-wise counts come in.

## Setup

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Download all 140 PDFs from CEO Kerala website
python download_pdfs.py

# 3. Parse PDFs into the legacy combined JSON
python parse_pdfs.py

# 4. Split and enrich 2021 booth data for issue analysis
python split_2021_booth_data.py

# 5. Optional: enrich 2021 candidates from public Kerala Assembly result pages
python enrich_2021_candidate_parties.py

# 6. Split 2026 ECI round results and enrich with candidate metadata
python split_2026_round_results.py
python enrich_2026_data.py

# 7. Build 2011 booth-wise history
python download_2011_pdfs.py
python parse_2011_pdfs.py
python enrich_2011_candidate_parties.py

# 8. Build 2016 booth-wise history
python download_2016_pdfs.py
python parse_2016_pdfs.py
python enrich_2016_candidate_parties.py
```

`split_2021_booth_data.py` creates `data/2021/001.json` through
`data/2021/140.json`. Each file keeps the existing `candidates` and `booths`
shape, and adds:

- `candidates_2021`: parsed 2021 candidate names, plus party/alliance/vote
  metadata from `RAW_META` and, when fetched, keralaassembly.org result pages.
- `booth_summary`: cleaned booth and vote totals for faster debugging.

The app and predictor read exclusively from `data/2021/*.json`.

`split_2026_round_results.py` creates `data/2026/001.json` through
`data/2026/140.json` from `data/round_results.json`. The app reads
`/api/round_results/<const_no>` exclusively from these split files.

The 2011 workflow creates `data/2011/001.json` through `data/2011/140.json`
from CEO Kerala Form 20 PDFs, then enriches `candidates_2011` using public
Kerala Assembly result pages for party, alliance, vote count, and source URL.

The 2016 workflow creates `data/2016/001.json` through `data/2016/140.json`
from CEO Kerala GE2016 booth-wise PDFs, then enriches `candidates_2016` using
public Kerala Assembly result pages. Scanned PDFs without a text layer keep
empty booth rows but still receive candidate metadata from the public result
source.

## Run

```bash
python app.py
```

Then open http://localhost:5000 in your browser.

## File Structure

```text
kerala-election-predictor/
├── app.py
├── download_pdfs.py
├── parse_pdfs.py
├── split_2021_booth_data.py
├── static/
│   └── index.html
├── data/
│   ├── booth_wise/
│   ├── booth_wise_parsed.json
│   ├── 2021/
│   │   ├── 001.json
│   │   └── ...
│   ├── 2026/
│   │   ├── 001.json
│   │   └── ...
│   ├── 2011/
│   │   ├── booth_wise/
│   │   ├── 001.json
│   │   └── ...
│   ├── 2016/
│   │   ├── booth_wise/
│   │   ├── 001.json
│   │   └── ...
│   ├── round_results.json
│   └── candidates_2026.json
└── README.md
```

## Auxiliary Booths

CEO Kerala PDFs list booths like `1`, `1(A)`, `2`, `2(A)`.

- `1(A)` is the auxiliary booth for main booth `1`.
- Round boundaries count only main booth numbers.
- Split 2021 files exclude obvious parser artifacts where footer/summary rows
  were accidentally interpreted as booth numbers.
