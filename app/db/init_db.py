"""
Database initialization script - creates all tables and seeds initial data
"""
from app.db.database import init_db, SessionLocal, engine
from app.models import User, NomenclatorEntry, RoleEnum, PastrareEnum
from app.models.archive import Dosar
from datetime import datetime

def seed_initial_data():
    """Seed database with initial data"""
    db = SessionLocal()

    try:
        # Check if admin user already exists
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            print("Creating admin user...")
            admin = User(
                username="admin",
                email="admin@nexusvault.ro",
                full_name="System Administrator",
                role=RoleEnum.ADMIN,
                is_verified=True,
                is_active=True
            )
            admin.set_password("admin123")  # Change this in production!
            db.add(admin)
            db.commit()
            print("✓ Admin user created")
        else:
            print("✓ Admin user already exists")

        # Check if root nomenclator entry exists
        root = db.query(NomenclatorEntry).filter(NomenclatorEntry.code == "ROOT").first()
        if not root:
            print("Creating root nomenclator entry...")
            root = NomenclatorEntry(
                code="ROOT",
                name="Root Classification",
                description="Root category for document classification",
                is_active=1
            )
            db.add(root)
            db.commit()
            print("✓ Root nomenclator entry created")
        else:
            print("✓ Root nomenclator entry already exists")

        # Create default nomenclator entries (official Romanian I-VII categories, English labels)
        default_entries = [
            {"code": "I", "name": "Administrative and Management Documents", "parent_code": "ROOT"},
            {"code": "I.1", "name": "Decisions, resolutions, internal regulations, annual reports", "parent_code": "I"},
            {"code": "II", "name": "Personnel Documents", "parent_code": "ROOT"},
            {"code": "II.1", "name": "Personnel files, job descriptions, staffing tables, individual employment contracts", "parent_code": "II"},
            {"code": "III", "name": "Financial and Accounting Documents", "parent_code": "ROOT"},
            {"code": "III.1", "name": "Execution accounts, balance sheets, accounting notes, invoices, payment orders, bank statements", "parent_code": "III"},
            {"code": "IV", "name": "Fixed Assets and Materials Documents", "parent_code": "ROOT"},
            {"code": "IV.1", "name": "Inventory lists, disposal reports, warehouse records", "parent_code": "IV"},
            {"code": "V", "name": "Educational Activity Documents", "parent_code": "ROOT"},
            {"code": "V.1", "name": "Curriculum plans, timetables, catalogs, register books", "parent_code": "V"},
            {"code": "VI", "name": "Correspondence", "parent_code": "ROOT"},
            {"code": "VI.1", "name": "Current institutional correspondence", "parent_code": "VI"},
            {"code": "VII", "name": "Other Documents", "parent_code": "ROOT"},
            {"code": "VII.1", "name": "Register books, special regime forms, other documents", "parent_code": "VII"},
            {"code": "INBOX", "name": "Inbox (Auto Archive)", "parent_code": "ROOT"},
        ]

        for entry_data in default_entries:
            existing = db.query(NomenclatorEntry).filter(
                NomenclatorEntry.code == entry_data["code"]
            ).first()

            parent = None
            if entry_data["parent_code"]:
                parent = db.query(NomenclatorEntry).filter(
                    NomenclatorEntry.code == entry_data["parent_code"]
                ).first()

            if not existing:
                new_entry = NomenclatorEntry(
                    code=entry_data["code"],
                    name=entry_data["name"],
                    parent_id=parent.id if parent else None,
                    is_active=1
                )
                db.add(new_entry)
                print(f"  Creating {entry_data['code']}...")
            else:
                if entry_data["parent_code"] and parent and existing.parent_id != parent.id:
                    existing.parent_id = parent.id
                    existing.name = entry_data["name"]
                    existing.is_active = 1
                    print(f"  Repairing parent for {entry_data['code']} -> {entry_data['parent_code']}")
                elif entry_data["parent_code"] and existing.parent_id is None:
                    existing.parent_id = parent.id if parent else None
                    existing.name = entry_data["name"]
                    existing.is_active = 1
                    print(f"  Setting missing parent for {entry_data['code']} -> {entry_data['parent_code']}")
                else:
                    existing.name = entry_data["name"]
                    existing.is_active = 1

        db.commit()
        print("✓ Nomenclator entries created")

        root_entry = db.query(NomenclatorEntry).filter(NomenclatorEntry.code == "ROOT").first()
        if root_entry:
            orphans = db.query(NomenclatorEntry).filter(
                NomenclatorEntry.parent_id.is_(None),
                NomenclatorEntry.code != "ROOT"
            ).all()
            for orphan in orphans:
                orphan.parent_id = root_entry.id
                orphan.is_active = 1
                print(f"  Reparenting orphan {orphan.code} under ROOT")
            db.commit()

        # Deactivate legacy non-official categories so only official I-VII appear
        legacy_codes = [
            "FIN", "FIN-INV", "FIN-PAY",
            "HR", "HR-EMP", "HR-PAY",
            "LEGAL", "LEGAL-CON", "LEGAL-DEC",
        ]
        for code in legacy_codes:
            legacy_entry = db.query(NomenclatorEntry).filter(NomenclatorEntry.code == code).first()
            if legacy_entry and legacy_entry.is_active == 1:
                legacy_entry.is_active = 0
                print(f"  Deactivating legacy nomenclator entry {code}")

        db.commit()
        print("✓ Legacy nomenclator entries deactivated")

        # Ensure default INBOX dosar exists
        inbox_entry = db.query(NomenclatorEntry).filter(NomenclatorEntry.code == "INBOX").first()
        if inbox_entry:
            inbox_dosar = db.query(Dosar).filter(Dosar.dosar_number == "INBOX-0001").first()
            if not inbox_dosar:
                inbox_dosar = Dosar(
                    dosar_number="INBOX-0001",
                    title="Inbox",
                    description="Default auto-archive inbox",
                    nomenclator_id=inbox_entry.id,
                    termen_pastrare=PastrareEnum.FIVE_YEARS,
                )
                db.add(inbox_dosar)
                db.commit()
                print("✓ INBOX dosar created")
            else:
                print("✓ INBOX dosar already exists")

    except Exception as e:
        print(f"✗ Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    """Initialize database"""
    print("\n=== NexusVault Database Initialization ===\n")

    print("Creating tables...")
    init_db()
    print("✓ Tables created\n")

    print("Seeding initial data...")
    seed_initial_data()

    print("\n=== Database initialization complete! ===\n")

if __name__ == "__main__":
    main()
