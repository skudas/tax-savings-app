"""Job marketplace routes - professionals posting and bidding on jobs."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel

from database import get_db
from models import User, JobPosting, JobApplication, JobSubscription
from .auth import get_current_user

router = APIRouter()


class JobPostCreate(BaseModel):
    title: str
    description: str
    category: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    budget_type: str = "fixed"
    deadline: Optional[datetime] = None
    estimated_duration: Optional[str] = None
    required_skills: Optional[List[str]] = None
    experience_level: Optional[str] = None
    scope: Optional[str] = None
    deliverables: Optional[List[str]] = None


class JobResponse(JobPostCreate):
    id: int
    posted_by_user_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    applicant_count: int = 0
    poster_name: Optional[str] = None
    poster_rating: Optional[float] = None
    poster_total_consultations: Optional[int] = None

    class Config:
        from_attributes = True


class JobApplicationCreate(BaseModel):
    bid_amount: Optional[float] = None
    proposed_timeline: Optional[str] = None
    cover_letter: Optional[str] = None
    portfolio_url: Optional[str] = None


class JobApplicationResponse(JobApplicationCreate):
    id: int
    job_id: int
    applied_by_user_id: int
    status: str
    created_at: datetime
    applicant_name: Optional[str] = None
    applicant_email: Optional[str] = None
    applicant_rating: Optional[float] = None
    applicant_total_consultations: Optional[int] = None

    class Config:
        from_attributes = True


@router.post("/jobs/subscribe", response_model=dict)
async def subscribe_to_job_posting(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Subscribe to job posting ($50/year)."""

    # Check if already subscribed
    existing = db.query(JobSubscription).filter(
        JobSubscription.user_id == current_user.id
    ).first()

    start_date = datetime.utcnow()
    end_date = start_date + timedelta(days=365)

    if existing and existing.status == "active" and existing.subscription_end and existing.subscription_end > start_date:
        raise HTTPException(status_code=400, detail="Already has active subscription")

    if existing:
        existing.status = "active"
        existing.annual_price = 50.0
        existing.subscription_start = start_date
        existing.subscription_end = end_date
        existing.renewal_date = end_date
        subscription = existing
    else:
        subscription = JobSubscription(
            user_id=current_user.id,
            status="active",
            subscription_start=start_date,
            subscription_end=end_date,
            renewal_date=end_date
        )
        db.add(subscription)

    db.commit()
    db.refresh(subscription)

    return {
        "subscription_id": subscription.id,
        "status": "active",
        "price": "$50/year",
        "expires": end_date.isoformat(),
        "max_concurrent_jobs": subscription.max_concurrent_jobs or 10
    }


