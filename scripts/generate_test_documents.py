#!/usr/bin/env python3
"""Generate sample invoice PDF documents for Streamlit upload testing."""
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "streamlit_app" / "test_documents"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _draw_header(page: fitz.Page, fields: dict[str, str]) -> int:
    margin = 50
    y = 50
    page.insert_text((margin, y), "INVOICE", fontsize=28, fontname="helv", fill=(0, 0, 0))
    y += 40

    page.insert_text((margin, y), "Supplier:", fontsize=12, fontname="helv")
    page.insert_text((margin, y + 16), fields["Supplier"], fontsize=11, fontname="helv")
    page.insert_text((margin, y + 32), fields["Tax ID"], fontsize=11, fontname="helv")
    y += 60

    page.insert_text((margin, y), "Bill To:", fontsize=12, fontname="helv")
    page.insert_text((margin, y + 16), fields["Bill To"], fontsize=11, fontname="helv")

    right_x = 360
    page.insert_text((right_x, 90), "Invoice Number:", fontsize=12, fontname="helv")
    page.insert_text((right_x + 120, 90), fields["Invoice Number"], fontsize=12, fontname="helv")
    page.insert_text((right_x, 110), "Invoice Date:", fontsize=12, fontname="helv")
    page.insert_text((right_x + 120, 110), fields["Invoice Date"], fontsize=12, fontname="helv")
    page.insert_text((right_x, 130), "Due Date:", fontsize=12, fontname="helv")
    page.insert_text((right_x + 120, 130), fields["Due Date"], fontsize=12, fontname="helv")
    return 160


def _draw_table(page: fitz.Page, items: list[dict[str, str]]) -> int:
    start_x = 50
    y = 220
    columns = [start_x, 300, 380, 470]
    page.insert_text((start_x, y - 18), "Description", fontsize=11, fontname="helv")
    page.insert_text((columns[1], y - 18), "Qty", fontsize=11, fontname="helv")
    page.insert_text((columns[2], y - 18), "Unit Price", fontsize=11, fontname="helv")
    page.insert_text((columns[3], y - 18), "Amount", fontsize=11, fontname="helv")
    y += 8
    y += 10

    for item in items:
        page.insert_text((start_x, y), item["description"], fontsize=11, fontname="helv")
        page.insert_text((columns[1], y), item["qty"], fontsize=11, fontname="helv")
        page.insert_text((columns[2], y), item["unit_price"], fontsize=11, fontname="helv")
        page.insert_text((columns[3], y), item["amount"], fontsize=11, fontname="helv")
        y += 22

    return y + 20


def _draw_totals(page: fitz.Page, fields: dict[str, str], y: int) -> None:
    base_x = 360
    page.insert_text((base_x, y), "Subtotal:", fontsize=11, fontname="helv")
    page.insert_text((base_x + 100, y), fields["Subtotal"], fontsize=11, fontname="helv")
    y += 18
    page.insert_text((base_x, y), "VAT (22%):", fontsize=11, fontname="helv")
    page.insert_text((base_x + 100, y), fields["VAT"], fontsize=11, fontname="helv")
    y += 18
    page.insert_text((base_x, y), "TOTAL:", fontsize=13, fontname="helv", fill=(0, 0, 0))
    page.insert_text((base_x + 100, y), fields["Total"], fontsize=13, fontname="helv", fill=(0, 0, 0))


def _draw_metadata(page: fitz.Page, fields: dict[str, str]) -> None:
    y = 430
    page.insert_text((50, y), "Supplier CUI:", fontsize=11, fontname="helv")
    page.insert_text((150, y), fields["Tax ID"], fontsize=11, fontname="helv")
    y += 18
    page.insert_text((50, y), "IBAN:", fontsize=11, fontname="helv")
    page.insert_text((150, y), fields["IBAN"], fontsize=11, fontname="helv")


def create_invoice_pdf(filename: str, fields: dict[str, str]) -> None:
    path = OUTPUT_DIR / filename
    doc = fitz.open()
    page = doc.new_page()

    y = _draw_header(page, fields)

    items = fields["items"]
    y = _draw_table(page, items)

    _draw_totals(page, fields, y)
    _draw_metadata(page, fields)

    doc.save(path)
    print(f"Created {path.relative_to(ROOT)}")


