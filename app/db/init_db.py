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

        # Create default nomenclator entries
        default_entries = [
            {"code": "FIN", "name": "Financial Documents", "parent_code": "ROOT"},
            {"code": "FIN-INV", "name": "Invoices", "parent_code": "FIN"},
            {"code": "FIN-PAY", "name": "Payment Records", "parent_code": "FIN"},
            {"code": "HR", "name": "Human Resources", "parent_code": "ROOT"},
            {"code": "HR-EMP", "name": "Employee Records", "parent_code": "HR"},
            {"code": "HR-PAY", "name": "Payroll", "parent_code": "HR"},
            {"code": "LEGAL", "name": "Legal Documents", "parent_code": "ROOT"},
            {"code": "LEGAL-CON", "name": "Contracts", "parent_code": "LEGAL"},
            {"code": "LEGAL-DEC", "name": "Decisions", "parent_code": "LEGAL"},
            {"code": "INBOX", "name": "Inbox (Auto Archive)", "parent_code": "ROOT"},
        ]

        for entry_data in default_entries:
            existing = db.query(NomenclatorEntry).filter(
                NomenclatorEntry.code == entry_data["code"]
            ).first()

            if not existing:
                parent = db.query(NomenclatorEntry).filter(
                    NomenclatorEntry.code == entry_data["parent_code"]
                ).first()

                new_entry = NomenclatorEntry(
                    code=entry_data["code"],
                    name=entry_data["name"],
                    parent_id=parent.id if parent else None,
                    is_active=1
                )
                db.add(new_entry)
                print(f"  Creating {entry_data['code']}...")

        db.commit()
        print("✓ Nomenclator entries created")

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
