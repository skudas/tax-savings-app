"""
Tax filing, deduction, and optimization API routes.

Mounted at /api/tax. All endpoints require a valid session cookie unless
otherwise noted. Calculations are delegated to tax_engine.py.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Cookie, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from auth import get_session
from database import get_db
from models import (
    AuditDoc,
    Deduction,
    DeductionRule,
    EfileSubmission,
    EstimatedTax,
    Investment,
    InvestmentSale,
    RetirementAccount,
    SelfEmploymentIncome,
    StateReturn,
    TaxForm,
    TaxReturn,
    User,
)
import tax_engine

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "static" / "uploads" / "audit"
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
ALLOWED_UPLOAD_TYPES = {
    "application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp",
    "text/csv", "text/plain", "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
VALID_FILING_STATUSES = set(tax_engine.FILING_STATUS_LABELS)
VALID_ENTITY_TYPES = {"sole_proprietor", "llc", "s_corp", "c_corp", "partnership"}
ITEMIZED_CATEGORIES = {"charitable", "mortgage_interest", "state_taxes"}
PASS_THROUGH_ABOVE_LINE = {"retirement", "health_insurance"}


# ---------------------------------------------------------------------------
# Dependencies & shared helpers
# ---------------------------------------------------------------------------


def get_current_user(session: Optional[str] = Cookie(None), db: Session = Depends(get_db)) -> User:
    """Resolve the logged-in user from the session cookie."""
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Session expired")
    user = db.query(User).filter(User.id == session_data["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _rule_rows(db: Session) -> List[DeductionRule]:
    return db.query(DeductionRule).filter(DeductionRule.active.is_(True)).all()


def _rule_map(db: Session) -> Dict[str, DeductionRule]:
    return {rule.category: rule for rule in _rule_rows(db)}


def _rule_dict(rule: DeductionRule) -> Dict[str, Any]:
    return {
        "category": rule.category,
        "description": rule.description,
        "max_amount": rule.max_amount,
        "percentage_limit": rule.percentage_limit,
        "limit_basis": rule.limit_basis,
        "irs_code": rule.irs_code,
        "deduction_type": rule.deduction_type,
        "income_types": rule.income_types or [],
        "common_questions": rule.common_questions or [],
        "documentation_required": rule.documentation_required or [],
        "active": rule.active,
    }


def seed_deduction_rules(db: Session) -> int:
    """Insert any missing default deduction rules. Returns count created."""
    existing = {row.category for row in db.query(DeductionRule).all()}
    created = 0
    for item in tax_engine.DEFAULT_DEDUCTION_RULES:
        if item["category"] in existing:
            continue
        db.add(DeductionRule(
            category=item["category"],
            description=item["description"],
            max_amount=item.get("max_amount"),
            percentage_limit=item.get("percentage_limit"),
            limit_basis=item.get("limit_basis", "absolute"),
            irs_code=item.get("irs_code"),
            deduction_type=item.get("deduction_type", "business"),
            income_types=item.get("income_types") or [],
            common_questions=item.get("common_questions") or [],
            documentation_required=item.get("documentation_required") or [],
        ))
        created += 1
    if created:
        db.commit()
    return created


def _get_return(db: Session, user: User, return_id: int) -> TaxReturn:
    tax_return = db.query(TaxReturn).filter(
        TaxReturn.id == return_id,
        TaxReturn.user_id == user.id,
    ).first()
    if not tax_return:
        raise HTTPException(status_code=404, detail="Tax return not found")
    return tax_return


def _parse_date(value: Any, field_name: str = "date") -> date:
    parsed = tax_engine._to_date(value)
    if not parsed:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}: {value!r}")
    return parsed


def _serialize_form(form: TaxForm, include_data: bool = True) -> Dict[str, Any]:
    payload = {
        "id": form.id,
        "tax_return_id": form.tax_return_id,
        "form_type": form.form_type,
        "form_name": form.form_name,
        "completed_bool": form.completed_bool,
        "generated_at": form.generated_at.isoformat() if form.generated_at else None,
    }
    if include_data:
        payload["data"] = form.data
    return payload


def _serialize_deduction(deduction: Deduction, rule: Optional[DeductionRule] = None) -> Dict[str, Any]:
    return {
        "id": deduction.id,
        "tax_return_id": deduction.tax_return_id,
        "tax_year": deduction.tax_year,
        "category": deduction.category,
        "amount": deduction.amount,
        "description": deduction.description,
        "receipt_url": deduction.receipt_url,
        "verified_bool": deduction.verified_bool,
        "documentation_status": deduction.documentation_status,
        "source": deduction.source,
        "irs_code": deduction.irs_code or (rule.irs_code if rule else None),
        "deduction_type": rule.deduction_type if rule else None,
        "created_at": deduction.created_at.isoformat() if deduction.created_at else None,
    }


def _serialize_return(tax_return: TaxReturn, db: Session, include_children: bool = False) -> Dict[str, Any]:
    forms = db.query(TaxForm).filter(TaxForm.tax_return_id == tax_return.id).all()
    deductions = db.query(Deduction).filter(Deduction.tax_return_id == tax_return.id).all()
    progress = tax_engine.return_progress(
        forms=[{"completed_bool": f.completed_bool} for f in forms],
        deductions=[{"id": d.id} for d in deductions],
        status=tax_return.status,
    )
    payload = {
        "id": tax_return.id,
        "user_id": tax_return.user_id,
        "tax_year": tax_return.tax_year,
        "filing_status": tax_return.filing_status,
        "filing_status_label": tax_engine.FILING_STATUS_LABELS.get(tax_return.filing_status, tax_return.filing_status),
        "entity_type": tax_return.entity_type,
        "state": tax_return.state,
        "status": tax_return.status,
        "w2_wages": tax_return.w2_wages,
        "federal_withholding": tax_return.federal_withholding,
        "self_employment_income": tax_return.self_employment_income,
        "rental_income": tax_return.rental_income,
        "other_income": tax_return.other_income,
        "capital_gains": tax_return.capital_gains,
        "retirement_contributions": tax_return.retirement_contributions,
        "health_insurance_premiums": tax_return.health_insurance_premiums,
        "total_income": tax_return.total_income,
        "total_deductions": tax_return.total_deductions,
        "taxable_income": tax_return.taxable_income,
        "estimated_tax": tax_return.estimated_tax,
        "total_payments": tax_return.total_payments,
        "refund_or_owed": tax_return.refund_or_owed,
        "notes": tax_return.notes,
        "created_at": tax_return.created_at.isoformat() if tax_return.created_at else None,
        "updated_at": tax_return.updated_at.isoformat() if tax_return.updated_at else None,
        "filed_at": tax_return.filed_at.isoformat() if tax_return.filed_at else None,
        "progress": progress,
        "forms_count": len(forms),
        "deductions_count": len(deductions),
    }
    if include_children:
        payload["forms"] = [_serialize_form(f) for f in forms]
        rules = _rule_map(db)
        payload["deductions"] = [_serialize_deduction(d, rules.get(d.category)) for d in deductions]
        payload["self_employment"] = [
            {
                "id": row.id,
                "business_name": row.business_name,
                "gross_revenue": row.gross_revenue,
                "expenses": row.expenses,
                "cost_of_goods_sold": row.cost_of_goods_sold,
                "net_profit": row.net_profit,
                "schedule_c_data": row.schedule_c_data or {},
            }
            for row in db.query(SelfEmploymentIncome).filter(
                SelfEmploymentIncome.tax_return_id == tax_return.id
            ).all()
        ]
        payload["state_returns"] = [
            {
                "id": row.id,
                "state": row.state,
                "residency_status": row.residency_status,
                "income_allocated": row.income_allocated,
                "state_tax": row.state_tax,
                "form_data": row.form_data,
            }
            for row in db.query(StateReturn).filter(StateReturn.tax_return_id == tax_return.id).all()
        ]
        payload["efile_submissions"] = [
            {
                "id": row.id,
                "status": row.status,
                "confirmation_number": row.confirmation_number,
                "submission_id": row.submission_id,
                "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
                "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
            }
            for row in db.query(EfileSubmission).filter(EfileSubmission.tax_return_id == tax_return.id).all()
        ]
    return payload


def _se_net_profit(db: Session, tax_return: TaxReturn) -> tuple:
    rows = db.query(SelfEmploymentIncome).filter(
        SelfEmploymentIncome.user_id == tax_return.user_id,
        (SelfEmploymentIncome.tax_return_id == tax_return.id) |
        ((SelfEmploymentIncome.tax_return_id.is_(None)) & (SelfEmploymentIncome.tax_year == tax_return.tax_year)),
    ).all()
    if rows:
        return sum(row.net_profit for row in rows), rows
    return float(tax_return.self_employment_income or 0.0), []


def _capital_gain_totals(db: Session, tax_return: TaxReturn) -> Dict[str, float]:
    sales = db.query(InvestmentSale).filter(
        InvestmentSale.user_id == tax_return.user_id,
        InvestmentSale.tax_year == tax_return.tax_year,
    ).all()
    if not sales:
        return {"short": 0.0, "long": float(tax_return.capital_gains or 0.0), "rows": []}
    summary = tax_engine.calculate_capital_gains(
        [{"symbol": s.symbol, "proceeds": s.proceeds, "cost_basis": s.cost_basis,
          "purchase_date": s.purchase_date, "sale_date": s.sale_date} for s in sales],
        tax_return.tax_year,
        tax_return.filing_status,
    )
    return {
        "short": summary["short_term_gain"],
        "long": summary["long_term_gain"],
        "rows": summary["rows"],
        "summary": summary,
    }


def _compute_return(db: Session, tax_return: TaxReturn) -> Dict[str, Any]:
    """Recalculate a return and persist the dashboard summary fields."""
    rules = _rule_map(db)
    deductions = db.query(Deduction).filter(
        Deduction.user_id == tax_return.user_id,
        (Deduction.tax_return_id == tax_return.id) |
        ((Deduction.tax_return_id.is_(None)) & (Deduction.tax_year == tax_return.tax_year)),
    ).all()

    business_total = 0.0
    above_line_total = 0.0
    itemized_total = 0.0
    retirement_from_deductions = 0.0
    health_from_deductions = 0.0
    for deduction in deductions:
        rule = rules.get(deduction.category)
        amount = float(deduction.amount or 0)
        if not rule:
            above_line_total += amount
            continue
        if rule.deduction_type == "business":
            business_total += amount
        elif rule.deduction_type == "itemized" or deduction.category in ITEMIZED_CATEGORIES:
            itemized_total += amount
        elif rule.deduction_type == "above_line":
            if deduction.category == "retirement":
                retirement_from_deductions += amount
            elif deduction.category == "health_insurance":
                health_from_deductions += amount
            else:
                above_line_total += amount
        else:
            above_line_total += amount

    se_net, _ = _se_net_profit(db, tax_return)
    gains = _capital_gain_totals(db, tax_return)
    retirement = retirement_from_deductions or float(tax_return.retirement_contributions or 0.0)
    health = health_from_deductions or float(tax_return.health_insurance_premiums or 0.0)

    calculation = tax_engine.calculate_individual_tax(
        tax_year=tax_return.tax_year,
        filing_status=tax_return.filing_status,
        w2_wages=tax_return.w2_wages or 0.0,
        self_employment_income=se_net,
        rental_income=tax_return.rental_income or 0.0,
        other_income=tax_return.other_income or 0.0,
        capital_gains_short=gains["short"],
        capital_gains_long=gains["long"],
        itemized_deductions=itemized_total,
        above_line_deductions=above_line_total,
        retirement_contributions=retirement,
        health_insurance_premiums=health,
        federal_withholding=tax_return.federal_withholding or 0.0,
    )

    tax_return.total_income = calculation["income"]["total_income"]
    tax_return.total_deductions = round(
        calculation["deduction"]["applied"] + calculation["adjustments"]["total"] + business_total, 2
    )
    tax_return.taxable_income = calculation["taxable_income"]
    tax_return.estimated_tax = calculation["tax"]["total_tax"]
    tax_return.total_payments = calculation["payments"]["total"]
    tax_return.refund_or_owed = calculation["refund_or_owed"]
    db.commit()
    db.refresh(tax_return)

    calculation["deduction_breakdown"] = {
        "business": round(business_total, 2),
        "above_line": round(calculation["adjustments"]["total"], 2),
        "itemized": round(itemized_total, 2),
        "standard_or_itemized_applied": calculation["deduction"]["applied"],
    }
    calculation["business_income"] = {
        "net_profit": round(se_net, 2),
        "has_schedule_c": bool(se_net),
    }
    calculation["capital_gains"] = gains.get("summary") or {
        "short_term_gain": gains["short"], "long_term_gain": gains["long"], "net_gain": gains["short"] + gains["long"]
    }
    return calculation


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------


class TaxReturnCreate(BaseModel):
    tax_year: int = Field(..., ge=2000, le=2100)
    filing_status: str = "single"
    entity_type: str = "sole_proprietor"
    state: Optional[str] = Field(None, max_length=2)
    w2_wages: float = 0.0
    federal_withholding: float = 0.0
    self_employment_income: float = 0.0
    rental_income: float = 0.0
    other_income: float = 0.0

    @field_validator("filing_status")
    @classmethod
    def valid_filing_status(cls, value: str) -> str:
        if value not in VALID_FILING_STATUSES:
            raise ValueError(f"filing_status must be one of {sorted(VALID_FILING_STATUSES)}")
        return value

    @field_validator("entity_type")
    @classmethod
    def valid_entity_type(cls, value: str) -> str:
        if value not in VALID_ENTITY_TYPES:
            raise ValueError(f"entity_type must be one of {sorted(VALID_ENTITY_TYPES)}")
        return value


class TaxReturnUpdate(BaseModel):
    filing_status: Optional[str] = None
    entity_type: Optional[str] = None
    state: Optional[str] = Field(None, max_length=2)
    status: Optional[str] = None
    w2_wages: Optional[float] = None
    federal_withholding: Optional[float] = None
    self_employment_income: Optional[float] = None
    rental_income: Optional[float] = None
    other_income: Optional[float] = None
    capital_gains: Optional[float] = None
    retirement_contributions: Optional[float] = None
    health_insurance_premiums: Optional[float] = None
    notes: Optional[str] = None


class DeductionCreate(BaseModel):
    tax_return_id: Optional[int] = None
    tax_year: Optional[int] = Field(None, ge=2000, le=2100)
    category: str
    amount: float = Field(..., gt=0)
    description: Optional[str] = None
    receipt_url: Optional[str] = None
    source: str = "manual"
    verified_bool: bool = False


class DeductionUpdate(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    description: Optional[str] = None
    receipt_url: Optional[str] = None
    verified_bool: Optional[bool] = None


class QuestionnaireRequest(BaseModel):
    income_type: str = "self_employed"
    tax_year: int = Field(default_factory=lambda: date.today().year - 1)
    gross_income: float = 0.0
    net_profit: float = 0.0
    tax_return_id: Optional[int] = None


class FormGenerateRequest(BaseModel):
    tax_return_id: int
    forms: Optional[List[str]] = None
    include_1040es: bool = False
    prior_year_tax: Optional[float] = None
    prior_year_agi: Optional[float] = None
    election_target: Optional[str] = None


class EntityComparisonRequest(BaseModel):
    annual_revenue: float = Field(..., ge=0)
    annual_expenses: float = Field(0, ge=0)
    tax_year: int = Field(default_factory=lambda: date.today().year)
    filing_status: str = "single"
    state: str = ""
    owner_w2_salary: Optional[float] = Field(None, ge=0)
    other_income: float = Field(0, ge=0)


class EstimatedTaxRequest(BaseModel):
    tax_year: int = Field(default_factory=lambda: date.today().year)
    filing_status: str = "single"
    tax_return_id: Optional[int] = None
    projected_total_tax: Optional[float] = Field(None, ge=0)
    net_profit: Optional[float] = Field(None, ge=0)
    prior_year_tax: Optional[float] = Field(None, ge=0)
    prior_year_agi: Optional[float] = None
    withholding: float = Field(0, ge=0)
    reminders_enabled: bool = True


class AuditDocCreate(BaseModel):
    tax_year: int = Field(..., ge=2000, le=2100)
    category: str
    filename: str
    file_url: str
    mime_type: Optional[str] = None
    file_size: int = 0
    notes: Optional[str] = None


class SelfEmploymentCreate(BaseModel):
    tax_return_id: Optional[int] = None
    tax_year: int = Field(..., ge=2000, le=2100)
    business_name: Optional[str] = None
    business_code: Optional[str] = None
    gross_revenue: float = Field(0, ge=0)
    expenses: float = Field(0, ge=0)
    cost_of_goods_sold: float = Field(0, ge=0)
    schedule_c_data: Optional[dict] = None


class InvestmentCreate(BaseModel):
    symbol: str
    name: Optional[str] = None
    asset_type: str = "stock"
    quantity: float = Field(0, ge=0)
    purchase_date: str
    cost_basis: float = Field(..., ge=0)
    current_value: Optional[float] = None


class SaleCreate(BaseModel):
    investment_id: Optional[int] = None
    tax_year: int = Field(default_factory=lambda: date.today().year)
    symbol: str
    description: Optional[str] = None
    purchase_date: str
    sale_date: str
    proceeds: float = Field(..., ge=0)
    cost_basis: float = Field(..., ge=0)


class WhatIfRequest(BaseModel):
    symbol: str = "Position"
    proceeds: float = Field(..., ge=0)
    cost_basis: float = Field(..., ge=0)
    purchase_date: str
    sale_date: str
    tax_year: int = Field(default_factory=lambda: date.today().year)
    filing_status: str = "single"
    ordinary_income: float = Field(0, ge=0)


class RetirementCompareRequest(BaseModel):
    tax_year: int = Field(default_factory=lambda: date.today().year)
    net_self_employment_income: float = Field(..., ge=0)
    marginal_tax_rate: Optional[float] = Field(None, ge=0, le=1)
    age: int = Field(40, ge=18, le=100)
    filing_status: str = "single"


class RetirementAccountCreate(BaseModel):
    tax_year: int = Field(default_factory=lambda: date.today().year)
    account_type: str
    provider: Optional[str] = None
    contributed_amount: float = Field(0, ge=0)
    balance: float = Field(0, ge=0)


class StateAllocation(BaseModel):
    state: str = Field(..., min_length=2, max_length=2)
    income: float = Field(..., ge=0)
    residency_status: str = "resident"


class MultiStateRequest(BaseModel):
    tax_year: int = Field(default_factory=lambda: date.today().year)
    tax_return_id: Optional[int] = None
    allocations: List[StateAllocation] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Tax returns
# ---------------------------------------------------------------------------


@router.post("/returns/new")
async def create_tax_return(
    request: TaxReturnCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new tax return for a user and tax year."""
    duplicate = db.query(TaxReturn).filter(
        TaxReturn.user_id == current_user.id,
        TaxReturn.tax_year == request.tax_year,
        TaxReturn.filing_status == request.filing_status,
        TaxReturn.entity_type == request.entity_type,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail=f"A return already exists for {request.tax_year} (id={duplicate.id})")

    tax_return = TaxReturn(
        user_id=current_user.id,
        tax_year=request.tax_year,
        filing_status=request.filing_status,
        entity_type=request.entity_type,
        state=(request.state or "").upper() or None,
        w2_wages=request.w2_wages,
        federal_withholding=request.federal_withholding,
        self_employment_income=request.self_employment_income,
        rental_income=request.rental_income,
        other_income=request.other_income,
    )
    db.add(tax_return)
    db.commit()
    db.refresh(tax_return)
    _compute_return(db, tax_return)
    return _serialize_return(tax_return, db, include_children=True)