@router.post("/jobs", response_model=JobResponse)
async def create_job(
    job_data: JobPostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Post a new job listing ($50/year subscription required)."""

    # Check if user has active job subscription
    subscription = db.query(JobSubscription).filter(
        JobSubscription.user_id == current_user.id,
        JobSubscription.status == "active"
    ).first()

    if not subscription:
        raise HTTPException(
            status_code=403,
            detail="Need $50/year job posting subscription to post jobs"
        )

    # Check if at max concurrent jobs
    active_jobs = db.query(JobPosting).filter(
        JobPosting.posted_by_user_id == current_user.id,
        JobPosting.status == "open"
    ).count()

    if active_jobs >= subscription.max_concurrent_jobs:
        raise HTTPException(
            status_code=400,
            detail=f"Max {subscription.max_concurrent_jobs} concurrent jobs reached"
        )

    # Create job
    job = JobPosting(
        posted_by_user_id=current_user.id,
        title=job_data.title,
        description=job_data.description,
        category=job_data.category,
        budget_min=job_data.budget_min,
        budget_max=job_data.budget_max,
        budget_type=job_data.budget_type,
        deadline=job_data.deadline,
        estimated_duration=job_data.estimated_duration,
        required_skills=job_data.required_skills,
        experience_level=job_data.experience_level,
        scope=job_data.scope,
        deliverables=job_data.deliverables
    )

    db.add(job)
    subscription.active_job_count += 1
    db.commit()
    db.refresh(job)

    return job


@router.get("/jobs", response_model=List[JobResponse])
async def list_jobs(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Browse all job listings."""

    query = db.query(JobPosting)

    if status:
        query = query.filter(JobPosting.status == status)
    else:
        query = query.filter(JobPosting.status == "open")  # Default to open jobs

    if category:
        query = query.filter(JobPosting.category == category)

    jobs = query.order_by(JobPosting.created_at.desc()).offset(skip).limit(limit).all()

    return jobs


@router.get("/jobs/subscription")
async def get_job_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get job posting subscription status for the current user."""

    subscription = db.query(JobSubscription).filter(
        JobSubscription.user_id == current_user.id
    ).first()

    active_jobs = db.query(JobPosting).filter(
        JobPosting.posted_by_user_id == current_user.id,
        JobPosting.status == "open"
    ).count()

    if not subscription:
        return {
            "subscribed": False,
            "status": "inactive",
            "plan": "$50/year",
            "annual_price": 50.0,
            "active_job_count": active_jobs,
            "max_concurrent_jobs": 10,
            "subscription_start": None,
            "subscription_end": None,
            "renewal_date": None,
        }

    is_active = subscription.status == "active" and (
        subscription.subscription_end is None or subscription.subscription_end > datetime.utcnow()
    )

    return {
        "subscribed": bool(is_active),
        "status": subscription.status,
        "plan": "$50/year",
        "annual_price": subscription.annual_price,
        "active_job_count": active_jobs,
        "max_concurrent_jobs": subscription.max_concurrent_jobs,
        "subscription_start": subscription.subscription_start.isoformat() if subscription.subscription_start else None,
        "subscription_end": subscription.subscription_end.isoformat() if subscription.subscription_end else None,
        "renewal_date": (subscription.renewal_date or subscription.subscription_end).isoformat()
        if (subscription.renewal_date or subscription.subscription_end) else None,
    }


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Get job details."""

    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@router.post("/jobs/{job_id}/apply", response_model=JobApplicationResponse)
async def apply_for_job(
    job_id: int,
    application: JobApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Apply/bid on a job posting."""

    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "open":
        raise HTTPException(status_code=400, detail="Job is not open for applications")

    # Check if already applied
    existing = db.query(JobApplication).filter(
        JobApplication.job_id == job_id,
        JobApplication.applied_by_user_id == current_user.id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Already applied for this job")

    # Create application
    app = JobApplication(
        job_id=job_id,
        applied_by_user_id=current_user.id,
        bid_amount=application.bid_amount,
        proposed_timeline=application.proposed_timeline,
        cover_letter=application.cover_letter,
        portfolio_url=application.portfolio_url
    )

    db.add(app)
    db.commit()
    db.refresh(app)

    return app


@router.get("/jobs/{job_id}/applications", response_model=List[JobApplicationResponse])
async def get_job_applications(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all applications for a job (job poster only)."""

    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Verify user is job poster
    if job.posted_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    applications = db.query(JobApplication).filter(
        JobApplication.job_id == job_id
    ).order_by(JobApplication.created_at.desc()).all()

    return applications


@router.put("/jobs/{job_id}/applications/{app_id}/accept")
async def accept_application(
    job_id: int,
    app_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accept a job application."""

    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()

    if not job or job.posted_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    app = db.query(JobApplication).filter(JobApplication.id == app_id).first()

    if not app or app.job_id != job_id:
        raise HTTPException(status_code=404, detail="Application not found")

    app.status = "hired"
    job.status = "in_progress"

    db.commit()

    return {"message": "Application accepted", "status": "hired"}


@router.put("/jobs/{job_id}/close")
async def close_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Close a job posting."""

    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()

    if not job or job.posted_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    job.status = "closed"

    # Update subscription job count
    subscription = db.query(JobSubscription).filter(
        JobSubscription.user_id == current_user.id
    ).first()

    if subscription:
        subscription.active_job_count = max(0, subscription.active_job_count - 1)

    db.commit()

    return {"message": "Job closed", "status": "closed"}


@router.get("/my-jobs", response_model=List[JobResponse])
async def get_my_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all jobs posted by current user."""

    jobs = db.query(JobPosting).filter(
        JobPosting.posted_by_user_id == current_user.id
    ).order_by(JobPosting.created_at.desc()).all()

    return jobs
