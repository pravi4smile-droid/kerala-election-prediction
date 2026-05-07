# 2026 Booth Data Integration Guide

## Overview
This integration adds support for Kerala 2026 election prediction by accounting for booth count changes between 2021 and 2026. The system now:
1. Extracts 2021 booth counts from parsed PDF data
2. Downloads and parses the 2026 booth-name-list PDF from the Kerala CEO website
3. Scales 2021 voting patterns based on booth count differences
4. Applies these adjustments when predicting 2026 results

## Setup Instructions

### Step 1: Extract 2021 Booth Counts
First, ensure you have the parsed 2021 booth data (generated from `parse_pdfs.py`), then run:

```bash
python extract_2021_booth_counts.py
```

This creates `data/booths_2021.json` containing the main booth count for each of the 140 constituencies from the 2021 data.

### Step 2: Download and Parse 2026 Booth List
Download and parse the official 2026 booth-name-list PDF:

```bash
python download_2026_booth_list.py
```

This script will:
- Download the PDF from: https://www.ceo.kerala.gov.in/ceokerala/pdf/govt_orders/legislative-assembly-2026/booth-name-list.pdf
- Extract booth counts per constituency
- Save to `data/booths_2026.json`
- Show booth count changes between 2021 and 2026

## Data Files

### `data/booths_2021.json`
Contains main booth count for each constituency in 2021:
```json
{
  "1": 169,
  "2": 163,
  "3": 171,
  ...
}
```

### `data/booths_2026.json`
Contains main booth count for each constituency in 2026:
```json
{
  "1": 229,
  "2": 218,
  "3": 237,
  ...
}
```

## How Predictions Work

### Booth-Count Scaling
When predicting 2026 results using 2021 data, the system applies a scaling factor:

$$\text{scaling\_factor} = \frac{\text{booths\_2026}}{\text{booths\_2021}}$$

Example: If constituency 1 had 169 booths in 2021 but 229 in 2026:
- Scaling factor = 229 / 169 ≈ 1.355
- If early votes show: LDF=5000, UDF=4000, NDA=3000
- Scaled votes: LDF=6775, UDF=5420, NDA=4065

### Complete Prediction Process
1. **Apply booth scaling**: votes × (booths_2026 / booths_2021)
2. **Apply pattern adjustment**: Multiply by 2021 early-to-final voting pattern factors
3. **Project final results**: Combine both adjustments for final prediction

### API Usage

#### GET `/api/constituencies`
Returns all 140 constituencies with booth count data:
```json
{
  "no": 1,
  "name": "Manjeshwaram",
  "booth_2021": 169,
  "booth_2026": 229,
  "booth_change": 60,
  "booth_change_pct": 35.5,
  "booth_scaling_factor": 1.355,
  ...
}
```

#### POST `/api/predict`
Predict results with optional booth adjustment:
```json
{
  "const_no": 1,
  "booths_counted": 50,
  "total_main_booths": 229,
  "votes": [5000, 4000, 3000],
  "prediction_year": 2026
}
```

Response includes booth scaling information:
```json
{
  "projected": [6775, 5420, 4065],
  "total_projected": 16260,
  "booth_info": {
    "scaling": 1.355,
    "booth_2021": 169,
    "booth_2026": 229,
    "booth_change": 60,
    "booth_change_pct": 35.5
  },
  ...
}
```

## Interpretation

### Booth Count Changes
- **Positive change** (more booths in 2026): Booth scaling factor > 1.0
  - Votes per booth might be lower if booth count increases
  - Total votes typically increase due to more booths
  
- **Negative change** (fewer booths in 2026): Booth scaling factor < 1.0
  - Total booths decreased
  - May indicate redistricting or consolidation

### Scaling Factor Guide
- **1.0**: No booth count change (rare)
- **0.9-1.1**: Minor change (±10%)
- **1.1-1.5**: Moderate increase (+10% to +50%)
- **< 0.9 or > 1.5**: Significant change (requires close monitoring)

## Important Notes

1. **Booth count impact**: The scaling factor directly multiplies vote counts. A booth increase from 169→229 (×1.355) means votes scale proportionally.

2. **Sampling assumption**: The scaling treats each additional booth as having average voting patterns similar to existing booths.

3. **Combined factors**: The system applies both:
   - Booth count scaling (accounts for structural changes)
   - Pattern factors from 2021 (accounts for voting behavior changes across rounds)

4. **Validation**: Compare projections from:
   - Linear scaling: `votes / pct_counted`
   - 2021 pattern: 2021 early-to-final factors
   - 2026 booth-adjusted: both factors combined

## Example Workflow

```bash
# Step 1: Prepare 2021 data (if not already done)
python download_pdfs.py          # Download 2021 PDFs
python parse_pdfs.py             # Parse 2021 booth data
python extract_2021_booth_counts.py  # Extract 2021 counts

# Step 2: Prepare 2026 data
python download_2026_booth_list.py   # Download and parse 2026 PDF

# Step 3: Run prediction server
python app.py

# Step 4: Open http://localhost:5000 and start predictions
```

## Troubleshooting

- **"No 2021 booth count data"**: Run `extract_2021_booth_counts.py`
- **"No 2026 booth count data"**: Run `download_2026_booth_list.py`
- **PDF parsing fails**: Check internet connection and URL availability
- **Scaling factor seems wrong**: Verify both booth count files have data for the constituency

## Files Created/Modified

### New Scripts
- `download_2026_booth_list.py` - Download and parse 2026 PDF
- `extract_2021_booth_counts.py` - Extract 2021 booth counts

### New Data Files
- `data/booths_2021.json` - 2021 booth counts
- `data/booths_2026.json` - 2026 booth counts

### Modified Files
- `app.py` - Updated prediction logic with booth scaling
