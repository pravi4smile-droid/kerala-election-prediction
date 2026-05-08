# Kerala Election Predictor

Local Flask app for exploring Kerala assembly election results, historical
booth patterns, ECI round data, and early-round winner projections.

## Run Locally

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000.

The app reads split JSON files from `data/`. PDFs are used only as parser
inputs and are ignored by git.

## Data Layout

```text
data/
  2011/              Assembly Form 20 booth history, 001.json..140.json
  2016/              Assembly Form 20 booth history, 001.json..140.json
  2019_ls/           Lok Sabha LAC-wise history, 001.json..140.json
  2021/              Assembly booth history, 001.json..140.json
  2024_ls/           Lok Sabha LAC-wise history, 001.json..140.json
  2024_be/           2024 assembly by-elections, partial set
  2024_be_ls/        2024 Wayanad LS by-election LAC segments, partial set
  2025_be/           2025 assembly by-elections, partial set
  2026/              ECI round-wise assembly data, 001.json..140.json
  data_parsing/      Raw/intermediate scraper outputs
```

Full election-year folders should contain 140 JSON files. By-election folders
are intentionally partial and should contain only affected constituencies.

## Common Workflows

Build 2021 assembly history:

```bash
python download_pdfs.py
python parse_pdfs.py
python split_2021_booth_data.py
python enrich_2021_candidate_parties.py
```

Build 2011 and 2016 history:

```bash
python download_2011_pdfs.py
python parse_2011_pdfs.py
python enrich_2011_candidate_parties.py

python download_2016_pdfs.py
python parse_2016_pdfs.py
python enrich_2016_candidate_parties.py
```

Build 2019 and 2024 LS history:

```bash
python download_ls_pdfs.py
python parse_ls_pdfs.py
python enrich_ls_alliances_from_wiki.py
```

Build 2026 round data:

```bash
python split_2026_round_results.py
python enrich_2026_data.py
python predict_from_eci.py
```

Parse selected by-elections:

```bash
python parse_by_election_pdfs.py
python predict_from_eci.py
```

`parse_by_election_pdfs.py` currently handles:

- `2024_be`: Palakkad `056`, Chelakkara `061`
- `2024_be_ls`: Wayanad LS by-election segments `017`, `018`, `019`, `032`, `034`, `035`, `036`
- `2025_be`: Nilambur `035`

To add another by-election, download the official Form 20 PDF into
`data/<year>_be/booth_wise/<const_no>.pdf` or
`data/<year>_be_ls/booth_wise/<const_no>.pdf`, add a config entry in
`parse_by_election_pdfs.py`, run the parser, and validate the generated JSON.

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
python -m py_compile app.py predict_from_eci.py parse_by_election_pdfs.py
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
git add app.py predict_from_eci.py static/index.html README.md data/<changed-folder> parse_by_election_pdfs.py
git commit -m "Describe the data or prediction change"
git push origin main
```

For Vercel deployment, keep `requirements.txt` minimal. Runtime parsing should
not depend on PDF libraries; PDF parsing is an offline maintenance step.

## Notes

- Round boundaries count only main booth numbers. Auxiliary booths are included
  in their parent round but do not increment the main booth count.
- `data/data_parsing/` contains raw scraper inputs. The app should prefer split
  files under `data/2026/` and generated prediction output under
  `data/live_predictions.json`.
- Avoid hand-editing large generated booth arrays unless fixing a proven parser
  artifact. When possible, update the parser and regenerate.
