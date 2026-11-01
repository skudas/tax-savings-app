"""Debug professional profile data."""

from database import SessionLocal
from models import ProfessionalProfile

db = SessionLocal()

# Fetch all professionals
professionals = db.query(ProfessionalProfile).all()

print(f"Found {len(professionals)} professionals\n")

for prof in professionals:
    print(f"ID: {prof.id}")
    print(f"  User: {prof.user.email}")
    print(f"  Bio: {prof.bio}")
    print(f"  Specialties type: {type(prof.specialties)} value: {prof.specialties}")
    print(f"  Certifications type: {type(prof.certifications)} value: {prof.certifications}")
    print()
