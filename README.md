# Kerala Election Predictor

Next.js frontend plus Flask API for exploring Kerala assembly election results,
historical booth patterns, ECI round data, and early-round winner projections.

## Run Locally

```bash
pip install -r requirements.txt
python app.py
```

In another terminal:

```bash
npm install
npm run dev
```

Open http://localhost:3000.

The Next.js dev server proxies `/api/*` to Flask at
`http://127.0.0.1:5000`. If Flask runs somewhere else, set
`BACKEND_ORIGIN=http://host:port` before `npm run dev`.

The app reads split JSON files from `data/`. PDFs are used only as parser
inputs and are ignored by git.

## Project Structure

The project is split into two clear layers:

**Runtime (app root)** — files needed for the app to run:

| File | Purpose |
|---|---|
| `app.py` | Flask API server — the only entry point |
| `predict_from_eci.py` | Prediction engine, imported directly by `app.py` |
| `eci_scraper.py` | Live ECI scraper, imported by `app.py` and `auto_runner.py` |
| `auto_runner.py` | Companion process — polls ECI every 5 min alongside `app.py` |

**Data pipeline (`data_pipeline/`)** — one-time and maintenance scripts not
needed by the running app:

| Category | Scripts |
|---|---|
| Download | `download_pdfs.py`, `download_2011_pdfs.py`, `download_2016_pdfs.py`, `download_ls_pdfs.py`, `download_2026_booth_list.py` |
| Parse | `parse_pdfs.py`, `parse_2011_pdfs.py`, `parse_2016_pdfs.py`, `parse_ls_pdfs.py`, `parse_by_election_pdfs.py` |
| Enrich | `enrich_2021_candidate_parties.py`, `enrich_2016_candidate_parties.py`, `enrich_2011_candidate_parties.py`, `enrich_2021_alliances_from_wiki.py`, `enrich_historical_alliances_from_wiki.py`, `enrich_ls_alliances_from_wiki.py`, `enrich_2026_data.py` |
| Split / extract | `split_2021_booth_data.py`, `split_2026_round_results.py`, `extract_2021_booth_counts.py` |
| Scrape | `scrape_round_results.py`, `scrape_votes_polled.py` |
| Analysis / simulation | `analyze_booth_changes.py`, `simulate_round5.py`, `ml_prediction_experiment.py`, `ml_round_simulation.py` |
| Tests | `test_constraint.py`, `test_gradient_boost.py` |

**Path convention inside `data_pipeline/` scripts:**

```python
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # data_pipeline/
BASE_DIR    = os.path.dirname(_SCRIPT_DIR)                 # project root
DATA_DIR    = os.path.join(BASE_DIR, "data")               # output JSON goes here
PDF_DIR     = os.path.join(_SCRIPT_DIR, "source_pdfs", "<year>")  # PDF inputs
```

## Data Layout

```text
app/                      Next.js frontend shell
  components/             Reusable React components
  lib/                    Frontend-only helpers
  types/                  TypeScript types
data/                     JSON files read by the live app (no PDFs here)
  2011/                   Assembly Form 20 booth history, 001.json..140.json
  2016/                   Assembly Form 20 booth history, 001.json..140.json
  2019_ls/                Lok Sabha LAC-wise history, 001.json..140.json
  2021/                   Assembly booth history, 001.json..140.json
  2024_ls/                Lok Sabha LAC-wise history, 001.json..140.json
  2024_be/                2024 assembly by-elections, partial set
  2024_be_ls/             2024 Wayanad LS by-election LAC segments, partial set
  2025_be/                2025 assembly by-elections, partial set
  2026/                   ECI round-wise assembly data, 001.json..140.json
  data_parsing/           Raw/intermediate scraper outputs
data_pipeline/            Offline data preparation — not required at runtime
  source_pdfs/            Original PDF source files (gitignored)
    2011/                 140 Form 20 PDFs for 2011 Assembly
    2016/                 140 Form 20 PDFs for 2016 Assembly
    2021/                 140 Form 20 PDFs for 2021 Assembly
    2019_ls/              140 LAC-wise PDFs for 2019 Lok Sabha
    2024_ls/              140 LAC-wise PDFs for 2024 Lok Sabha
    2024_be/              By-election PDFs (Palakkad, Chelakkara)
    2024_be_ls/           Wayanad LS by-election LAC segment PDFs
    2025_be/              2025 by-election PDFs
  *.py                    Download / parse / enrich / analysis scripts
```

Full election-year folders should contain 140 JSON files. By-election folders
are intentionally partial and should contain only affected constituencies.

## Common Workflows

All pipeline scripts must be run from the `data_pipeline/` directory (or with
their full path), so that `__file__` resolves correctly.

Build 2021 assembly history:

