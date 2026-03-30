from fpdf import FPDF
from pathlib import Path

def create_test_pdf(filename, supplier, net, vat, total, stamped=True):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, f"INVOICE: {filename.split('.')[0].upper()}", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("helvetica", "", 12)
    pdf.cell(0, 10, f"Supplier: {supplier}", ln=True)
    pdf.cell(0, 10, f"Net Amount: {net} RON", ln=True)
    pdf.cell(0, 10, f"VAT Amount: {vat} RON", ln=True)
    pdf.cell(0, 10, f"Total Amount: {total} RON", ln=True)
    
    if stamped:
        pdf.ln(20)
        pdf.set_text_color(0, 0, 255)  # Blue color for stamp
        pdf.set_font("helvetica", "B", 14)
        pdf.cell(0, 10, "[ STAMPED & VERIFIED ]", ln=True)
    
    # Target directory based on your folder structure
    output_dir = Path("tests/fixtures/invoices")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = output_dir / filename
    pdf.output(str(file_path))
    print(f"Generated: {file_path}")

# 1. Valid Invoice (Correct Math)
create_test_pdf("invoice_valid.pdf", "Correct Corp SRL", "100.00", "19.00", "119.00")

# 2. Wrong VAT (Math Error: 100 + 50 != 119)
create_test_pdf("invoice_wrong_vat.pdf", "Math Error SA", "100.00", "50.00", "119.00")

# 3. No Stamp (Visual Missing)
create_test_pdf("invoice_no_stamp.pdf", "No Signatures Ltd", "500.00", "95.00", "595.00", stamped=False)