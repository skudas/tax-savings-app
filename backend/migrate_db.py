"""Migrate database schema."""

from database import drop_db, init_db

print("Dropping old database schema...")
drop_db()
print("  OK - Schema dropped")

print("Creating new database schema...")
init_db()
print("  OK - Schema created with new models")

print("\nDatabase migration completed!")
