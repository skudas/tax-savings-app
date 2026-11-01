"""Test search function directly."""

from database import SessionLocal
from models import ProfessionalProfile
from routes.professionals import ProfessionalListResponse, RateCardResponse

db = SessionLocal()

specialty = "S-Corp"
verified_only = False
skip = 0
limit = 20

# Get professionals
query = db.query(ProfessionalProfile)

if verified_only:
    query = query.filter(ProfessionalProfile.verified == True)

professionals = query.all()

print(f"Found {len(professionals)} professionals\n")

# Apply specialty filter
if specialty:
    professionals = [
        p for p in professionals
        if p.specialties and any(specialty.lower() in s.lower() for s in p.specialties)
    ]

print(f"After specialty filter: {len(professionals)}\n")

# Apply pagination
professionals = professionals[skip:skip + limit]

print(f"After pagination: {len(professionals)}\n")

# Build response
result = []
for prof in professionals:
    try:
        print(f"Processing professional {prof.id}...")

        rate_cards_list = []
        for rc in prof.rate_cards:
            print(f"  Adding rate card: {rc.service_name}")
            rc_response = RateCardResponse(
                id=rc.id,
                service_name=rc.service_name,
                service_type=rc.service_type,
                price=rc.price,
                duration_minutes=rc.duration_minutes,
                description=rc.description
            )
            rate_cards_list.append(rc_response)

        print(f"  Rate cards: {len(rate_cards_list)}")

        prof_response = ProfessionalListResponse(
            id=prof.id,
            user_id=prof.user_id,
            user_email=prof.user.email,
            user_name=f"{prof.user.first_name} {prof.user.last_name}",
            bio=prof.bio,
            specialties=prof.specialties,
            years_experience=prof.years_experience,
            certifications=prof.certifications,
            verified=prof.verified,
            average_rating=prof.average_rating,
            total_consultations=prof.total_consultations,
            rate_cards=rate_cards_list
        )

        result.append(prof_response)
        print(f"  Success!")

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()

print(f"\nFinal result: {len(result)} professionals")
for p in result:
    print(f"  - {p.user_name}: {p.specialties}")
