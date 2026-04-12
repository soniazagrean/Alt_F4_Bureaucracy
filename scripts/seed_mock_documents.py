#!/usr/bin/env python3
"""
Mock Documents Seeder for NV-024 Testing
Generates and seeds mock documents with various statuses for manual testing
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import json
from io import BytesIO

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.db.database import SessionLocal, engine
from app.models import Document, DocumentStatusEnum, DocumentTypeEnum, DocumentPage, User, NomenclatorEntry
from app.services.storage import StorageService
from app.services.search import SearchService
from app.config import settings

# Try to import reportlab for PDF generation
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("⚠️  reportlab not installed, will create minimal PDFs")


def create_sample_pdf(filename: str, title: str, content: str) -> BytesIO:
    """Create a sample PDF file in memory with unique content"""
    pdf_buffer = BytesIO()
    
    if REPORTLAB_AVAILABLE:
        c = canvas.Canvas(pdf_buffer, pagesize=letter)
        c.setTitle(title)
        
        # Header
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, title)
        
        # Content
        c.setFont("Helvetica", 10)
        y_position = 720
        for line in content.split('\n'):
            if y_position < 50:
                c.showPage()
                y_position = 750
            c.drawString(50, y_position, line)
            y_position -= 15
        
        # Footer with timestamp
        c.setFont("Helvetica", 8)
        c.drawString(50, 30, f"Generated: {datetime.now().isoformat()}")
        c.drawString(50, 15, "Mock Document for Testing NV-024")
        
        c.save()
    else:
        # Minimal but unique PDF structure - include content in the stream so each PDF is different
        # Use content as part of the PDF to ensure different hashes
        import hashlib
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        
        pdf_buffer.write(b"%PDF-1.4\n")
        pdf_buffer.write(b"1 0 obj\n<</Type /Catalog /Pages 2 0 R>>\nendobj\n")
        pdf_buffer.write(b"2 0 obj\n<</Type /Pages /Kids [3 0 R] /Count 1>>\nendobj\n")
        pdf_buffer.write(b"3 0 obj\n<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R>>\nendobj\n")
        
        # Include unique content in the stream to differentiate PDFs
        stream_content = f"BT\n/F1 12 Tf\n50 700 Td\n({title[:40]}) Tj\n50 680 Td\n(Hash: {content_hash}) Tj\nET\n"
        stream_bytes = stream_content.encode()
        stream_length = len(stream_bytes)
        
        pdf_buffer.write(f"4 0 obj\n<</Length {stream_length}>> stream\n".encode())
        pdf_buffer.write(stream_bytes)
        pdf_buffer.write(b"\nendstream\nendobj\n")
        
        pdf_buffer.write(b"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000115 00000 n\n0000000203 00000 n\n")
        pdf_buffer.write(b"trailer\n<</Size 5 /Root 1 0 R>>\n%%EOF")
    
    pdf_buffer.seek(0)
    return pdf_buffer


def get_or_create_admin(db: Session) -> User:
    """Get or create admin user for seeding"""
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        print("  🔨 Creating admin user...")
        admin = User(
            username="admin",
            email="admin@nexusvault.ro",
            full_name="System Administrator",
            role=RoleEnum.ADMIN,
            is_verified=True,
            is_active=True
        )
        admin.set_password("admin123")
        db.add(admin)
        db.commit()
    return admin


def get_or_create_nomenclator(db: Session, code: str, name: str, parent_code: str = None) -> NomenclatorEntry:
    """Get or create nomenclator entry"""
    entry = db.query(NomenclatorEntry).filter(NomenclatorEntry.code == code).first()
    if not entry:
        parent = None
        if parent_code:
            parent = db.query(NomenclatorEntry).filter(NomenclatorEntry.code == parent_code).first()
        
        entry = NomenclatorEntry(
            code=code,
            name=name,
            parent_id=parent.id if parent else None,
            is_active=1
        )
        db.add(entry)
        db.commit()
    return entry


def index_documents_in_meilisearch(documents: list):
    """Index documents in MeiliSearch for search functionality"""
    try:
        search_service = SearchService()
        
        # Prepare documents for indexing
        docs_to_index = []
        for doc in documents:
            doc_data = {
                "id": str(doc.id),
                "title": doc.title,
                "description": doc.description or "",
                "tip_document": doc.document_type.value if doc.document_type else "other",
                "status": doc.status.value if doc.status else "pending",
                "document_number": doc.document_number,
                "amount": doc.amount or 0,
                "currency": doc.currency or "RON",
                "data": doc.document_date.isoformat() if doc.document_date else datetime.now(timezone.utc).isoformat(),
                "created_at": doc.created_at.isoformat() if doc.created_at else datetime.now(timezone.utc).isoformat(),
            }
            docs_to_index.append(doc_data)
        
        # Index in MeiliSearch
        if docs_to_index:
            search_service.client.index("documents").add_documents(docs_to_index)
            print(f"  ✓ Indexed {len(docs_to_index)} documents in MeiliSearch")
        
    except Exception as e:
        print(f"  ⚠️  MeiliSearch indexing failed: {str(e)[:50]}...")
        print(f"     Documents will still be searchable via PostgreSQL fallback")


def upload_pdf_to_storage(pdf_buffer: BytesIO, bucket_key: str, file_name: str) -> str:
    """Upload PDF to MinIO storage"""
    try:
        storage = StorageService()
        storage.upload_file(
            file_data=pdf_buffer.getvalue(),
            file_name=file_name,
            bucket_key=bucket_key,
            content_type="application/pdf"
        )
        return f"{bucket_key}/{file_name}"
    except Exception as e:
        print(f"  ⚠️  Storage upload failed: {e}")
        print(f"     Using local path instead: {file_name}")
        return file_name


def seed_mock_documents(db: Session):
    """Seed database with mock documents for testing"""
    
    print("\n🎬 Seeding Mock Documents for NV-024 Testing\n")
    
    # Get or create admin user
    print("📁 Setting up prerequisites...")
    admin = get_or_create_admin(db)
    
    # Create nomenclator entries
    fin_parent = get_or_create_nomenclator(db, "FIN", "Financial Documents")
    inv_parent = get_or_create_nomenclator(db, "FIN-INV", "Invoices", "FIN")
    legal_parent = get_or_create_nomenclator(db, "LEGAL", "Legal Documents")
    contracts = get_or_create_nomenclator(db, "LEGAL-CON", "Contracts", "LEGAL")
    
    print("✓ Prerequisites created\n")
    
    # Mock document configurations
    mock_docs = [
        {
            "document_number": "DOC-2026-001",
            "title": "Invoice 2024-001",
            "doc_type": DocumentTypeEnum.INVOICE,
            "status": DocumentStatusEnum.PENDING,
            "amount": 1500.00,
            "nomenclator": inv_parent,
            "retry_count": 0,
        },
        {
            "document_number": "DOC-2026-002",
            "title": "Invoice 2024-002",
            "doc_type": DocumentTypeEnum.INVOICE,
            "status": DocumentStatusEnum.UPLOADED,
            "amount": 2350.50,
            "nomenclator": inv_parent,
            "retry_count": 0,
        },
        {
            "document_number": "DOC-2026-003",
            "title": "Invoice 2024-003",
            "doc_type": DocumentTypeEnum.INVOICE,
            "status": DocumentStatusEnum.PROCESSING,
            "amount": 890.25,
            "nomenclator": inv_parent,
            "retry_count": 1,
        },
        {
            "document_number": "DOC-2026-004",
            "title": "Invoice 2024-004",
            "doc_type": DocumentTypeEnum.INVOICE,
            "status": DocumentStatusEnum.CLASSIFIED,
            "amount": 3200.00,
            "nomenclator": inv_parent,
            "retry_count": 0,
        },
        {
            "document_number": "DOC-2026-005",
            "title": "Invoice 2024-005",
            "doc_type": DocumentTypeEnum.INVOICE,
            "status": DocumentStatusEnum.EXTRACTED,
            "amount": 1750.75,
            "nomenclator": inv_parent,
            "retry_count": 0,
        },
        {
            "document_number": "DOC-2026-006",
            "title": "Invoice 2024-006",
            "doc_type": DocumentTypeEnum.INVOICE,
            "status": DocumentStatusEnum.VALIDATED,
            "amount": 4500.00,
            "nomenclator": inv_parent,
            "retry_count": 0,
        },
        {
            "document_number": "DOC-2026-007",
            "title": "Service Contract Q1 2024",
            "doc_type": DocumentTypeEnum.CONTRACT,
            "status": DocumentStatusEnum.ERROR,
            "amount": 5000.00,
            "nomenclator": contracts,
            "retry_count": 3,
            "error_message": "OCR extraction failed - low image quality",
        },
        {
            "document_number": "DOC-2026-008",
            "title": "Invoice 2024-007",
            "doc_type": DocumentTypeEnum.INVOICE,
            "status": DocumentStatusEnum.REJECTED,
            "amount": 650.00,
            "nomenclator": inv_parent,
            "retry_count": 2,
            "error_message": "Fraud detected - amount mismatch",
        },
        {
            "document_number": "DOC-2026-009",
            "title": "Invoice 2024-008",
            "doc_type": DocumentTypeEnum.INVOICE,
            "status": DocumentStatusEnum.PENDING,
            "amount": 2100.00,
            "nomenclator": inv_parent,
            "retry_count": 0,
        },
        {
            "document_number": "DOC-2026-010",
            "title": "Invoice 2024-009",
            "doc_type": DocumentTypeEnum.INVOICE,
            "status": DocumentStatusEnum.ARCHIVED,
            "amount": 800.00,
            "nomenclator": inv_parent,
            "retry_count": 0,
            "archived_at": datetime.now(timezone.utc) - timedelta(days=7),
        },
    ]
    
    print("📄 Creating documents...\n")
    
    created_count = 0
    for doc_config in mock_docs:
        # Check if document already exists
        existing = db.query(Document).filter(
            Document.document_number == doc_config["document_number"]
        ).first()
        
        if existing:
            print(f"  ⏭️  {doc_config['document_number']} - Already exists")
            continue
        
        # Create PDF content
        pdf_content = f"""
{doc_config['title']}
{'=' * 50}

