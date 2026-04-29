#!/usr/bin/env python3
"""Generate simple contract PDF documents for upload testing."""
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "streamlit_app" / "test_documents"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def create_contract_pdf(filename: str, party_a: str, party_b: str, contract_number: str, date: str, value: str):
    path = OUTPUT_DIR / filename
    doc = fitz.open()
    page = doc.new_page()

    page.insert_text((50, 50), "CONTRACT / CONTRACT OF SERVICES", fontsize=18, fontname="helv")
    page.insert_text((50, 90), f"Contract number: {contract_number}", fontsize=11, fontname="helv")
    page.insert_text((50, 110), f"Date: {date}", fontsize=11, fontname="helv")

    y = 160
    page.insert_text((50, y), f"Between:", fontsize=12, fontname="helv")
    y += 20
    page.insert_text((70, y), f"Party A: {party_a}", fontsize=11, fontname="helv")
    y += 18
    page.insert_text((70, y), f"Party B: {party_b}", fontsize=11, fontname="helv")

    y += 36
    page.insert_text((50, y), "Subject:", fontsize=12, fontname="helv")
    y += 20
    page.insert_text((70, y), "Provision of IT services and support as per attached schedule.", fontsize=11, fontname="helv")

    y += 40
    page.insert_text((50, y), "Value:", fontsize=12, fontname="helv")
    page.insert_text((150, y), value, fontsize=11, fontname="helv")

    y += 40
    page.insert_text((50, y), "Signatures:", fontsize=12, fontname="helv")
    y += 40
    page.insert_text((70, y), "Party A (signature)       Party B (signature)", fontsize=10, fontname="helv")

    doc.save(path)
    print(f"Created {path.relative_to(ROOT)}")


def main():
    contracts = [
        ("contract_2026_101.pdf", "Municipality Authority", "ACME INDUSTRIES SRL", "CTR-2025-101", "2026-01-15", "10,000.00 RON"),
        ("contract_2026_102.pdf", "Public Works Dept.", "InfraBuild SRL", "CTR-2025-106", "2026-02-10", "250,000.00 RON"),
        ("contract_2025_201.pdf", "Energy Office", "GreenPower SA", "CTR-2025-201", "2025-06-20", "75,000.00 RON"),
    ]

    for filename, a, b, num, date, val in contracts:
        create_contract_pdf(filename, a, b, num, date, val)

    print("Done generating contracts.")


if __name__ == '__main__':
    main()
