from __future__ import annotations

from dataclasses import dataclass
from typing import List

from fpdf import FPDF


@dataclass
class InvoiceLine:
    description: str
    qty: int
    unit_price: float

    @property
    def amount(self) -> float:
        return self.qty * self.unit_price


@dataclass
class InvoiceDoc:
    filename: str
    supplier: str
    tax_id: str
    bill_to: str
    invoice_number: str
    invoice_date: str
    due_date: str
    lines: List[InvoiceLine]
    vat_percent: int = 22
    footer_note: str = "Payment Terms: Net 30 days | Bank Transfer: IBAN RO1234567890123456"

    @property
    def subtotal(self) -> float:
        return round(sum(line.amount for line in self.lines), 2)

    @property
    def vat_value(self) -> float:
        return round(self.subtotal * self.vat_percent / 100, 2)

    @property
    def total(self) -> float:
        return round(self.subtotal + self.vat_value, 2)


def _money(value: float, with_currency: bool = True) -> str:
    suffix = " RON" if with_currency else ""
    return f"{value:.2f}{suffix}"


def create_invoice(doc: InvoiceDoc) -> None:
    pdf = FPDF("P", "mm", "A4")
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 24)
    pdf.text(20, 25, "INVOICE")

    # Left info block
    pdf.set_font("Helvetica", "B", 12)
    pdf.text(20, 45, "Supplier:")
    pdf.set_font("Helvetica", "", 11)
    pdf.text(20, 53, doc.supplier)
    pdf.text(20, 60, f"Tax ID: {doc.tax_id}")

    pdf.set_font("Helvetica", "B", 12)
    pdf.text(20, 78, "Bill To:")
    pdf.set_font("Helvetica", "", 11)
    pdf.text(20, 86, doc.bill_to)

    # Right info block
    pdf.set_font("Helvetica", "B", 12)
    pdf.text(130, 45, "Invoice Number:")
    pdf.set_font("Helvetica", "", 11)
    pdf.text(130, 53, doc.invoice_number)

    pdf.set_font("Helvetica", "B", 12)
    pdf.text(130, 63, "Invoice Date:")
    pdf.set_font("Helvetica", "", 11)
    pdf.text(130, 71, doc.invoice_date)

    pdf.set_font("Helvetica", "B", 12)
    pdf.text(130, 81, "Due Date:")
    pdf.set_font("Helvetica", "", 11)
    pdf.text(130, 89, doc.due_date)

    # Table header
    table_top = 115
    pdf.set_line_width(0.4)
    pdf.line(20, table_top, 190, table_top)
    pdf.set_font("Helvetica", "B", 11)
    pdf.text(20, 111, "Description")
    pdf.text(98, 111, "Qty")
    pdf.text(115, 111, "Unit Price")
    pdf.text(165, 111, "Amount")

    # Table rows
    y = 123
    pdf.set_font("Helvetica", "", 11)
    for line in doc.lines:
        pdf.text(20, y, line.description)
        pdf.text(98, y, str(line.qty))
        pdf.text(115, y, _money(line.unit_price))
        pdf.text(165, y, _money(line.amount, with_currency=False))
        y += 8

    table_bottom = y + 4
    pdf.set_line_width(0.4)
    pdf.line(20, table_bottom, 190, table_bottom)

    # Totals
    totals_y = table_bottom + 12
    pdf.set_font("Helvetica", "", 11)
    pdf.text(115, totals_y, "Subtotal:")
    pdf.text(165, totals_y, _money(doc.subtotal))

    pdf.text(115, totals_y + 8, f"VAT ({doc.vat_percent}%):")
    pdf.text(165, totals_y + 8, _money(doc.vat_value))

    pdf.set_font("Helvetica", "B", 15)
    pdf.text(115, totals_y + 18, "TOTAL:")
    pdf.text(165, totals_y + 18, _money(doc.total))

    # Footer note
    pdf.set_font("Helvetica", "", 9)
    pdf.text(20, 268, "This is a test invoice for document extraction testing purposes.")
    pdf.text(20, 274, doc.footer_note)

    pdf.output(doc.filename)
    print(f"Generated: {doc.filename}")