def main() -> None:
    invoices = [
        {
            "filename": "invoice_acme_2025-001.pdf",
            "fields": {
                "Supplier": "SC ACME INDUSTRIES SRL",
                "Tax ID": "RO12345678",
                "Bill To": "ABC Company Ltd.",
                "Invoice Number": "FAC-2025/001",
                "Invoice Date": "2025-04-10",
                "Due Date": "2025-05-10",
                "IBAN": "RO49AAAA1B31007593840000",
                "Subtotal": "1,700.00 RON",
                "VAT": "374.00 RON",
                "Total": "2,074.00 RON",
                "Cod nomenclator": "III.1",
                "Dosar propus": "Financial Documents 2024",
                "items": [
                    {"description": "Software License", "qty": "1", "unit_price": "500.00 RON", "amount": "500.00"},
                    {"description": "Support Services", "qty": "12", "unit_price": "100.00 RON", "amount": "1,200.00"},
                ],
            },
        },
        {
            "filename": "invoice_acme_2025-002.pdf",
            "fields": {
                "Supplier": "SC ACME INDUSTRIES SRL",
                "Tax ID": "RO12345678",
                "Bill To": "ABC Company Ltd.",
                "Invoice Number": "FAC-2025/002",
                "Invoice Date": "2025-04-15",
                "Due Date": "2025-05-15",
                "IBAN": "RO49AAAA1B31007593840000",
                "Subtotal": "2,850.00 RON",
                "VAT": "627.00 RON",
                "Total": "3,477.00 RON",
                "Cod nomenclator": "III.1",
                "Dosar propus": "Financial Documents 2024",
                "items": [
                    {"description": "Cloud infrastructure setup", "qty": "1", "unit_price": "1,500.00 RON", "amount": "1,500.00"},
                    {"description": "Technical support", "qty": "6", "unit_price": "225.00 RON", "amount": "1,350.00"},
                ],
            },
        },
        {
            "filename": "invoice_orange_2025-003.pdf",
            "fields": {
                "Supplier": "SC ORANGE LOGISTICS SRL",
                "Tax ID": "RO87654321",
                "Bill To": "DEF Distribution SA",
                "Invoice Number": "FAC-2025/003",
                "Invoice Date": "2025-04-18",
                "Due Date": "2025-05-18",
                "IBAN": "RO49BBBB1B31007593840000",
                "Subtotal": "2,450.00 RON",
                "VAT": "539.00 RON",
                "Total": "2,989.00 RON",
                "Cod nomenclator": "III.1",
                "Dosar propus": "Financial Documents 2024",
                "items": [
                    {"description": "Transportation service", "qty": "1", "unit_price": "1,200.00 RON", "amount": "1,200.00"},
                    {"description": "Storage fee", "qty": "1", "unit_price": "1,250.00 RON", "amount": "1,250.00"},
                ],
            },
        },
        {
            "filename": "invoice_orange_2025-004.pdf",
            "fields": {
                "Supplier": "SC ORANGE LOGISTICS SRL",
                "Tax ID": "RO87654321",
                "Bill To": "GHI Retail SRL",
                "Invoice Number": "FAC-2025/004",
                "Invoice Date": "2025-04-22",
                "Due Date": "2025-05-22",
                "IBAN": "RO49BBBB1B31007593840000",
                "Subtotal": "1,980.00 RON",
                "VAT": "435.60 RON",
                "Total": "2,415.60 RON",
                "Cod nomenclator": "III.1",
                "Dosar propus": "Financial Documents 2024",
                "items": [
                    {"description": "Last-mile delivery", "qty": "5", "unit_price": "360.00 RON", "amount": "1,800.00"},
                    {"description": "Insurance fee", "qty": "1", "unit_price": "180.00 RON", "amount": "180.00"},
                ],
            },
        },
        {
            "filename": "invoice_fleet_2024-005.pdf",
            "fields": {
                "Supplier": "SC FLEET OPERATIONS SRL",
                "Tax ID": "RO33445566",
                "Bill To": "Public Transport Authority",
                "Invoice Number": "FAC-2024/005",
                "Invoice Date": "2024-04-25",
                "Due Date": "2024-05-25",
                "IBAN": "RO49DDDD1B31007593840000",
                "Subtotal": "28,000.00 RON",
                "VAT": "6,160.00 RON",
                "Total": "34,160.00 RON",
                "Cod nomenclator": "III.1",
                "Dosar propus": "Transport Contracts 2026",
                "items": [
                    {"description": "Fleet maintenance service", "qty": "1", "unit_price": "28,000.00 RON", "amount": "28,000.00"},
                ],
            },
        },
        {
            "filename": "invoice_fleet_2024-006.pdf",
            "fields": {
                "Supplier": "SC FLEET OPERATIONS SRL",
                "Tax ID": "RO33445566",
                "Bill To": "Public Transport Authority",
                "Invoice Number": "FAC-2024/006",
                "Invoice Date": "2024-04-28",
                "Due Date": "2024-05-28",
                "IBAN": "RO49DDDD1B31007593840000",
                "Subtotal": "14,500.00 RON",
                "VAT": "3,190.00 RON",
                "Total": "17,690.00 RON",
                "Cod nomenclator": "III.1",
                "Dosar propus": "Transport Contracts 2026",
                "items": [
                    {"description": "Emergency repair service", "qty": "1", "unit_price": "14,500.00 RON", "amount": "14,500.00"},
                ],
            },
        },
        {
            "filename": "invoice_blue_2024-007.pdf",
            "fields": {
                "Supplier": "SC BLUE CONSULTING SRL",
                "Tax ID": "RO11223344",
                "Bill To": "JKL Holdings SA",
                "Invoice Number": "FAC-2024/007",
                "Invoice Date": "2024-04-30",
                "Due Date": "2024-05-30",
                "IBAN": "RO49CCCC1B31007593840000",
                "Subtotal": "4,750.00 RON",
                "VAT": "1,045.00 RON",
                "Total": "5,795.00 RON",
                "Cod nomenclator": "III.1",
                "Dosar propus": "Other Financial 2025",
                "items": [
                    {"description": "Strategy consulting", "qty": "1", "unit_price": "4,500.00 RON", "amount": "4,500.00"},
                    {"description": "Report delivery", "qty": "1", "unit_price": "250.00 RON", "amount": "250.00"},
                ],
            },
        },
    ]

    print(f"Generating {len(invoices)} invoice PDFs in {OUTPUT_DIR.relative_to(ROOT)}")
    for invoice in invoices:
        create_invoice_pdf(invoice["filename"], invoice["fields"])

    print("Done.")


if __name__ == "__main__":
    main()
