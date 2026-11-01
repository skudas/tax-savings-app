"""Consultation booking and management routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel

from database import get_db
from models import User, Consultation, ConsultationStatus, RateCard
from .auth import get_current_user

router = APIRouter()


class ConsultationCreate(BaseModel):
    professional_id: int
    rate_card_id: int
    scheduled_at: datetime
    duration_minutes: int
    notes: Optional[str] = None


class ConsultationUpdate(BaseModel):
    status: Optional[str] = None
    meeting_link: Optional[str] = None
    notes: Optional[str] = None


class ConsultationResponse(BaseModel):
    id: int
    client_id: int
    professional_id: int
    rate_card_id: int
    scheduled_at: datetime
    duration_minutes: int
    rate_per_unit: float
    total_price: float
    commission_percent: float
    commission_amount: float
    professional_receives: float
    status: str
    notes: Optional[str]
    meeting_link: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class ConsultationDetailResponse(ConsultationResponse):
    client_email: str
    client_name: str
    professional_email: str
    professional_name: str
    service_name: str
    service_type: str


@router.post("/", response_model=ConsultationResponse)
async def create_consultation(
    consultation: ConsultationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Book a consultation with a professional."""
    # Get rate card
    rate_card = db.query(RateCard).filter(
        RateCard.id == consultation.rate_card_id
    ).first()

    if not rate_card:
        raise HTTPException(status_code=404, detail="Rate card not found")

    # Verify professional exists
    professional = db.query(User).filter(
        User.id == consultation.professional_id
    ).first()

    if not professional or not professional.professional_profile:
        raise HTTPException(status_code=404, detail="Professional not found")

    # Calculate price
    if rate_card.service_type == "hourly":
        total_price = (consultation.duration_minutes / 60) * rate_card.price
    else:  # fixed or package
        total_price = rate_card.price

    # Calculate commission (10% default)
    commission_percent = 10.0
    commission_amount = total_price * (commission_percent / 100)
    professional_receives = total_price - commission_amount

    # Create consultation
    new_consultation = Consultation(
        client_id=current_user.id,
        professional_id=consultation.professional_id,
        rate_card_id=consultation.rate_card_id,
        scheduled_at=consultation.scheduled_at,
        duration_minutes=consultation.duration_minutes,
        rate_per_unit=rate_card.price,
        total_price=total_price,
        commission_percent=commission_percent,
        commission_amount=commission_amount,
        professional_receives=professional_receives,
        status=ConsultationStatus.PENDING.value,
        notes=consultation.notes
    )

    db.add(new_consultation)
    db.commit()
    db.refresh(new_consultation)

    return new_consultation


