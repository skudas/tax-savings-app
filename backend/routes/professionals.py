"""Professional tax advisor profile management routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr

from database import get_db
from models import User, UserType, ProfessionalProfile, RateCard, Review
from .auth import get_current_user

router = APIRouter()


class RateCardCreate(BaseModel):
    service_name: str
    service_type: str  # "hourly", "fixed", "package"
    price: float
    duration_minutes: Optional[int] = None
    description: Optional[str] = None


class RateCardResponse(RateCardCreate):
    id: int

    class Config:
        from_attributes = True


class ProfessionalProfileCreate(BaseModel):
    bio: Optional[str] = None
    specialties: Optional[List[str]] = None  # ["S-Corp", "LLC", etc]
    years_experience: Optional[int] = None
    certifications: Optional[List[str]] = None  # ["CPA", "EA", etc]
    license_number: Optional[str] = None
    availability_json: Optional[dict] = None


class ProfessionalProfileResponse(ProfessionalProfileCreate):
    id: int
    user_id: int
    verified: bool
    total_consultations: int
    average_rating: float
    created_at: datetime
    updated_at: datetime
    rate_cards: List[RateCardResponse] = []

    class Config:
        from_attributes = True


class ProfessionalListResponse(BaseModel):
    id: int
    user_id: int
    user_email: str
    user_name: str
    bio: Optional[str]
    specialties: Optional[List[str]]
    years_experience: Optional[int]
    certifications: Optional[List[str]]
    verified: bool
    average_rating: float
    total_consultations: int
    rate_cards: List[RateCardResponse] = []

    class Config:
        from_attributes = True


class ProfessionalReviewResponse(BaseModel):
    id: int
    rating: int
    title: Optional[str]
    content: Optional[str]
    created_at: datetime
    client_name: str
    client_email: str


@router.post("/profile", response_model=ProfessionalProfileResponse)
async def create_professional_profile(
    profile_data: ProfessionalProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create professional profile for current user."""
    if current_user.professional_profile:
        raise HTTPException(status_code=400, detail="Professional profile already exists")

    # Update user type
    current_user.user_type = UserType.PROFESSIONAL.value

    # Create professional profile
    professional = ProfessionalProfile(
        user_id=current_user.id,
        bio=profile_data.bio,
        specialties=profile_data.specialties,
        years_experience=profile_data.years_experience,
        certifications=profile_data.certifications,
        license_number=profile_data.license_number,
        availability_json=profile_data.availability_json
    )

    db.add(professional)
    db.commit()
    db.refresh(professional)

    return professional


@router.get("/profile", response_model=ProfessionalProfileResponse)
async def get_professional_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get professional profile for current user."""
    if not current_user.professional_profile:
        raise HTTPException(status_code=404, detail="Professional profile not found")

    return current_user.professional_profile


@router.put("/profile", response_model=ProfessionalProfileResponse)
async def update_professional_profile(
    profile_data: ProfessionalProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update professional profile."""
    if not current_user.professional_profile:
        raise HTTPException(status_code=404, detail="Professional profile not found")

    profile = current_user.professional_profile

    # Update fields
    if profile_data.bio is not None:
        profile.bio = profile_data.bio
    if profile_data.specialties is not None:
        profile.specialties = profile_data.specialties
    if profile_data.years_experience is not None:
        profile.years_experience = profile_data.years_experience
    if profile_data.certifications is not None:
        profile.certifications = profile_data.certifications
    if profile_data.license_number is not None:
        profile.license_number = profile_data.license_number
    if profile_data.availability_json is not None:
        profile.availability_json = profile_data.availability_json

    profile.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(profile)

    return profile