def create_contract(
    filename: str,
    contract_number: str,
    party_a: str,
    party_b: str,
    start_date: str,
    end_date: str,
    contract_value: float,
    scope: str,
) -> None:
    pdf = FPDF("P", "mm", "A4")
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 22)
    pdf.text(20, 22, "CONTRACT")

    pdf.set_font("Helvetica", "B", 12)
    pdf.text(20, 36, "Contract Number:")
    pdf.set_font("Helvetica", "", 11)
    pdf.text(65, 36, contract_number)

    pdf.set_font("Helvetica", "B", 12)
    pdf.text(20, 48, "Party A:")
    pdf.set_font("Helvetica", "", 11)
    pdf.text(45, 48, party_a)

    pdf.set_font("Helvetica", "B", 12)
    pdf.text(20, 58, "Party B:")
    pdf.set_font("Helvetica", "", 11)
    pdf.text(45, 58, party_b)

    pdf.set_font("Helvetica", "B", 12)
    pdf.text(20, 70, "Contract Period:")
    pdf.set_font("Helvetica", "", 11)
    pdf.text(62, 70, f"{start_date} to {end_date}")

    pdf.set_font("Helvetica", "B", 12)
    pdf.text(20, 82, "Contract Value:")
    pdf.set_font("Helvetica", "", 11)
    pdf.text(62, 82, _money(contract_value))

    pdf.set_font("Helvetica", "B", 12)
    pdf.text(20, 98, "Scope of Work")
    pdf.set_line_width(0.4)
    pdf.line(20, 101, 190, 101)
    pdf.set_font("Helvetica", "", 11)
    pdf.text(20, 111, scope)

    pdf.set_font("Helvetica", "B", 12)
    pdf.text(20, 132, "Key Clauses")
    pdf.line(20, 135, 190, 135)
    pdf.set_font("Helvetica", "", 11)
    pdf.text(20, 145, "1. Services must be delivered according to agreed milestones.")
    pdf.text(20, 153, "2. Payment is due in 30 days after validated invoice.")
    pdf.text(20, 161, "3. Confidentiality obligations apply to both parties.")
    pdf.text(20, 169, "4. Any dispute is settled under Romanian commercial law.")

    pdf.set_font("Helvetica", "", 9)
    pdf.text(20, 274, "Generated contract fixture for document classification and extraction tests.")
    pdf.output(filename)
    print(f"Generated: {filename}")


def create_report(
    filename: str,
    report_number: str,
    report_title: str,
    author: str,
    report_date: str,
    summary: str,
    findings: list[str],
) -> None:
    pdf = FPDF("P", "mm", "A4")
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 22)
    pdf.text(20, 22, "REPORT")

    pdf.set_font("Helvetica", "B", 12)
    pdf.text(20, 36, "Report Number:")
    pdf.set_font("Helvetica", "", 11)
    pdf.text(58, 36, report_number)

    pdf.set_font("Helvetica", "B", 12)
    pdf.text(20, 48, "Title:")
    pdf.set_font("Helvetica", "", 11)
    pdf.text(33, 48, report_title)

    pdf.set_font("Helvetica", "B", 12)
    pdf.text(20, 60, "Author:")
    pdf.set_font("Helvetica", "", 11)
    pdf.text(37, 60, author)

    pdf.set_font("Helvetica", "B", 12)
    pdf.text(120, 60, "Date:")
    pdf.set_font("Helvetica", "", 11)
    pdf.text(132, 60, report_date)

    pdf.set_font("Helvetica", "B", 12)
    pdf.text(20, 76, "Executive Summary")
    pdf.set_line_width(0.4)
    pdf.line(20, 79, 190, 79)
    pdf.set_font("Helvetica", "", 11)
    pdf.text(20, 89, summary)

    pdf.set_font("Helvetica", "B", 12)
    pdf.text(20, 108, "Key Findings")
    pdf.line(20, 111, 190, 111)
    pdf.set_font("Helvetica", "", 11)
    y = 121
    for idx, finding in enumerate(findings, start=1):
        pdf.text(20, y, f"{idx}. {finding}")
        y += 9

    pdf.set_font("Helvetica", "", 9)
    pdf.text(20, 274, "Generated report fixture for document classification and extraction tests.")
    pdf.output(filename)
    print(f"Generated: {filename}")


