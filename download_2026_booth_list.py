#!/usr/bin/env python3
"""
Download and parse the 2026 booth-name-list PDF from Kerala CEO website
Extracts booth counts for each constituency to update booths_2026.json

Usage: python download_2026_booth_list.py
"""

import os, sys, json, re

try:
    import requests
    import pdfplumber
except ImportError:
    print("Installing required packages...")
    os.system(f"{sys.executable} -m pip install requests pdfplumber --quiet")
    import requests
    import pdfplumber

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
DIR_2026 = os.path.join(DATA_DIR, "2026")

PDF_URL = "https://www.ceo.kerala.gov.in/ceokerala/pdf/govt_orders/legislative-assembly-2026/booth-name-list.pdf"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/pdf,*/*",
}


def download_pdf(url, output_path):
    """Download PDF from URL."""
    print(f"Downloading from: {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(r.content)
        print(f"✓ Downloaded {len(r.content)} bytes to {output_path}")
        return True
    except Exception as e:
        print(f"✗ Download failed: {e}")
        return False


def parse_booth_list_pdf(pdf_path):
    """
    Parse 2026 booth-name-list PDF and extract booth count per constituency.
    
    Expected format: PDF with sections for each constituency listing booth names.
    We count unique main booths per constituency (excluding auxiliary booths).
    """
    
    booths_by_const = {}
    current_constituency = None
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                lines = text.split("\n")
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Look for constituency header (usually contains constituency number and name)
                    # Format might be: "1 - MANJESHWARAM" or similar
                    const_match = re.match(r'^(\d+)\s*[-–]\s*(.+?)(?:\s+\(\d+\)|$)', line, re.IGNORECASE)
                    if const_match:
                        const_no = int(const_match.group(1))
                        const_name = const_match.group(2).strip()
                        current_constituency = const_no
                        if const_no not in booths_by_const:
                            booths_by_const[const_no] = {"name": const_name, "booths": set()}
                        continue
                    
                    # Booth labels are typically: "1", "1A", "2", "2A", etc.
                    # Extract booth numbers from each line
                    if current_constituency:
                        # Split by common separators (comma, space, newline)
                        booth_labels = re.findall(r'\b(\d+[A-Z]?)\b', line)
                        for booth in booth_labels:
                            # Extract main booth number (remove the auxiliary letter if present)
                            main_booth = re.match(r'^(\d+)', booth)
                            if main_booth:
                                booths_by_const[current_constituency]["booths"].add(int(main_booth.group(1)))
    
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        return None
    
    # Convert sets to counts
    result = {}
    for const_no, data in booths_by_const.items():
        result[str(const_no)] = len(data["booths"])
    
    return result, booths_by_const


def main():
    print("=" * 60)
    print("  Kerala Election 2026 — Booth-wise List Downloader")
    print("=" * 60)
    
    # Create data directory if needed
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Download PDF
    temp_pdf = os.path.join(DATA_DIR, "booth_list_2026_temp.pdf")
    if not download_pdf(PDF_URL, temp_pdf):
        print("\n⚠  Could not download PDF. Please download manually from:")
        print(f"   {PDF_URL}")
        print("   And save to: " + temp_pdf)
        sys.exit(1)
    
    # Parse PDF
    print("\nParsing PDF...")
    booth_counts, detailed = parse_booth_list_pdf(temp_pdf)
    
    if not booth_counts:
        print("✗ Failed to extract booth counts from PDF")
        sys.exit(1)
    
    # Show results
    print(f"\n✓ Extracted booth counts for {len(booth_counts)} constituencies:")
    for const_no in sorted(int(k) for k in booth_counts.keys())[:5]:
        const_no_str = str(const_no)
        count = booth_counts[const_no_str]
        print(f"   Const {const_no}: {count} booths")
    print(f"   ... (showing first 5)")

    # Merge booth_count into each data/2026/*.json file
    updated = 0
    for const_no_str, count in booth_counts.items():
        path = os.path.join(DIR_2026, f"{int(const_no_str):03d}.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)
        entry["booth_count"] = count
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)
        updated += 1
    print(f"\n✓ Updated booth_count in {updated} files in {DIR_2026}")
    
    # Clean up temp file
    os.remove(temp_pdf)
    print("✓ Temporary PDF deleted")


if __name__ == "__main__":
    main()
