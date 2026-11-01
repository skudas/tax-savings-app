"""Test database initialization."""

import sys
import traceback

try:
    print("Importing database module...")
    from database import init_db, get_db
    print("  OK - database module imported")

    print("Initializing database...")
    init_db()
    print("  OK - database initialized")

    print("Importing models...")
    from models import User, ProfessionalProfile
    print("  OK - models imported")

    print("Testing database session...")
    from database import SessionLocal
    db = SessionLocal()
    print("  OK - database session created")

    users = db.query(User).all()
    print(f"  OK - query executed, found {len(users)} users")

    print("\nAll database tests passed!")

except Exception as e:
    print(f"\nERROR: {e}")
    traceback.print_exc()