if __name__ == "__main__":
    invoice_docs = [
        InvoiceDoc(
            filename="factura_sigura.pdf",
            supplier="Coffee Shop SRL",
            tax_id="RO3456789012",
            bill_to="ABC Company Ltd.",
            invoice_number="FAC-2026/001",
            invoice_date="2026-04-10",
            due_date="2026-05-10",
            lines=[InvoiceLine("Coffee supplies", 1, 45.50)],
        ),
        InvoiceDoc(
            filename="factura_frauduloasa.pdf",
            supplier="Constructii Gigant SRL",
            tax_id="RO9988776655",
            bill_to="Mega Holding SA",
            invoice_number="FAC-2026/002",
            invoice_date="2026-04-11",
            due_date="2026-05-11",
            lines=[InvoiceLine("Industrial equipment", 1, 1_250_000.00)],
        ),
        InvoiceDoc(
            filename="factura_verificare.pdf",
            supplier="Training Center SRL",
            tax_id="RO1122334455",
            bill_to="Client Test SA",
            invoice_number="FAC-2026/003",
            invoice_date="2026-04-12",
            due_date="2026-05-12",
            lines=[InvoiceLine("Training package", 1, 1500.00)],
        ),
        InvoiceDoc(
            filename="safe_invoice.pdf",
            supplier="TechCorp SRL",
            tax_id="RO12345678901",
            bill_to="ABC Company Ltd.",
            invoice_number="INV-2026/001",
            invoice_date="2026-04-10",
            due_date="2026-05-10",
            lines=[
                InvoiceLine("Software License", 1, 500.00),
                InvoiceLine("Support Services", 12, 100.00),
            ],
        ),
        InvoiceDoc(
            filename="high_risk_invoice.pdf",
            supplier="Delta Construct SA",
            tax_id="RO4455667788",
            bill_to="Government Procurement",
            invoice_number="INV-2026/002",
            invoice_date="2026-04-15",
            due_date="2026-04-20",
            lines=[InvoiceLine("Infrastructure works", 1, 65000.00)],
        ),
        InvoiceDoc(
            filename="invoice_bad_sum.pdf",
            supplier="Office Plus SRL",
            tax_id="RO6677889900",
            bill_to="City Services",
            invoice_number="INV-2026/003",
            invoice_date="2026-04-18",
            due_date="2026-05-18",
            lines=[InvoiceLine("Office furniture", 3, 2300.00)],
        ),
        InvoiceDoc(
            filename="invoice_duplicate.pdf",
            supplier="TechCorp SRL",
            tax_id="RO12345678901",
            bill_to="ABC Company Ltd.",
            invoice_number="INV-2026/001",
            invoice_date="2026-04-10",
            due_date="2026-05-10",
            lines=[InvoiceLine("Software License renewal", 1, 500.00)],
        ),
        InvoiceDoc(
            filename="invoice_missing_data.pdf",
            supplier="Unknown Supplier",
            tax_id="RO0000000000",
            bill_to="-",
            invoice_number="INV-2026/004",
            invoice_date="2026-04-22",
            due_date="2026-05-22",
            lines=[InvoiceLine("Consulting services", 1, 950.00)],
        ),
    ]

    for invoice_doc in invoice_docs:
        create_invoice(invoice_doc)

    contract_docs = [
        {
            "filename": "contract_2026_101.pdf",
            "contract_number": "CTR-2026-101",
            "party_a": "City Hall Procurement Department",
            "party_b": "BuildSmart SRL",
            "start_date": "2026-05-01",
            "end_date": "2027-04-30",
            "contract_value": 480000.00,
            "scope": "Rehabilitation works for municipal office building.",
        },
        {
            "filename": "contract_2026_102.pdf",
            "contract_number": "CTR-2026-102",
            "party_a": "County Hospital",
            "party_b": "Meditech Systems SA",
            "start_date": "2026-06-01",
            "end_date": "2028-06-01",
            "contract_value": 920000.00,
            "scope": "Supply and maintenance of diagnostic imaging equipment.",
        },
        {
            "filename": "contract_2026_103.pdf",
            "contract_number": "CTR-2026-103",
            "party_a": "Public Transport Authority",
            "party_b": "Fleet Operations SRL",
            "start_date": "2026-04-15",
            "end_date": "2027-04-14",
            "contract_value": 310000.00,
            "scope": "Maintenance services for electric bus fleet.",
        },
    ]

    for contract_doc in contract_docs:
        create_contract(**contract_doc)

    report_docs = [
        {
            "filename": "report_2026_101.pdf",
            "report_number": "RPT-2026-101",
            "report_title": "Quarterly Procurement Performance",
            "author": "Internal Audit Unit",
            "report_date": "2026-04-20",
            "summary": "Quarterly review of procurement cycle efficiency and compliance.",
            "findings": [
                "Average approval time decreased by 12% versus previous quarter.",
                "Two delayed vendor onboarding files require remediation.",
                "No critical compliance violations were identified.",
            ],
        },
        {
            "filename": "report_2026_102.pdf",
            "report_number": "RPT-2026-102",
            "report_title": "Infrastructure Risk Assessment",
            "author": "Risk Management Office",
            "report_date": "2026-04-22",
            "summary": "Risk scoring for ongoing infrastructure projects and suppliers.",
            "findings": [
                "Three high-value projects exceed budget forecast by over 8%.",
                "Supplier concentration risk observed in road rehabilitation contracts.",
                "Mitigation plan recommends dual-vendor sourcing for critical services.",
            ],
        },
        {
            "filename": "report_2026_103.pdf",
            "report_number": "RPT-2026-103",
            "report_title": "Document Processing KPI Snapshot",
            "author": "Digital Transformation Team",
            "report_date": "2026-04-25",
            "summary": "Operational report on OCR, classification, and review throughput.",
            "findings": [
                "Automated extraction success rate reached 93.5%.",
                "Manual review backlog reduced from 148 to 79 documents.",
                "Top error class remains missing supplier tax identifier.",
            ],
        },
    ]

    for report_doc in report_docs:
        create_report(**report_doc)