@router.get("/returns")
async def list_tax_returns(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all tax returns for the current user."""
    returns = db.query(TaxReturn).filter(
        TaxReturn.user_id == current_user.id
    ).order_by(TaxReturn.tax_year.desc(), TaxReturn.created_at.desc()).all()
    return [_serialize_return(row, db) for row in returns]


@router.get("/returns/{return_id}")
async def get_tax_return(
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a tax return with its forms, deductions, and calculations."""
    tax_return = _get_return(db, current_user, return_id)
    calculation = _compute_return(db, tax_return)
    payload = _serialize_return(tax_return, db, include_children=True)
    payload["calculation"] = calculation
    return payload


@router.patch("/returns/{return_id}")
async def update_tax_return(
    return_id: int,
    request: TaxReturnUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update return inputs or status."""
    tax_return = _get_return(db, current_user, return_id)
    updates = request.model_dump(exclude_unset=True)
    if "filing_status" in updates and updates["filing_status"] not in VALID_FILING_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid filing status")
    if "entity_type" in updates and updates["entity_type"] not in VALID_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail="Invalid entity type")
    if "state" in updates and updates["state"]:
        updates["state"] = updates["state"].upper()
    for key, value in updates.items():
        setattr(tax_return, key, value)
    if updates.get("status") == "filed" and not tax_return.filed_at:
        tax_return.filed_at = datetime.utcnow()
    db.commit()
    _compute_return(db, tax_return)
    return _serialize_return(tax_return, db, include_children=True)


@router.post("/returns/{return_id}/recalculate")
async def recalculate_tax_return(
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recalculate totals for a return without generating forms."""
    tax_return = _get_return(db, current_user, return_id)
    calculation = _compute_return(db, tax_return)
    return {"return": _serialize_return(tax_return, db), "calculation": calculation}


# ---------------------------------------------------------------------------
# Deductions & questionnaire
# ---------------------------------------------------------------------------


@router.post("/deductions/questionnaire")
async def start_deduction_questionnaire(
    request: QuestionnaireRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Start the smart deduction interview.

    Returns the relevant sections, IRS limits, documentation requirements, and
    an estimated benefit for the user's income type.
    """
    seed_deduction_rules(db)
    income_type = request.income_type
    if request.tax_return_id:
        tax_return = _get_return(db, current_user, request.tax_return_id)
        income_type = "self_employed" if tax_return.self_employment_income else (
            "rental" if tax_return.rental_income else ("w2" if tax_return.w2_wages else income_type)
        )
    rules = [_rule_dict(rule) for rule in _rule_rows(db)]
    questionnaire = tax_engine.deduction_questionnaire(income_type, rules)
    gross = request.gross_income
    net = request.net_profit or request.gross_income
    for section in questionnaire["sections"]:
        section["estimated_max_savings"] = round(
            min(
                section["max_amount"] if section.get("max_amount") else (gross * 0.10),
                gross * 0.25,
            ) * section.pop("estimated_savings_rate", 0.25),
            2,
        )
        rule = next((r for r in rules if r["category"] == section["category"]), None)
        if rule:
            section["suggested_deduction"] = round(
                min(
                    rule["max_amount"] if rule.get("max_amount") else max(0.0, net) * 0.05,
                    max(0.0, net),
                ), 2
            )
    questionnaire["respondent"] = {"user_id": current_user.id, "tax_year": request.tax_year}
    questionnaire["answered_count"] = db.query(Deduction).filter(
        Deduction.user_id == current_user.id,
        Deduction.tax_year == request.tax_year,
    ).count()
    return questionnaire


@router.post("/deductions")
async def add_deduction(
    request: DeductionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Claim a deduction after validating it against IRS limits."""
    seed_deduction_rules(db)
    rule = db.query(DeductionRule).filter(DeductionRule.category == request.category).first()

    tax_year = request.tax_year or date.today().year - 1
    tax_return = None
    if request.tax_return_id:
        tax_return = _get_return(db, current_user, request.tax_return_id)
        tax_year = tax_return.tax_year

    gross = 0.0
    net = 0.0
    if tax_return:
        gross = float(tax_return.w2_wages or 0) + float(tax_return.self_employment_income or 0)
        net, _ = _se_net_profit(db, tax_return)
    validation = tax_engine.validate_deduction(
        request.category,
        request.amount,
        gross_income=gross,
        net_profit=net,
        rule=_rule_dict(rule) if rule else None,
    )
    documentation_status = "complete" if request.receipt_url else ("partial" if request.verified_bool else "missing")

    deduction = Deduction(
        user_id=current_user.id,
        tax_return_id=request.tax_return_id,
        tax_year=tax_year,
        category=request.category,
        amount=request.amount,
        description=request.description,
        receipt_url=request.receipt_url,
        verified_bool=request.verified_bool,
        documentation_status=documentation_status,
        source=request.source,
        irs_code=rule.irs_code if rule else None,
    )
    db.add(deduction)
    db.commit()
    db.refresh(deduction)

    if tax_return:
        _compute_return(db, tax_return)

    return {
        "deduction": _serialize_deduction(deduction, rule),
        "validation": validation,
        "rule": _rule_dict(rule) if rule else None,
    }


@router.get("/deductions")
async def list_deductions(
    tax_year: Optional[int] = None,
    tax_return_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List deductions with totals grouped by category."""
    query = db.query(Deduction).filter(Deduction.user_id == current_user.id)
    if tax_year:
        query = query.filter(Deduction.tax_year == tax_year)
    if tax_return_id:
        tax_return = _get_return(db, current_user, tax_return_id)
        query = query.filter(
            (Deduction.tax_return_id == tax_return.id) | (Deduction.tax_year == tax_return.tax_year)
        )
    deductions = query.order_by(Deduction.created_at.desc()).all()
    rules = _rule_map(db)
    category_totals: Dict[str, float] = {}
    for row in deductions:
        category_totals[row.category] = round(category_totals.get(row.category, 0.0) + row.amount, 2)
    return {
        "deductions": [_serialize_deduction(row, rules.get(row.category)) for row in deductions],
        "total": round(sum(row.amount for row in deductions), 2),
        "by_category": category_totals,
        "count": len(deductions),
    }


@router.get("/deductions/rules")
async def list_deduction_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the IRS-aware deduction rule catalog."""
    seed_deduction_rules(db)
    return [_rule_dict(rule) for rule in _rule_rows(db)]


@router.patch("/deductions/{deduction_id}")
async def update_deduction(
    deduction_id: int,
    request: DeductionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a claimed deduction."""
    deduction = db.query(Deduction).filter(
        Deduction.id == deduction_id,
        Deduction.user_id == current_user.id,
    ).first()
    if not deduction:
        raise HTTPException(status_code=404, detail="Deduction not found")
    updates = request.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(deduction, key, value)
    if "receipt_url" in updates or "verified_bool" in updates:
        deduction.documentation_status = "complete" if deduction.receipt_url else ("partial" if deduction.verified_bool else "missing")
    db.commit()
    if deduction.tax_return_id:
        tax_return = _get_return(db, current_user, deduction.tax_return_id)
        _compute_return(db, tax_return)
    return _serialize_deduction(deduction, _rule_map(db).get(deduction.category))


@router.delete("/deductions/{deduction_id}")
async def delete_deduction(
    deduction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a claimed deduction."""
    deduction = db.query(Deduction).filter(
        Deduction.id == deduction_id,
        Deduction.user_id == current_user.id,
    ).first()
    if not deduction:
        raise HTTPException(status_code=404, detail="Deduction not found")
    tax_return_id = deduction.tax_return_id
    db.delete(deduction)
    db.commit()
    if tax_return_id:
        tax_return = db.query(TaxReturn).filter(TaxReturn.id == tax_return_id).first()
        if tax_return:
            _compute_return(db, tax_return)
    return {"message": "Deduction removed", "id": deduction_id}


# ---------------------------------------------------------------------------
# Self-employment income
# ---------------------------------------------------------------------------


@router.post("/self-employment")
async def add_self_employment(
    request: SelfEmploymentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add Schedule C business income for a tax year."""
    if request.tax_return_id:
        _get_return(db, current_user, request.tax_return_id)
    row = SelfEmploymentIncome(
        user_id=current_user.id,
        tax_return_id=request.tax_return_id,
        tax_year=request.tax_year,
        business_name=request.business_name,
        business_code=request.business_code,
        gross_revenue=request.gross_revenue,
        expenses=request.expenses,
        cost_of_goods_sold=request.cost_of_goods_sold,
        schedule_c_data=request.schedule_c_data or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    if request.tax_return_id:
        tax_return = _get_return(db, current_user, request.tax_return_id)
        _compute_return(db, tax_return)
    return {
        "id": row.id,
        "business_name": row.business_name,
        "gross_revenue": row.gross_revenue,
        "expenses": row.expenses,
        "cost_of_goods_sold": row.cost_of_goods_sold,
        "net_profit": row.net_profit,
        "schedule_c_data": row.schedule_c_data,
    }


@router.get("/self-employment")
async def list_self_employment(
    tax_year: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List self-employment income records."""
    query = db.query(SelfEmploymentIncome).filter(SelfEmploymentIncome.user_id == current_user.id)
    if tax_year:
        query = query.filter(SelfEmploymentIncome.tax_year == tax_year)
    rows = query.order_by(SelfEmploymentIncome.tax_year.desc()).all()
    return [
        {
            "id": row.id,
            "tax_year": row.tax_year,
            "tax_return_id": row.tax_return_id,
            "business_name": row.business_name,
            "gross_revenue": row.gross_revenue,
            "expenses": row.expenses,
            "cost_of_goods_sold": row.cost_of_goods_sold,
            "net_profit": row.net_profit,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Form generation
# ---------------------------------------------------------------------------


@router.post("/forms/generate")
async def generate_forms(
    request: FormGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate JSON/PDF-ready tax forms for a return."""
    tax_return = _get_return(db, current_user, request.tax_return_id)
    calculation = _compute_return(db, tax_return)
    rules = _rule_map(db)
    deductions = db.query(Deduction).filter(Deduction.user_id == current_user.id).filter(
        (Deduction.tax_return_id == tax_return.id) | (Deduction.tax_year == tax_return.tax_year)
    ).all()
    business_expenses = sum(
        float(d.amount or 0) for d in deductions
        if (rules.get(d.category) and rules[d.category].deduction_type == "business")
    )
    se_net, se_rows = _se_net_profit(db, tax_return)
    gains = _capital_gain_totals(db, tax_return)
    taxpayer = {
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "email": current_user.email,
    }

    requested = {f.lower().replace("-", "_") for f in (request.forms or [])}
    generate_all = not requested
    payloads: List[Dict[str, Any]] = []

    def wanted(form_type: str, condition: bool) -> bool:
        return generate_all and condition or form_type in requested

    if wanted("1040", True):
        payloads.append(tax_engine.generate_form_1040(calculation, taxpayer=taxpayer, tax_year=tax_return.tax_year))

    if wanted("schedule_c", se_net != 0):
        se_row = se_rows[0] if se_rows else None
        payloads.append(tax_engine.generate_schedule_c(
            tax_year=tax_return.tax_year,
            business_name=se_row.business_name if se_row else None,
            gross_revenue=se_row.gross_revenue if se_row else se_net,
            expenses=se_row.expenses if se_row else business_expenses,
            cost_of_goods_sold=se_row.cost_of_goods_sold if se_row else 0.0,
            schedule_c_data=(se_row.schedule_c_data if se_row else None) or {},
            owner=taxpayer,
        ))

    if wanted("schedule_se", se_net != 0):
        payloads.append(tax_engine.generate_schedule_se(
            tax_year=tax_return.tax_year,
            net_profit=se_net,
            w2_wages=tax_return.w2_wages or 0.0,
            filing_status=tax_return.filing_status,
        ))

    if wanted("schedule_e", bool(tax_return.rental_income)):
        payloads.append(tax_engine.generate_schedule_e(
            tax_year=tax_return.tax_year,
            rental_income=tax_return.rental_income or 0.0,
        ))

    if wanted("schedule_d", bool(gains.get("rows")) or bool(tax_return.capital_gains)):
        payloads.append(tax_engine.generate_schedule_d(
            tax_year=tax_return.tax_year,
            sales=gains.get("rows", []),
            ordinary_income=calculation["taxable_income"],
            filing_status=tax_return.filing_status,
        ))

    if "1040nr" in requested or (generate_all and tax_return.notes and "nonresident" in tax_return.notes.lower()):
        payloads.append(tax_engine.generate_form_1040nr(
            tax_year=tax_return.tax_year,
            us_source_income=calculation["income"]["total_income"],
            filing_status=tax_return.filing_status,
        ))

    if "8832" in requested or (generate_all and tax_return.entity_type in {"s_corp", "c_corp", "partnership"}):
        payloads.append(tax_engine.generate_form_8832(
            election_year=tax_return.tax_year,
            current_entity="LLC",
            elected_classification=request.election_target or (
                "S-Corporation" if tax_return.entity_type == "s_corp"
                else "C-Corporation" if tax_return.entity_type == "c_corp" else "Partnership"
            ),
            owner_count=1 if tax_return.entity_type in {"s_corp", "c_corp"} else 2,
        ))

    state_returns = db.query(StateReturn).filter(StateReturn.tax_return_id == tax_return.id).all()
    for state_row in state_returns:
        if generate_all or f"state_{state_row.state.lower()}" in requested:
            payloads.append(tax_engine.generate_state_form(
                tax_year=tax_return.tax_year,
                state=state_row.state,
                residency_status=state_row.residency_status,
                income_allocated=state_row.income_allocated,
                state_tax=state_row.state_tax,
            ))

    if request.include_1040es or "1040es" in requested:
        payloads.append(tax_engine.generate_1040es(
            tax_year=tax_return.tax_year,
            calculation=calculation,
            withholding=calculation["payments"]["withholding"],
            prior_year_tax=request.prior_year_tax,
            prior_year_agi=request.prior_year_agi,
        ))

    if not payloads:
        raise HTTPException(status_code=400, detail="No forms matched the requested types")

    # Replace prior generated copies of the same form types.
    form_types = {p["form_type"] for p in payloads}
    db.query(TaxForm).filter(
        TaxForm.tax_return_id == tax_return.id,
        TaxForm.form_type.in_(form_types),
    ).delete(synchronize_session=False)

    saved = []
    for payload in payloads:
        form = TaxForm(
            tax_return_id=tax_return.id,
            form_type=payload["form_type"],
            form_name=payload["form_name"],
            data=payload,
            completed_bool=True,
        )
        db.add(form)
        saved.append(form)
    if tax_return.status == "draft":
        tax_return.status = "ready_to_file"
    db.commit()
    for form in saved:
        db.refresh(form)

    return {
        "tax_return_id": tax_return.id,
        "generated": [_serialize_form(form) for form in saved],
        "count": len(saved),
        "calculation": calculation,
    }


@router.get("/forms/{form_id}")
async def get_form(
    form_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a generated form as JSON."""
    form = db.query(TaxForm).join(TaxReturn, TaxForm.tax_return_id == TaxReturn.id).filter(
        TaxForm.id == form_id,
        TaxReturn.user_id == current_user.id,
    ).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    payload = _serialize_form(form)
    payload["return"] = {
        "id": form.tax_return.id,
        "tax_year": form.tax_return.tax_year,
        "filing_status": form.tax_return.filing_status,
        "entity_type": form.tax_return.entity_type,
    }
    return payload


@router.get("/returns/{return_id}/forms")
async def list_return_forms(
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List generated forms for a return."""
    tax_return = _get_return(db, current_user, return_id)
    forms = db.query(TaxForm).filter(TaxForm.tax_return_id == tax_return.id).order_by(TaxForm.id.asc()).all()
    return [_serialize_form(form) for form in forms]


# ---------------------------------------------------------------------------
# Entity comparison
# ---------------------------------------------------------------------------


@router.post("/entity-comparison")
async def entity_comparison(
    request: EntityComparisonRequest,
    current_user: User = Depends(get_current_user),
):
    """Compare projected total tax across entity structures."""
    if request.filing_status not in VALID_FILING_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid filing status")
    return tax_engine.compare_entities(
        annual_revenue=request.annual_revenue,
        annual_expenses=request.annual_expenses,
        tax_year=request.tax_year,
        filing_status=request.filing_status,
        state=request.state,
        owner_w2_salary=request.owner_w2_salary,
        other_income=request.other_income,
    )


# ---------------------------------------------------------------------------
# Estimated taxes
# ---------------------------------------------------------------------------


def _serialize_estimated(row: EstimatedTax) -> Dict[str, Any]:
    due_dates = row.due_dates or tax_engine.quarterly_due_dates(row.tax_year)
    paid = row.paid_json or {}
    schedule = []
    for key, amount in (("q1", row.q1_amount), ("q2", row.q2_amount), ("q3", row.q3_amount), ("q4", row.q4_amount)):
        due_iso = due_dates.get(key)
        days = None
        if due_iso:
            try:
                due = date.fromisoformat(due_iso)
                days = (due - date.today()).days
            except ValueError:
                pass
        schedule.append({
            "quarter": key.upper(),
            "amount": round(amount or 0.0, 2),
            "due_date": due_iso,
            "reminder_enabled": row.reminders_enabled,
            "paid": bool(paid.get(key)),
            "days_until_due": days,
        })
    return {
        "id": row.id,
        "tax_year": row.tax_year,
        "q1_amount": row.q1_amount,
        "q2_amount": row.q2_amount,
        "q3_amount": row.q3_amount,
        "q4_amount": row.q4_amount,
        "total_estimated_tax": row.total_estimated_tax,
        "safe_harbor_amount": row.safe_harbor_amount,
        "due_dates": due_dates,
        "reminders_enabled": row.reminders_enabled,
        "paid": paid,
        "schedule": schedule,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("/estimated-taxes")
async def calculate_and_save_estimated(
    request: EstimatedTaxRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Calculate quarterly estimated payments and persist the schedule."""
    projected = request.projected_total_tax
    withholding = request.withholding
    filing_status = request.filing_status
    if request.tax_return_id:
        tax_return = _get_return(db, current_user, request.tax_return_id)
        calculation = _compute_return(db, tax_return)
        projected = calculation["tax"]["total_tax"]
        withholding = calculation["payments"]["withholding"]
        filing_status = tax_return.filing_status
    elif projected is None:
        if request.net_profit is None:
            raise HTTPException(status_code=400, detail="Provide projected_total_tax, net_profit, or tax_return_id")
        estimate_calc = tax_engine.calculate_individual_tax(
            tax_year=request.tax_year,
            filing_status=filing_status,
            self_employment_income=request.net_profit,
        )
        projected = estimate_calc["tax"]["total_tax"]
        withholding = request.withholding

    result = tax_engine.calculate_estimated_taxes(
        tax_year=request.tax_year,
        filing_status=filing_status,
        projected_total_tax=projected or 0.0,
        prior_year_tax=request.prior_year_tax,
        withholding=withholding,
        prior_year_agi=request.prior_year_agi,
        reminders_enabled=request.reminders_enabled,
    )

    row = db.query(EstimatedTax).filter(
        EstimatedTax.user_id == current_user.id,
        EstimatedTax.tax_year == request.tax_year,
    ).first()
    if not row:
        row = EstimatedTax(user_id=current_user.id, tax_year=request.tax_year)
        db.add(row)
    row.q1_amount = row.q2_amount = row.q3_amount = row.q4_amount = result["quarterly_payment"]
    row.total_estimated_tax = result["projected_total_tax"]
    row.safe_harbor_amount = result["safe_harbor_amount"]
    row.due_dates = {**result["due_dates"], "filing_status": filing_status}
    row.reminders_enabled = request.reminders_enabled
    row.paid_json = row.paid_json or {"q1": False, "q2": False, "q3": False, "q4": False}
    db.commit()
    db.refresh(row)

    return {"estimated_tax": _serialize_estimated(row), "calculation": result}


@router.get("/estimated-taxes")
async def list_estimated_taxes(
    tax_year: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List saved estimated tax schedules."""
    query = db.query(EstimatedTax).filter(EstimatedTax.user_id == current_user.id)
    if tax_year:
        query = query.filter(EstimatedTax.tax_year == tax_year)
    rows = query.order_by(EstimatedTax.tax_year.desc()).all()
    return [_serialize_estimated(row) for row in rows]


@router.patch("/estimated-taxes/{estimate_id}/paid")
async def mark_quarter_paid(
    estimate_id: int,
    quarter: str,
    paid: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a quarterly payment as paid or unpaid."""
    if quarter.lower() not in {"q1", "q2", "q3", "q4"}:
        raise HTTPException(status_code=400, detail="quarter must be q1-q4")
    row = db.query(EstimatedTax).filter(
        EstimatedTax.id == estimate_id,
        EstimatedTax.user_id == current_user.id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Estimated tax record not found")
    paid_map = row.paid_json or {}
    paid_map[quarter.lower()] = paid
    row.paid_json = paid_map
    db.commit()
    return _serialize_estimated(row)


# ---------------------------------------------------------------------------
# Audit documentation
# ---------------------------------------------------------------------------


@router.get("/audit-docs")
async def list_audit_docs(
    tax_year: Optional[int] = None,
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List audit documentation grouped by category."""
    query = db.query(AuditDoc).filter(AuditDoc.user_id == current_user.id)
    if tax_year:
        query = query.filter(AuditDoc.tax_year == tax_year)
    if category:
        query = query.filter(AuditDoc.category == category)
    docs = query.order_by(AuditDoc.uploaded_at.desc()).all()
    grouped: Dict[str, List[dict]] = {}
    for doc in docs:
        grouped.setdefault(doc.category, []).append({
            "id": doc.id,
            "tax_year": doc.tax_year,
            "filename": doc.filename,
            "file_url": doc.file_url,
            "mime_type": doc.mime_type,
            "file_size": doc.file_size,
            "notes": doc.notes,
            "verified_bool": doc.verified_bool,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        })
    return {
        "documents": [
            {
                "id": doc.id,
                "tax_year": doc.tax_year,
                "category": doc.category,
                "filename": doc.filename,
                "file_url": doc.file_url,
                "mime_type": doc.mime_type,
                "file_size": doc.file_size,
                "notes": doc.notes,
                "verified_bool": doc.verified_bool,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            }
            for doc in docs
        ],
        "by_category": grouped,
        "count": len(docs),
    }


@router.post("/audit-docs")
async def add_audit_doc(
    request: AuditDocCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register an externally hosted supporting document."""
    doc = AuditDoc(
        user_id=current_user.id,
        tax_year=request.tax_year,
        category=request.category,
        filename=request.filename,
        file_url=request.file_url,
        mime_type=request.mime_type,
        file_size=request.file_size,
        notes=request.notes,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "filename": doc.filename, "category": doc.category, "file_url": doc.file_url}


@router.post("/audit-docs/upload")
async def upload_audit_doc(
    tax_year: int = Query(..., ge=2000, le=2100),
    category: str = Query(...),
    notes: Optional[str] = Query(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a receipt or supporting document for audit defense."""
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 15 MB limit")
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {content_type}")

    safe_name = os.path.basename(file.filename or "document")
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    user_dir = UPLOAD_DIR / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / stored_name).write_bytes(content)

    doc = AuditDoc(
        user_id=current_user.id,
        tax_year=tax_year,
        category=category,
        filename=safe_name,
        file_url=f"/static/uploads/audit/{current_user.id}/{stored_name}",
        mime_type=content_type,
        file_size=len(content),
        notes=notes,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "filename": doc.filename, "file_url": doc.file_url, "category": doc.category}


@router.delete("/audit-docs/{doc_id}")
async def delete_audit_doc(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a supporting document record."""
    doc = db.query(AuditDoc).filter(
        AuditDoc.id == doc_id,
        AuditDoc.user_id == current_user.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted", "id": doc_id}


@router.get("/audit-docs/coverage")
async def audit_doc_coverage(
    tax_year: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Show documentation coverage for each claimed deduction."""
    year = tax_year or (date.today().year - 1)
    deductions = db.query(Deduction).filter(
        Deduction.user_id == current_user.id,
        Deduction.tax_year == year,
    ).all()
    docs = db.query(AuditDoc).filter(
        AuditDoc.user_id == current_user.id,
        AuditDoc.tax_year == year,
    ).all()
    return tax_engine.audit_coverage(
        [{"id": d.id, "category": d.category, "amount": d.amount, "receipt_url": d.receipt_url, "verified_bool": d.verified_bool} for d in deductions],
        [{"id": d.id, "category": d.category, "filename": d.filename} for d in docs],
    )


@router.get("/audit-docs/package")
async def audit_package(
    tax_year: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate an audit response package manifest."""
    year = tax_year or (date.today().year - 1)
    deductions = db.query(Deduction).filter(
        Deduction.user_id == current_user.id,
        Deduction.tax_year == year,
    ).all()
    docs = db.query(AuditDoc).filter(
        AuditDoc.user_id == current_user.id,
        AuditDoc.tax_year == year,
    ).all()
    coverage = tax_engine.audit_coverage(
        [{"id": d.id, "category": d.category, "amount": d.amount, "receipt_url": d.receipt_url, "verified_bool": d.verified_bool} for d in deductions],
        [{"id": d.id, "category": d.category, "filename": d.filename} for d in docs],
    )
    package = {
        "tax_year": year,
        "prepared_at": datetime.utcnow().isoformat(),
        "taxpayer": {
            "name": f"{current_user.first_name} {current_user.last_name}".strip(),
            "email": current_user.email,
        },
        "summary": {
            "total_deductions": coverage["total_deductions"],
            "documented_amount": coverage["documented_amount"],
            "coverage_percent": coverage["coverage_percent"],
            "risk_level": coverage["risk_level"],
            "document_count": coverage["document_count"],
        },
        "documents_by_category": {},
        "deductions": coverage["rows"],
        "items_needing_action": coverage["under_documented"],
        "response_checklist": [
            "Download and organize all documents listed by category.",
            "Write a brief explanation of the business purpose for each flagged deduction.",
            "Include mileage logs, receipts, and bank statements for amounts over $75.",
            "Keep a copy of the filed return and this manifest for your records.",
            "Respond to IRS notices by the stated deadline and send copies, never originals.",
        ],
        "disclaimer": tax_engine.DISCLAIMER,
    }
    for doc in docs:
        package["documents_by_category"].setdefault(doc.category, []).append({
            "filename": doc.filename,
            "file_url": doc.file_url,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            "verified": doc.verified_bool,
        })
    return package


# ---------------------------------------------------------------------------
# Capital gains & investments
# ---------------------------------------------------------------------------


@router.post("/investments")
async def add_investment(
    request: InvestmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Track an investment position and its cost basis."""
    row = Investment(
        user_id=current_user.id,
        symbol=request.symbol.upper(),
        name=request.name,
        asset_type=request.asset_type,
        quantity=request.quantity,
        purchase_date=datetime.combine(_parse_date(request.purchase_date, "purchase_date"), datetime.min.time()),
        cost_basis=request.cost_basis,
        current_value=request.current_value,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "symbol": row.symbol,
        "quantity": row.quantity,
        "cost_basis": row.cost_basis,
        "purchase_date": row.purchase_date.isoformat(),
    }


@router.get("/investments")
async def list_investments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List tracked investment positions."""
    rows = db.query(Investment).filter(Investment.user_id == current_user.id).all()
    return [
        {
            "id": row.id,
            "symbol": row.symbol,
            "name": row.name,
            "asset_type": row.asset_type,
            "quantity": row.quantity,
            "purchase_date": row.purchase_date.isoformat(),
            "cost_basis": row.cost_basis,
            "current_value": row.current_value,
        }
        for row in rows
    ]


@router.post("/capital-gains/sales")
async def record_sale(
    request: SaleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a sale and calculate holding period plus gain/loss."""
    purchase = _parse_date(request.purchase_date, "purchase_date")
    sale = _parse_date(request.sale_date, "sale_date")
    if sale < purchase:
        raise HTTPException(status_code=400, detail="sale_date cannot be before purchase_date")
    if request.investment_id:
        investment = db.query(Investment).filter(
            Investment.id == request.investment_id,
            Investment.user_id == current_user.id,
        ).first()
        if not investment:
            raise HTTPException(status_code=404, detail="Investment not found")
    holding = "long" if (sale - purchase).days > 365 else "short"
    gain = round(request.proceeds - request.cost_basis, 2)
    row = InvestmentSale(
        user_id=current_user.id,
        investment_id=request.investment_id,
        tax_year=request.tax_year,
        symbol=request.symbol.upper(),
        description=request.description,
        purchase_date=datetime.combine(purchase, datetime.min.time()),
        sale_date=datetime.combine(sale, datetime.min.time()),
        proceeds=request.proceeds,
        cost_basis=request.cost_basis,
        holding_period=holding,
        gain_loss=gain,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "symbol": row.symbol,
        "holding_period": row.holding_period,
        "gain_loss": row.gain_loss,
        "proceeds": row.proceeds,
        "cost_basis": row.cost_basis,
        "sale_date": row.sale_date.isoformat(),
    }


@router.get("/capital-gains")
async def list_capital_gains(
    tax_year: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List sales and summarized capital gain tax impact."""
    year = tax_year or (date.today().year - 1)
    rows = db.query(InvestmentSale).filter(
        InvestmentSale.user_id == current_user.id,
        InvestmentSale.tax_year == year,
    ).all()
    summary = tax_engine.calculate_capital_gains(
        [{"symbol": r.symbol, "description": r.description, "proceeds": r.proceeds, "cost_basis": r.cost_basis,
          "purchase_date": r.purchase_date, "sale_date": r.sale_date} for r in rows],
        year,
        "single",
    )
    return {"tax_year": year, "sales": summary["rows"], "summary": summary}


@router.post("/capital-gains/what-if")
async def capital_gains_what_if(
    request: WhatIfRequest,
    current_user: User = Depends(get_current_user),
):
    """Compare the tax impact of selling now versus holding for long-term treatment."""
    if request.filing_status not in VALID_FILING_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid filing status")
    return tax_engine.what_if_sale(
        symbol=request.symbol,
        proceeds=request.proceeds,
        cost_basis=request.cost_basis,
        purchase_date=request.purchase_date,
        sale_date=request.sale_date,
        tax_year=request.tax_year,
        filing_status=request.filing_status,
        ordinary_income=request.ordinary_income,
    )


@router.get("/capital-gains/schedule-d")
async def capital_gains_schedule_d(
    tax_year: Optional[int] = None,
    tax_return_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a Schedule D payload directly from recorded sales."""
    year = tax_year or (date.today().year - 1)
    ordinary_income = 0.0
    filing_status = "single"
    if tax_return_id:
        tax_return = _get_return(db, current_user, tax_return_id)
        year = tax_return.tax_year
        filing_status = tax_return.filing_status
        ordinary_income = tax_return.taxable_income or 0.0
    rows = db.query(InvestmentSale).filter(
        InvestmentSale.user_id == current_user.id,
        InvestmentSale.tax_year == year,
    ).all()
    return tax_engine.generate_schedule_d(
        tax_year=year,
        sales=[{"symbol": r.symbol, "description": r.description, "proceeds": r.proceeds, "cost_basis": r.cost_basis,
                "purchase_date": r.purchase_date, "sale_date": r.sale_date} for r in rows],
        ordinary_income=ordinary_income,
        filing_status=filing_status,
    )


# ---------------------------------------------------------------------------
# Retirement
# ---------------------------------------------------------------------------


@router.post("/retirement/compare")
async def retirement_compare(
    request: RetirementCompareRequest,
    current_user: User = Depends(get_current_user),
):
    """Compare Traditional IRA, Roth IRA, SEP-IRA, and Solo 401(k)."""
    if request.filing_status not in VALID_FILING_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid filing status")
    return tax_engine.retirement_comparison(
        tax_year=request.tax_year,
        net_self_employment_income=request.net_self_employment_income,
        marginal_tax_rate=request.marginal_tax_rate,
        age=request.age,
        filing_status=request.filing_status,
    )


@router.post("/retirement/accounts")
async def add_retirement_account(
    request: RetirementAccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Track a retirement account contribution and balance."""
    valid_types = {"traditional_ira", "roth_ira", "sep_ira", "solo_401k"}
    if request.account_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"account_type must be one of {sorted(valid_types)}")
    year = request.tax_year if request.tax_year in tax_engine.RETIREMENT_LIMITS else max(tax_engine.RETIREMENT_LIMITS)
    limit = tax_engine.RETIREMENT_LIMITS[year].get(request.account_type, 0)
    row = RetirementAccount(
        user_id=current_user.id,
        tax_year=request.tax_year,
        account_type=request.account_type,
        provider=request.provider,
        contributed_amount=request.contributed_amount,
        balance=request.balance,
        contribution_limit=limit,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "tax_year": row.tax_year,
        "account_type": row.account_type,
        "contributed_amount": row.contributed_amount,
        "contribution_limit": row.contribution_limit,
        "remaining_room": round(max(0.0, row.contribution_limit - row.contributed_amount), 2),
        "over_contributed": row.contributed_amount > row.contribution_limit,
    }


@router.get("/retirement/accounts")
async def list_retirement_accounts(
    tax_year: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List retirement accounts and contribution room."""
    query = db.query(RetirementAccount).filter(RetirementAccount.user_id == current_user.id)
    if tax_year:
        query = query.filter(RetirementAccount.tax_year == tax_year)
    rows = query.order_by(RetirementAccount.tax_year.desc()).all()
    return [
        {
            "id": row.id,
            "tax_year": row.tax_year,
            "account_type": row.account_type,
            "provider": row.provider,
            "contributed_amount": row.contributed_amount,
            "balance": row.balance,
            "contribution_limit": row.contribution_limit,
            "remaining_room": round(max(0.0, row.contribution_limit - row.contributed_amount), 2),
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Multi-state
# ---------------------------------------------------------------------------


@router.post("/state-returns")
async def calculate_state_returns(
    request: MultiStateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Calculate and persist multi-state allocations and liabilities."""
    tax_return = None
    if request.tax_return_id:
        tax_return = _get_return(db, current_user, request.tax_return_id)
        if tax_return.tax_year != request.tax_year:
            raise HTTPException(status_code=400, detail="tax_year must match the linked return")

    results = []
    total_tax = 0.0
    for allocation in request.allocations:
        state = allocation.state.upper()
        if state not in tax_engine.STATE_RATES:
            raise HTTPException(status_code=400, detail=f"Unsupported state code: {state}")
        calc = tax_engine.calculate_state_tax(state, allocation.income, allocation.residency_status)
        total_tax += calc["state_tax"]
        row = StateReturn(
            user_id=current_user.id,
            tax_return_id=request.tax_return_id,
            tax_year=request.tax_year,
            state=state,
            residency_status=allocation.residency_status,
            income_allocated=allocation.income,
            state_tax=calc["state_tax"],
            form_data=calc,
        )
        db.add(row)
        results.append(calc)
    db.commit()
    return {
        "tax_year": request.tax_year,
        "states": results,
        "total_state_tax": round(total_tax, 2),
        "note": "Part-year residents are estimated at 50% of the full-year liability.",
        "disclaimer": tax_engine.DISCLAIMER,
    }


@router.get("/state-returns")
async def list_state_returns(
    tax_year: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List state return records."""
    query = db.query(StateReturn).filter(StateReturn.user_id == current_user.id)
    if tax_year:
        query = query.filter(StateReturn.tax_year == tax_year)
    rows = query.order_by(StateReturn.tax_year.desc()).all()
    return [
        {
            "id": row.id,
            "tax_year": row.tax_year,
            "state": row.state,
            "residency_status": row.residency_status,
            "income_allocated": row.income_allocated,
            "state_tax": row.state_tax,
            "form_data": row.form_data,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# E-file (mock)
# ---------------------------------------------------------------------------


@router.post("/efile/{return_id}/prepare")
async def prepare_efile(
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Prepare a mock IRS e-file payload for a return."""
    tax_return = _get_return(db, current_user, return_id)
    forms = db.query(TaxForm).filter(TaxForm.tax_return_id == tax_return.id).all()
    if not forms:
        raise HTTPException(status_code=400, detail="Generate forms before preparing an e-file submission")
    payload = tax_engine.generate_efile_payload(
        tax_return={
            "id": tax_return.id,
            "tax_year": tax_return.tax_year,
            "filing_status": tax_return.filing_status,
            "entity_type": tax_return.entity_type,
            "total_income": tax_return.total_income,
            "total_deductions": tax_return.total_deductions,
            "estimated_tax": tax_return.estimated_tax,
        },
        forms=[{"form_type": f.form_type, "completed": f.completed_bool} for f in forms],
        taxpayer={"first_name": current_user.first_name, "last_name": current_user.last_name, "email": current_user.email},
    )
    submission = EfileSubmission(
        tax_return_id=tax_return.id,
        status="prepared",
        submission_id=payload["submission_id"],
        payload=payload,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return {"id": submission.id, "status": submission.status, "submission_id": submission.submission_id, "payload": submission.payload}


@router.post("/efile/{return_id}/submit")
async def submit_efile(
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Simulate transmitting and acknowledging a return with the IRS."""
    tax_return = _get_return(db, current_user, return_id)
    submission = db.query(EfileSubmission).filter(
        EfileSubmission.tax_return_id == tax_return.id,
    ).order_by(EfileSubmission.id.desc()).first()
    if not submission:
        raise HTTPException(status_code=400, detail="Prepare the e-file submission first")
    submission.status = "accepted"
    submission.confirmation_number = f"IRS-{datetime.utcnow():%Y%m%d%H%M%S}-{tax_return.id}"
    submission.submitted_at = datetime.utcnow()
    submission.acknowledged_at = datetime.utcnow()
    tax_return.status = "accepted"
    tax_return.filed_at = tax_return.filed_at or datetime.utcnow()
    db.commit()
    return {
        "id": submission.id,
        "status": submission.status,
        "confirmation_number": submission.confirmation_number,
        "submitted_at": submission.submitted_at.isoformat(),
        "acknowledged_at": submission.acknowledged_at.isoformat(),
        "tax_return_status": tax_return.status,
    }


@router.get("/efile/{return_id}")
async def get_efile_status(
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get e-file submission history for a return."""
    tax_return = _get_return(db, current_user, return_id)
    rows = db.query(EfileSubmission).filter(
        EfileSubmission.tax_return_id == tax_return.id,
    ).order_by(EfileSubmission.id.desc()).all()
    return [
        {
            "id": row.id,
            "status": row.status,
            "submission_id": row.submission_id,
            "confirmation_number": row.confirmation_number,
            "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
            "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
            "rejection_reason": row.rejection_reason,
            "payload": row.payload,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------------


@router.get("/dashboard/{return_id}")
async def tax_dashboard(
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregated dashboard data for a single return."""
    tax_return = _get_return(db, current_user, return_id)
    calculation = _compute_return(db, tax_return)
    forms = db.query(TaxForm).filter(TaxForm.tax_return_id == tax_return.id).all()
    deductions = db.query(Deduction).filter(Deduction.tax_year == tax_return.tax_year, Deduction.user_id == current_user.id).all()
    estimate = db.query(EstimatedTax).filter(
        EstimatedTax.user_id == current_user.id,
        EstimatedTax.tax_year == tax_return.tax_year,
    ).first()
    payment_schedule = tax_engine.calculate_estimated_taxes(
        tax_year=tax_return.tax_year,
        filing_status=tax_return.filing_status,
        projected_total_tax=calculation["tax"]["total_tax"],
        withholding=calculation["payments"]["withholding"],
    )
    return {
        "return": _serialize_return(tax_return, db),
        "calculation": calculation,
        "forms": [_serialize_form(f, include_data=False) for f in forms],
        "deductions_total": round(sum(d.amount for d in deductions), 2),
        "deductions_count": len(deductions),
        "estimated_tax_schedule": estimate and _serialize_estimated(estimate) or None,
        "upcoming_payments": [q for q in payment_schedule["schedule"] if q["days_until_due"] >= 0][:4],
        "timeline": {
            "created_at": tax_return.created_at.isoformat() if tax_return.created_at else None,
            "filed_at": tax_return.filed_at.isoformat() if tax_return.filed_at else None,
            "status": tax_return.status,
            "progress": _serialize_return(tax_return, db)["progress"],
        },
    }