Document Number: {doc_config['document_number']}
Document Type: {doc_config['doc_type'].value}
Date: {datetime.now().strftime('%d.%m.%Y')}
Amount: {doc_config['amount']} RON

Status: {doc_config['status'].value}

This is a mock document generated for testing the NV-024 feature:
Upload page and status monitoring.

Content: Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.

{'=' * 50}
Generated for testing - NV-024
        """
        
        # Create PDF
        pdf_buffer = create_sample_pdf(doc_config["document_number"], doc_config["title"], pdf_content)
        pdf_data = pdf_buffer.getvalue()
        
        # Calculate file hash
        file_hash = hashlib.sha256(pdf_data).hexdigest()
        
        # Upload to storage (or use local path if storage unavailable)
        file_path = f"mock_documents/{doc_config['document_number']}.pdf"
        try:
            storage = StorageService()
            storage.upload_file(
                file_data=pdf_data,
                file_name=file_path,
                bucket_key="uploads",
                content_type="application/pdf"
            )
            print(f"  ✓ {doc_config['document_number']} - Uploaded to MinIO")
        except Exception as e:
            print(f"  ⚠️  {doc_config['document_number']} - MinIO upload failed: {str(e)[:50]}...")
        
        # Create document record
        document = Document(
            document_number=doc_config["document_number"],
            title=doc_config["title"],
            description=f"Mock {doc_config['doc_type'].value} document created for NV-024 testing. Amount: {doc_config['amount']} RON",
            document_type=doc_config["doc_type"],
            status=doc_config["status"],
            amount=doc_config["amount"],
            currency="RON",
            file_path=f"uploads/{file_path}",
            file_size=len(pdf_data),
            mime_type="application/pdf",
            page_count=1,
            file_hash=file_hash,
            nomenclator_id=doc_config["nomenclator"].id,
            created_by_id=admin.id,
            document_date=datetime.now(timezone.utc) - timedelta(days=7),
            retry_count=doc_config.get("retry_count", 0),
            error_message=doc_config.get("error_message"),
            error_timestamp=datetime.now(timezone.utc) if doc_config.get("error_message") else None,
            fraud_score=0.8 if "Fraud" in (doc_config.get("error_message") or "") else 0.0,
            confidence=0.92 if doc_config["status"] in [DocumentStatusEnum.EXTRACTED, DocumentStatusEnum.VALIDATED] else 0.0,
            archived_at=doc_config.get("archived_at"),
        )
        
        db.add(document)
        created_count += 1
    
    # Commit all documents
    try:
        db.commit()
        print(f"\n✅ Successfully created {created_count} mock documents\n")
        
        # Step 2: Index documents in MeiliSearch for search functionality
        print("🔍 Indexing documents in MeiliSearch...")
        
        # Fetch newly created documents for indexing
        indexed_docs = db.query(Document).filter(
            Document.document_number.like('DOC-2026-%')
        ).all()
        
        index_documents_in_meilisearch(indexed_docs)
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error committing documents: {e}\n")
        raise
    
    # Display summary
    print("📊 Summary of Created Documents:\n")
    
    statuses = [doc["status"] for doc in mock_docs]
    for status in DocumentStatusEnum:
        count = sum(1 for s in statuses if s == status)
        if count > 0:
            print(f"  • {status.value:12} : {count:2} documents")
    
    print("\n" + "="*50)
    print("✨ Mock documents seeded successfully!")
    print("="*50 + "\n")
    
    print("💡 Testing Tips for NV-024:")
    print("  1. Visit the Upload page in Streamlit")
    print("  2. Check document status polling (should update every 3s)")
    print("  3. Verify different status badges are displayed correctly")
    print("  4. Test error message display for REJECTED/ERROR documents")
    print("  5. Verify progress indicators work smoothly\n")


def main():
    """Main entry point"""
    db = SessionLocal()
    try:
        seed_mock_documents(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