@router.get("/my-bookings", response_model=List[ConsultationDetailResponse])
async def get_my_bookings(
    current_user: User = Depends(get_current_user),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get all bookings for current user (as client or professional)."""
    query = db.query(Consultation).filter(
        (Consultation.client_id == current_user.id) |
        (Consultation.professional_id == current_user.id)
    )

    if status:
        query = query.filter(Consultation.status == status)

    consultations = query.order_by(
        Consultation.scheduled_at.desc()
    ).offset(skip).limit(limit).all()

    result = []
    for c in consultations:
        result.append(ConsultationDetailResponse(
            id=c.id,
            client_id=c.client_id,
            professional_id=c.professional_id,
            rate_card_id=c.rate_card_id,
            scheduled_at=c.scheduled_at,
            duration_minutes=c.duration_minutes,
            rate_per_unit=c.rate_per_unit,
            total_price=c.total_price,
            commission_percent=c.commission_percent,
            commission_amount=c.commission_amount,
            professional_receives=c.professional_receives,
            status=c.status,
            notes=c.notes,
            meeting_link=c.meeting_link,
            created_at=c.created_at,
            completed_at=c.completed_at,
            client_email=c.client.email,
            client_name=f"{c.client.first_name} {c.client.last_name}",
            professional_email=c.professional.email,
            professional_name=f"{c.professional.first_name} {c.professional.last_name}",
            service_name=c.rate_card.service_name,
            service_type=c.rate_card.service_type
        ))

    return result


@router.get("/{consultation_id}", response_model=ConsultationDetailResponse)
async def get_consultation(
    consultation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get consultation details."""
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    # Check access
    if (consultation.client_id != current_user.id and
        consultation.professional_id != current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    return ConsultationDetailResponse(
        id=consultation.id,
        client_id=consultation.client_id,
        professional_id=consultation.professional_id,
        rate_card_id=consultation.rate_card_id,
        scheduled_at=consultation.scheduled_at,
        duration_minutes=consultation.duration_minutes,
        rate_per_unit=consultation.rate_per_unit,
        total_price=consultation.total_price,
        commission_percent=consultation.commission_percent,
        commission_amount=consultation.commission_amount,
        professional_receives=consultation.professional_receives,
        status=consultation.status,
        notes=consultation.notes,
        meeting_link=consultation.meeting_link,
        created_at=consultation.created_at,
        completed_at=consultation.completed_at,
        client_email=consultation.client.email,
        client_name=f"{consultation.client.first_name} {consultation.client.last_name}",
        professional_email=consultation.professional.email,
        professional_name=f"{consultation.professional.first_name} {consultation.professional.last_name}",
        service_name=consultation.rate_card.service_name,
        service_type=consultation.rate_card.service_type
    )


@router.put("/{consultation_id}", response_model=ConsultationResponse)
async def update_consultation(
    consultation_id: int,
    update_data: ConsultationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update consultation status or meeting link."""
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    # Check permissions (professional or admin can confirm, client can cancel)
    if update_data.status:
        if update_data.status == ConsultationStatus.CONFIRMED.value:
            if consultation.professional_id != current_user.id:
                raise HTTPException(status_code=403, detail="Only professional can confirm")
        elif update_data.status == ConsultationStatus.CANCELLED.value:
            if consultation.client_id != current_user.id and consultation.professional_id != current_user.id:
                raise HTTPException(status_code=403, detail="Cannot cancel")

    if update_data.status:
        consultation.status = update_data.status
        if update_data.status == ConsultationStatus.COMPLETED.value:
            consultation.completed_at = datetime.utcnow()

    if update_data.meeting_link:
        consultation.meeting_link = update_data.meeting_link

    if update_data.notes is not None:
        consultation.notes = update_data.notes

    db.commit()
    db.refresh(consultation)

    return consultation


@router.delete("/{consultation_id}")
async def cancel_consultation(
    consultation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a consultation."""
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    # Check access
    if (consultation.client_id != current_user.id and
        consultation.professional_id != current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Can't cancel completed consultations
    if consultation.status == ConsultationStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Cannot cancel completed consultation")

    consultation.status = ConsultationStatus.CANCELLED.value
    db.commit()

    return {"message": "Consultation cancelled"}


@router.get("/professional/{professional_id}/available", response_model=List[dict])
async def get_available_slots(
    professional_id: int,
    date: datetime,
    db: Session = Depends(get_db)
):
    """Get available consultation slots for a professional on a given date."""
    # Get professional's booked consultations for that day
    booked = db.query(Consultation).filter(
        Consultation.professional_id == professional_id,
        Consultation.scheduled_at >= date.replace(hour=0, minute=0, second=0),
        Consultation.scheduled_at < date.replace(hour=23, minute=59, second=59),
        Consultation.status != ConsultationStatus.CANCELLED.value
    ).all()

    # Get professional's availability
    professional = db.query(User).filter(User.id == professional_id).first()
    if not professional or not professional.professional_profile:
        raise HTTPException(status_code=404, detail="Professional not found")

    availability = professional.professional_profile.availability_json or {}

    # Simple availability: generate 1-hour slots during working hours
    slots = []
    for hour in range(9, 18):  # 9 AM to 5 PM
        slot_start = date.replace(hour=hour, minute=0, second=0)
        slot_end = slot_start + timedelta(hours=1)

        # Check if slot is booked
        is_booked = any(
            b.scheduled_at <= slot_start < b.scheduled_at + timedelta(minutes=b.duration_minutes)
            for b in booked
        )

        if not is_booked:
            slots.append({
                "start": slot_start,
                "end": slot_end,
                "available": True
            })

    return slots
