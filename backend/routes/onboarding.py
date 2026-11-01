"""
Onboarding routes: questionnaire and results.
"""

from fastapi import APIRouter, HTTPException, Depends, Cookie
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import json

from database import get_db
from models import User, OnboardingResult
from auth import get_session
from tax_calculator import TaxCalculator

router = APIRouter()


class OnboardingQuestionnaireRequest(BaseModel):
    annual_net_profit: float
    current_entity_type: str
    state: str
    pays_payroll_provider: bool


class OnboardingResultResponse(BaseModel):
    id: int
    annual_net_profit: float
    current_entity_type: str
    state: str
    estimated_annual_savings_min: float
    estimated_annual_savings_max: float
    assumptions: dict
    created_at: str

    class Config:
        from_attributes = True


def get_current_user(session: Optional[str] = Cookie(None), db: Session = Depends(get_db)) -> User:
    """Get current logged-in user (used for route dependency)."""
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Session expired")

    user = db.query(User).filter(User.id == session_data["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.post("/questionnaire", response_model=dict)
async def submit_questionnaire(
    request: OnboardingQuestionnaireRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit onboarding questionnaire and get S-Corp savings estimate.
    """
    try:
        # Calculate savings using tax calculator
        result = TaxCalculator.estimate_savings(
            annual_net_profit=request.annual_net_profit,
            current_entity_type=request.current_entity_type,
            state=request.state,
            pays_payroll_provider=request.pays_payroll_provider,
        )

        # Store result in database
        onboarding = OnboardingResult(
            user_id=current_user.id,
            annual_net_profit=request.annual_net_profit,
            current_entity_type=request.current_entity_type,
            state=request.state,
            pays_payroll_provider=request.pays_payroll_provider,
            estimated_annual_savings_min=result.net_annual_savings_min,
            estimated_annual_savings_max=result.net_annual_savings_max,
            assumptions_json=result.assumptions,
        )
        db.add(onboarding)
        db.commit()
        db.refresh(onboarding)

        # Return detailed result
        return {
            "id": onboarding.id,
            "annual_net_profit": result.annual_net_profit,
            "current_entity_type": result.current_entity_type.value,
            "state": result.state,
            "current_se_tax_annual": round(result.current_se_tax_annual, 2),
            "recommended_w2_salary": round(result.recommended_w2_salary, 2),
            "estimated_se_tax_with_scorp": round(result.estimated_se_tax_with_scorp, 2),
            "gross_tax_savings": round(result.gross_tax_savings, 2),
            "estimated_annual_costs": round(result.estimated_annual_costs, 2),
            "net_annual_savings": round(result.net_annual_savings, 2),
            "net_annual_savings_min": round(result.net_annual_savings_min, 2),
            "net_annual_savings_max": round(result.net_annual_savings_max, 2),
            "assumptions": result.assumptions,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/results", response_model=list)
async def get_results(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all onboarding results for current user."""
    results = db.query(OnboardingResult).filter(
        OnboardingResult.user_id == current_user.id
    ).order_by(OnboardingResult.created_at.desc()).all()

    return [
        {
            "id": r.id,
            "annual_net_profit": r.annual_net_profit,
            "current_entity_type": r.current_entity_type,
            "state": r.state,
            "estimated_annual_savings_min": r.estimated_annual_savings_min,
            "estimated_annual_savings_max": r.estimated_annual_savings_max,
            "assumptions": r.assumptions_json,
            "created_at": r.created_at.isoformat(),
        }
        for r in results
    ]


@router.get("/results/{result_id}")
async def get_result_detail(
    result_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific onboarding result."""
    result = db.query(OnboardingResult).filter(
        OnboardingResult.id == result_id,
        OnboardingResult.user_id == current_user.id
    ).first()

    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    return {
        "id": result.id,
        "annual_net_profit": result.annual_net_profit,
        "current_entity_type": result.current_entity_type,
        "state": result.state,
        "estimated_annual_savings_min": result.estimated_annual_savings_min,
        "estimated_annual_savings_max": result.estimated_annual_savings_max,
        "assumptions": result.assumptions_json,
        "created_at": result.created_at.isoformat(),
    }