@router.post("/profile/rate-cards", response_model=RateCardResponse)
async def create_rate_card(
    rate_card: RateCardCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a rate card for professional's services."""
    if not current_user.professional_profile:
        raise HTTPException(status_code=403, detail="Not a professional")

    new_rate_card = RateCard(
        professional_id=current_user.professional_profile.id,
        service_name=rate_card.service_name,
        service_type=rate_card.service_type,
        price=rate_card.price,
        duration_minutes=rate_card.duration_minutes,
        description=rate_card.description
    )

    db.add(new_rate_card)
    db.commit()
    db.refresh(new_rate_card)

    return new_rate_card


@router.get("/profile/rate-cards", response_model=List[RateCardResponse])
async def get_rate_cards(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all rate cards for professional."""
    if not current_user.professional_profile:
        raise HTTPException(status_code=403, detail="Not a professional")

    return db.query(RateCard).filter(
        RateCard.professional_id == current_user.professional_profile.id
    ).all()


@router.get("/search", response_model=List[ProfessionalListResponse])
async def search_professionals(
    specialty: Optional[str] = Query(None),
    certification: Optional[str] = Query(None),
    min_experience: Optional[int] = Query(None),
    verified_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Search professionals by specialties, certifications, or experience."""
    query = db.query(ProfessionalProfile)

    if verified_only:
        query = query.filter(ProfessionalProfile.verified == True)

    # Fetch all and filter in Python (safer for JSON columns)
    professionals = query.all()

    # Apply filters on fetched data
    if specialty:
        professionals = [
            p for p in professionals
            if p.specialties and any(specialty.lower() in s.lower() for s in p.specialties)
        ]

    if certification:
        professionals = [
            p for p in professionals
            if p.certifications and any(certification.lower() in c.lower() for c in p.certifications)
        ]

    if min_experience is not None:
        professionals = [
            p for p in professionals
            if p.years_experience and p.years_experience >= min_experience
        ]

    # Apply pagination
    professionals = professionals[skip:skip + limit]

    result = []
    for prof in professionals:
        result.append(ProfessionalListResponse(
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
            rate_cards=[RateCardResponse(id=rc.id, service_name=rc.service_name, service_type=rc.service_type, price=rc.price, duration_minutes=rc.duration_minutes, description=rc.description) for rc in prof.rate_cards]
        ))

    return result


@router.get("/{professional_id}", response_model=ProfessionalListResponse)
async def get_professional(
    professional_id: int,
    db: Session = Depends(get_db)
):
    """Get public professional profile by ID."""
    prof = db.query(ProfessionalProfile).filter(
        ProfessionalProfile.id == professional_id
    ).first()

    if not prof:
        raise HTTPException(status_code=404, detail="Professional not found")

    return ProfessionalListResponse(
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
        rate_cards=[RateCardResponse.from_orm(rc) for rc in prof.rate_cards]
    )


@router.get("/{professional_id}/reviews", response_model=List[ProfessionalReviewResponse])
async def get_professional_reviews(
    professional_id: int,
    db: Session = Depends(get_db)
):
    """Get public client reviews for a professional profile."""
    prof = db.query(ProfessionalProfile).filter(
        ProfessionalProfile.id == professional_id
    ).first()

    if not prof:
        raise HTTPException(status_code=404, detail="Professional not found")

    reviews = db.query(Review).filter(
        Review.professional_id == professional_id
    ).order_by(Review.created_at.desc()).all()

    result = []
    for review in reviews:
        client = db.query(User).filter(User.id == review.client_id).first()
        result.append(ProfessionalReviewResponse(
            id=review.id,
            rating=review.rating,
            title=review.title,
            content=review.content,
            created_at=review.created_at,
            client_name=f"{client.first_name} {client.last_name}" if client else "Verified client",
            client_email=client.email if client else ""
        ))

    return result


@router.get("/", response_model=List[ProfessionalListResponse])
async def list_professionals(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List all verified professionals with pagination."""
    professionals = db.query(ProfessionalProfile).filter(
        ProfessionalProfile.verified == True
    ).offset(skip).limit(limit).all()

    result = []
    for prof in professionals:
        result.append(ProfessionalListResponse(
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
            rate_cards=[RateCardResponse(id=rc.id, service_name=rc.service_name, service_type=rc.service_type, price=rc.price, duration_minutes=rc.duration_minutes, description=rc.description) for rc in prof.rate_cards]
        ))

    return result
