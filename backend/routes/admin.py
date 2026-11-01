"""
Admin routes: member list and onboarding results.
"""

from fastapi import APIRouter, HTTPException, Depends, Cookie
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models import User, OnboardingResult
from auth import get_session

router = APIRouter()


def get_current_admin(session: Optional[str] = Cookie(None), db: Session = Depends(get_db)) -> User:
    """Get current admin user (for MVP, all authenticated users can access)."""
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Session expired")

    user = db.query(User).filter(User.id == session_data["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.get("/members")
async def list_members(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """List all members."""
    users = db.query(User).all()

    return [
        {
            "id": u.id,
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.get("/members/{user_id}/results")
async def get_member_results(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get onboarding results for a member."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    results = db.query(OnboardingResult).filter(
        OnboardingResult.user_id == user_id
    ).order_by(OnboardingResult.created_at.desc()).all()

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        },
        "results": [
            {
                "id": r.id,
                "annual_net_profit": r.annual_net_profit,
                "current_entity_type": r.current_entity_type,
                "state": r.state,
                "estimated_annual_savings_min": r.estimated_annual_savings_min,
                "estimated_annual_savings_max": r.estimated_annual_savings_max,
                "created_at": r.created_at.isoformat(),
            }
            for r in results
        ]
    }


@router.get("/dashboard")
async def admin_dashboard(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get admin dashboard summary."""
    total_users = db.query(User).count()
    total_results = db.query(OnboardingResult).count()

    # Get latest results
    latest_results = db.query(OnboardingResult).order_by(
        OnboardingResult.created_at.desc()
    ).limit(10).all()

    return {
        "total_users": total_users,
        "total_results": total_results,
        "latest_results": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "annual_net_profit": r.annual_net_profit,
                "estimated_annual_savings_min": r.estimated_annual_savings_min,
                "estimated_annual_savings_max": r.estimated_annual_savings_max,
                "created_at": r.created_at.isoformat(),
            }
            for r in latest_results
        ]
    }