```bash
cd data_pipeline
python download_pdfs.py
python parse_pdfs.py
python split_2021_booth_data.py
python enrich_2021_candidate_parties.py
```

Build 2011 and 2016 history:

```bash
cd data_pipeline
python download_2011_pdfs.py
python parse_2011_pdfs.py
python enrich_2011_candidate_parties.py

python download_2016_pdfs.py
python parse_2016_pdfs.py
python enrich_2016_candidate_parties.py
```

Build 2019 and 2024 LS history:

```bash
cd data_pipeline
python download_ls_pdfs.py
python parse_ls_pdfs.py
python enrich_ls_alliances_from_wiki.py
```

Build 2026 round data:

```bash
cd data_pipeline
python split_2026_round_results.py
python enrich_2026_data.py
cd ..
python predict_from_eci.py
```

Parse selected by-elections:

```bash
cd data_pipeline
python parse_by_election_pdfs.py
cd ..
python predict_from_eci.py
```

`parse_by_election_pdfs.py` currently handles:

- `2024_be`: Palakkad `056`, Chelakkara `061`
- `2024_be_ls`: Wayanad LS by-election segments `017`, `018`, `019`, `032`, `034`, `035`, `036`
- `2025_be`: Nilambur `035`

To add another by-election, download the official Form 20 PDF into
`data_pipeline/source_pdfs/<year>_be/<const_no:03d>.pdf`, add a config entry in
`data_pipeline/parse_by_election_pdfs.py`, run the parser, and validate the
generated JSON in `data/<year>_be/<const_no:03d>.json`.

## Prediction Inputs

`predict_from_eci.py` combines these history years:

```text
2011, 2016, 2019_ls, 2021, 2024_ls, 2024_be, 2024_be_ls, 2025_be
```

For 2024, the loader reads `2024_ls` first, then overrides affected
constituencies with `2024_be` and `2024_be_ls`. This keeps the normal 2024 LS
history for all other seats while using newer by-election data where available.

If a historical JSON has no booth rows, prediction skips that year for booth
pattern projection and falls back to the other available years. This is used for
`data/2021/066.json`, where Ollur has correct 2021 result metadata but no valid
booth-wise data.

## Validation Checklist

After changing data, run:

```bash
python -m py_compile app.py predict_from_eci.py data_pipeline/parse_by_election_pdfs.py
python predict_from_eci.py
```

Recommended checks:

- JSON parses with `python -m json.tool data/<folder>/<file>.json`.
- Full-year folders have 140 JSON files.
- Each constituency has one major `ldf`, `udf`, and `nda` candidate unless
  the real election had no candidate for that alliance.
- `booth_summary.candidate_totals` equals the sum of all booth row columns.
- By-election `evm_summary` and `final_summary` match the official Form 20.
- 2026 `total` equals the final round cumulative vote list.
- No booth row has impossible candidate-column totals. A useful guardrail is
  `sum(votes) <= 2000` for one booth row.

Known legitimate exceptions:

- `data/2011/055.json`: Malampuzha had no NDA candidate.
- `data/2021/013.json`: Thalassery had no NDA candidate.
- `data/2021/066.json`: Ollur is metadata-only because the booth-wise file was
  duplicated from Wadakkanchery.

## Git And Deployment

PDFs are ignored by `.gitignore`, so commit generated JSON files and parser/code
changes, not downloaded PDFs.

Typical commit flow:

```bash
git status --short
git add app.py predict_from_eci.py static/index.html app/ package.json package-lock.json next.config.mjs tsconfig.json vercel.json README.md data/<changed-folder> data_pipeline/<changed-scripts>
git commit -m "Describe the data or prediction change"
git push origin main
```

For Vercel deployment:

- Next.js owns the frontend route `/`.
- Flask remains the Python backend for `/api/*`.
- The React frontend owns its route, state, and tab rendering. Shared styles now
  live in `app/globals.css`.
- New frontend code should go into `app/components`, `app/lib`, and `app/types`.
  Keep `app/page.tsx` thin and route-level only.
- Keep `requirements.txt` minimal. Runtime parsing should not depend on PDF
  libraries; PDF parsing is an offline maintenance step.

Before deploying, run:

```bash
npm run typecheck
npm run build
python -m py_compile app.py predict_from_eci.py eci_scraper.py
```

## Notes

- Round boundaries count only main booth numbers. Auxiliary booths are included
  in their parent round but do not increment the main booth count.
- `data/data_parsing/` contains raw scraper inputs. The app should prefer split
  files under `data/2026/` and generated prediction output under
  `data/live_predictions.json`.
- Avoid hand-editing large generated booth arrays unless fixing a proven parser
  artifact. When possible, update the parser and regenerate.
