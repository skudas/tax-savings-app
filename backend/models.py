"""
SQLAlchemy ORM models for the tax savings marketplace application.

Models:
- User: Base user (clients and professionals)
- ProfessionalProfile: Tax professional information
- ProfessionalSubscription: Monthly subscription status
- RateCard: Professional pricing for different services
- Consultation: Booked consultations between client and professional
- Message: Direct messages between parties
- Review: Client reviews of professionals
- Transaction: Payment transactions with commission tracking
- OnboardingResult: Results from S-Corp savings questionnaire
- AuditLog: Audit trail of changes
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class UserType(str, enum.Enum):
    """User types: client or professional."""
    CLIENT = "client"
    PROFESSIONAL = "professional"


class SubscriptionStatus(str, enum.Enum):
    """Subscription statuses."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class ConsultationStatus(str, enum.Enum):
    """Consultation booking statuses."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class User(Base):
    """User account model - supports both clients and professionals."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    user_type = Column(String(20), default=UserType.CLIENT.value)  # "client" or "professional"
    phone = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    professional_profile = relationship("ProfessionalProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    onboarding_results = relationship("OnboardingResult", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    client_consultations = relationship("Consultation", foreign_keys="Consultation.client_id", back_populates="client")
    professional_consultations = relationship("Consultation", foreign_keys="Consultation.professional_id", back_populates="professional")
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    received_messages = relationship("Message", foreign_keys="Message.recipient_id", back_populates="recipient")

    # Tax filing relationships
    tax_returns = relationship("TaxReturn", back_populates="user", cascade="all, delete-orphan")
    deductions = relationship("Deduction", back_populates="user", cascade="all, delete-orphan")
    estimated_taxes = relationship("EstimatedTax", back_populates="user", cascade="all, delete-orphan")
    audit_docs = relationship("AuditDoc", back_populates="user", cascade="all, delete-orphan")
    self_employment_income = relationship("SelfEmploymentIncome", back_populates="user", cascade="all, delete-orphan")
    investments = relationship("Investment", back_populates="user", cascade="all, delete-orphan")
    investment_sales = relationship("InvestmentSale", back_populates="user", cascade="all, delete-orphan")
    retirement_accounts = relationship("RetirementAccount", back_populates="user", cascade="all, delete-orphan")
    state_returns = relationship("StateReturn", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email} ({self.user_type})>"


class ProfessionalProfile(Base):
    """Tax professional profile information."""

    __tablename__ = "professional_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, unique=True)

    # Professional info
    bio = Column(Text)
    specialties = Column(JSON)  # List of specialties: ["S-Corp", "LLC", "Sole Prop", etc]
    years_experience = Column(Integer)
    certifications = Column(JSON)  # List of certifications: ["CPA", "EA", "CFP", etc]

    # Professional verification
    verified = Column(Boolean, default=False)
    verification_date = Column(DateTime)
    license_number = Column(String(100))

    # Availability
    availability_json = Column(JSON)  # {Mon-Fri hours, timezone, etc}

    # Stats
    total_consultations = Column(Integer, default=0)
    average_rating = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="professional_profile")
    rate_cards = relationship("RateCard", back_populates="professional", cascade="all, delete-orphan")
    subscription = relationship("ProfessionalSubscription", back_populates="professional", uselist=False, cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="professional", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Professional {self.user.email}>"


class RateCard(Base):
    """Professional's pricing for different services."""

    __tablename__ = "rate_cards"

    id = Column(Integer, primary_key=True)
    professional_id = Column(Integer, ForeignKey("professional_profiles.id"), nullable=False, index=True)

    service_name = Column(String(100), nullable=False)  # "Initial Consultation", "S-Corp Planning", "Hourly Consultation", etc
    service_type = Column(String(20), nullable=False)  # "hourly", "fixed", "package"
    price = Column(Float, nullable=False)
    duration_minutes = Column(Integer)  # For hourly rate, what's the minimum booking
    description = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    professional = relationship("ProfessionalProfile", back_populates="rate_cards")
    consultations = relationship("Consultation", back_populates="rate_card")

    def __repr__(self):
        return f"<RateCard {self.service_name} - ${self.price}>"


class ProfessionalSubscription(Base):
    """Professional's subscription status."""

    __tablename__ = "professional_subscriptions"

    id = Column(Integer, primary_key=True)
    professional_id = Column(Integer, ForeignKey("professional_profiles.id"), nullable=False, index=True, unique=True)

    plan_type = Column(String(20), default="basic")  # "basic", "pro", "premium"
    monthly_price = Column(Float, default=35.0)
    status = Column(String(20), default=SubscriptionStatus.ACTIVE.value)

    # Billing
    billing_period_start = Column(DateTime, nullable=False, default=datetime.utcnow)
    billing_period_end = Column(DateTime, nullable=False)
    stripe_subscription_id = Column(String(255))

    # Commission tracking
    total_earnings = Column(Float, default=0.0)
    total_commissions_paid = Column(Float, default=0.0)
    current_balance = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    professional = relationship("ProfessionalProfile", back_populates="subscription")

    def __repr__(self):
        return f"<Subscription {self.professional.user.email} - {self.status}>"


class Consultation(Base):
    """Booked consultation between client and professional."""

    __tablename__ = "consultations"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    professional_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    rate_card_id = Column(Integer, ForeignKey("rate_cards.id"), nullable=False)

    # Consultation details
    scheduled_at = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    rate_per_unit = Column(Float, nullable=False)  # Price at time of booking
    total_price = Column(Float, nullable=False)

    # Platform commission
    commission_percent = Column(Float, default=10.0)  # 10% commission
    commission_amount = Column(Float, default=0.0)
    professional_receives = Column(Float, default=0.0)  # total_price - commission

    status = Column(String(20), default=ConsultationStatus.PENDING.value)
    notes = Column(Text)

    # Meeting details
    meeting_link = Column(String(500))  # Zoom/Google Meet link

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)

    # Relationships
    client = relationship("User", foreign_keys=[client_id], back_populates="client_consultations")
    professional = relationship("User", foreign_keys=[professional_id], back_populates="professional_consultations")
    rate_card = relationship("RateCard", back_populates="consultations")

    def __repr__(self):
        return f"<Consultation {self.id} - {self.status}>"


class Message(Base):
    """Direct messages between client and professional."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    read_at = Column(DateTime)

    # Relationships
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="received_messages")

    def __repr__(self):
        return f"<Message from {self.sender.email} to {self.recipient.email}>"


class Review(Base):
    """Client reviews of professionals."""

    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    professional_id = Column(Integer, ForeignKey("professional_profiles.id"), nullable=False, index=True)
    consultation_id = Column(Integer, ForeignKey("consultations.id"))

    rating = Column(Integer, nullable=False)  # 1-5 stars
    title = Column(String(200))
    content = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    professional = relationship("ProfessionalProfile", back_populates="reviews")

    def __repr__(self):
        return f"<Review {self.rating}/5 for professional {self.professional_id}>"


class JobPosting(Base):
    """Job listings posted by professionals hiring contractors."""

    __tablename__ = "job_postings"

    id = Column(Integer, primary_key=True)
    posted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Job details
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100))  # "Tax Return", "Bookkeeping", "Audit", etc

    # Budget
    budget_min = Column(Float)
    budget_max = Column(Float)
    budget_type = Column(String(20))  # "fixed", "hourly", "range"

    # Timeline
    deadline = Column(DateTime)
    estimated_duration = Column(String(100))  # "1 week", "1 month", etc

    # Status
    status = Column(String(20), default="open")  # "open", "in_progress", "closed", "cancelled"

    # Skills/requirements (JSON array)
    required_skills = Column(JSON)  # ["Tax Planning", "S-Corp", "Bookkeeping"]
    experience_level = Column(String(20))  # "entry", "intermediate", "expert"

    # Engagement details
    scope = Column(Text)  # Detailed scope of work
    deliverables = Column(JSON)  # List of deliverables

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def applicant_count(self):
        return len(self.applications or [])

    @property
    def poster_name(self):
        user = self.posted_by
        if not user:
            return None
        return f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email

    @property
    def poster_rating(self):
        profile = getattr(self.posted_by, "professional_profile", None) if self.posted_by else None
        return profile.average_rating if profile else None

    @property
    def poster_total_consultations(self):
        profile = getattr(self.posted_by, "professional_profile", None) if self.posted_by else None
        return profile.total_consultations if profile else None

    # Relationships
    posted_by = relationship("User", foreign_keys=[posted_by_user_id])
    applications = relationship("JobApplication", back_populates="job", cascade="all, delete-orphan")


class JobApplication(Base):
    """Applications/bids on job postings."""

    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("job_postings.id"), nullable=False, index=True)
    applied_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Application details
    bid_amount = Column(Float)
    proposed_timeline = Column(String(100))
    cover_letter = Column(Text)
    portfolio_url = Column(String(500))

    # Status
    status = Column(String(20), default="pending")  # "pending", "accepted", "rejected", "hired"

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    @property
    def applicant_name(self):
        user = self.applied_by
        if not user:
            return None
        return f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email

    @property
    def applicant_email(self):
        return self.applied_by.email if self.applied_by else None

    @property
    def applicant_rating(self):
        profile = getattr(self.applied_by, "professional_profile", None) if self.applied_by else None
        return profile.average_rating if profile else None

    @property
    def applicant_total_consultations(self):
        profile = getattr(self.applied_by, "professional_profile", None) if self.applied_by else None
        return profile.total_consultations if profile else None

    job = relationship("JobPosting", back_populates="applications")
    applied_by = relationship("User", foreign_keys=[applied_by_user_id])


class JobSubscription(Base):
    """Job posting subscription for professionals."""

    __tablename__ = "job_subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, unique=True)

    status = Column(String(20), default="active")  # "active", "inactive", "expired", "cancelled"
    annual_price = Column(Float, default=50.0)  # $50/year

    subscription_start = Column(DateTime, nullable=False, default=datetime.utcnow)
    subscription_end = Column(DateTime, nullable=False)  # 1 year from start
    renewal_date = Column(DateTime)

    active_job_count = Column(Integer, default=0)
    max_concurrent_jobs = Column(Integer, default=10)  # Max 10 concurrent job postings

    stripe_subscription_id = Column(String(255))

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")


class OnboardingResult(Base):
    """S-Corp savings estimation result from onboarding questionnaire."""

    __tablename__ = "onboarding_results"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Questionnaire inputs
    annual_net_profit = Column(Float, nullable=False)
    current_entity_type = Column(String(50), nullable=False)  # sole_proprietor, llc, s_corp
    state = Column(String(2), nullable=False)
    pays_payroll_provider = Column(Boolean, default=False)

    # Results
    estimated_annual_savings_min = Column(Float, nullable=False)
    estimated_annual_savings_max = Column(Float, nullable=False)

    # Store assumptions as JSON for transparency
    assumptions_json = Column(JSON, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="onboarding_results")

    def __repr__(self):
        return f"<OnboardingResult user_id={self.user_id} savings={self.estimated_annual_savings_min}-{self.estimated_annual_savings_max}>"


class Category(Base):
    """Transaction category (customizable per user)."""

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)  # income or expense
    parent_category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="categories")
    parent_category = relationship("Category", remote_side=[id], foreign_keys=[parent_category_id])
    transactions = relationship("Transaction", back_populates="category")

    def __repr__(self):
        return f"<Category {self.name} ({self.type})>"


class Transaction(Base):
    """Bank transaction record."""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    # Transaction details
    date = Column(DateTime, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    description = Column(String(500), nullable=False)

    # Never store full bank account number - only last 4 digits (encrypted)
    bank_account_last_4 = Column(String(255), nullable=True)  # Encrypted

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction {self.date.strftime('%Y-%m-%d')} ${self.amount:.2f}>"


class AuditLog(Base):
    """Audit trail for transaction category changes."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # What changed
    entity_type = Column(String(50), nullable=False)  # Transaction, Category, etc.
    entity_id = Column(Integer, nullable=False)
    action = Column(String(20), nullable=False)  # create, update, delete

    # Changes
    old_value_json = Column(JSON, nullable=True)
    new_value_json = Column(JSON, nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog {self.entity_type}#{self.entity_id} {self.action}>"


# ---------------------------------------------------------------------------
# Tax filing & optimization models
# ---------------------------------------------------------------------------


class FilingStatus(str, enum.Enum):
    """Federal filing statuses."""
    SINGLE = "single"
    MARRIED_FILING_JOINTLY = "married_filing_jointly"
    MARRIED_FILING_SEPARATELY = "married_filing_separately"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_SURVIVING_SPOUSE = "qualifying_surviving_spouse"


class EntityTypeEnum(str, enum.Enum):
    """Business entity structures supported by the platform."""
    SOLE_PROPRIETOR = "sole_proprietor"
    LLC = "llc"
    S_CORP = "s_corp"
    C_CORP = "c_corp"
    PARTNERSHIP = "partnership"


class ReturnStatus(str, enum.Enum):
    """Lifecycle status for a tax return."""
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    READY_TO_FILE = "ready_to_file"
    FILED = "filed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    AMENDED = "amended"


class TaxReturn(Base):
    """A user's tax return for a single tax year."""

    __tablename__ = "tax_returns"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    tax_year = Column(Integer, nullable=False, index=True)
    filing_status = Column(String(40), default=FilingStatus.SINGLE.value, nullable=False)
    entity_type = Column(String(40), default=EntityTypeEnum.SOLE_PROPRIETOR.value, nullable=False)
    state = Column(String(2))
    status = Column(String(30), default=ReturnStatus.DRAFT.value, nullable=False)

    # Income summary
    w2_wages = Column(Float, default=0.0)
    federal_withholding = Column(Float, default=0.0)
    self_employment_income = Column(Float, default=0.0)
    rental_income = Column(Float, default=0.0)
    other_income = Column(Float, default=0.0)
    capital_gains = Column(Float, default=0.0)
    retirement_contributions = Column(Float, default=0.0)
    health_insurance_premiums = Column(Float, default=0.0)

    # Calculated summary (persisted for dashboards)
    total_income = Column(Float, default=0.0)
    total_deductions = Column(Float, default=0.0)
    taxable_income = Column(Float, default=0.0)
    estimated_tax = Column(Float, default=0.0)
    total_payments = Column(Float, default=0.0)
    refund_or_owed = Column(Float, default=0.0)

    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    filed_at = Column(DateTime)

    # Relationships
    user = relationship("User", back_populates="tax_returns")
    forms = relationship("TaxForm", back_populates="tax_return", cascade="all, delete-orphan")
    deductions = relationship("Deduction", back_populates="tax_return")
    self_employment = relationship("SelfEmploymentIncome", back_populates="tax_return", cascade="all, delete-orphan")
    state_returns = relationship("StateReturn", back_populates="tax_return", cascade="all, delete-orphan")
    efile_submissions = relationship("EfileSubmission", back_populates="tax_return", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TaxReturn {self.tax_year} user={self.user_id} status={self.status}>"


class TaxForm(Base):
    """A generated tax form (JSON in PDF-ready shape)."""

    __tablename__ = "tax_forms"

    id = Column(Integer, primary_key=True)
    tax_return_id = Column(Integer, ForeignKey("tax_returns.id"), nullable=False, index=True)

    form_type = Column(String(40), nullable=False)   # "1040", "schedule_c", "schedule_e", etc.
    form_name = Column(String(120), nullable=False)
    data = Column(JSON, nullable=False)
    completed_bool = Column(Boolean, default=False)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    tax_return = relationship("TaxReturn", back_populates="forms")

    def __repr__(self):
        return f"<TaxForm {self.form_type} return={self.tax_return_id}>"


class Deduction(Base):
    """A deduction claimed by a user."""

    __tablename__ = "deductions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tax_return_id = Column(Integer, ForeignKey("tax_returns.id"), nullable=True, index=True)

    tax_year = Column(Integer, nullable=False, index=True)
    category = Column(String(80), nullable=False, index=True)
    amount = Column(Float, nullable=False, default=0.0)
    description = Column(Text)
    receipt_url = Column(String(500))
    verified_bool = Column(Boolean, default=False)
    documentation_status = Column(String(30), default="missing")  # missing, partial, complete
    source = Column(String(30), default="manual")  # manual, questionnaire, imported
    irs_code = Column(String(40))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="deductions")
    tax_return = relationship("TaxReturn", back_populates="deductions")

    def __repr__(self):
        return f"<Deduction {self.category} ${self.amount:.2f} user={self.user_id}>"


class DeductionRule(Base):
    """IRS-aware rule describing a deductible category and its limits."""

    __tablename__ = "deduction_rules"

    id = Column(Integer, primary_key=True)
    category = Column(String(80), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False)
    max_amount = Column(Float, nullable=True)          # absolute cap, if any
    percentage_limit = Column(Float, nullable=True)    # e.g. 0.20 of gross for QBI
    limit_basis = Column(String(40), default="absolute")  # absolute, gross_income, net_profit, none
    irs_code = Column(String(40))
    deduction_type = Column(String(30), default="business")  # business, above_line, itemized, credit
    income_types = Column(JSON)                        # ["w2", "1099", "self_employed", "rental"]
    common_questions = Column(JSON)                    # list of {question, help, field}
    documentation_required = Column(JSON)              # list of supporting docs
    active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<DeductionRule {self.category}>"


class EstimatedTax(Base):
    """Quarterly estimated tax payments (Form 1040-ES)."""

    __tablename__ = "estimated_taxes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tax_year = Column(Integer, nullable=False, index=True)

    q1_amount = Column(Float, default=0.0)
    q2_amount = Column(Float, default=0.0)
    q3_amount = Column(Float, default=0.0)
    q4_amount = Column(Float, default=0.0)

    total_estimated_tax = Column(Float, default=0.0)
    safe_harbor_amount = Column(Float, default=0.0)
    due_dates = Column(JSON)  # {"q1": "2025-04-15", ...}
    reminders_enabled = Column(Boolean, default=True)
    paid_json = Column(JSON)  # {"q1": true, ...}

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="estimated_taxes")

    def __repr__(self):
        return f"<EstimatedTax {self.tax_year} user={self.user_id}>"


class AuditDoc(Base):
    """Supporting documentation for audit defense."""

    __tablename__ = "audit_docs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    tax_year = Column(Integer, nullable=False, index=True)
    category = Column(String(80), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)
    mime_type = Column(String(120))
    file_size = Column(Integer, default=0)
    notes = Column(Text)
    verified_bool = Column(Boolean, default=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="audit_docs")

    def __repr__(self):
        return f"<AuditDoc {self.filename} ({self.category})>"


class SelfEmploymentIncome(Base):
    """Self-employment / Schedule C income and expenses."""

    __tablename__ = "self_employment_income"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tax_return_id = Column(Integer, ForeignKey("tax_returns.id"), nullable=True, index=True)

    tax_year = Column(Integer, nullable=False, index=True)
    business_name = Column(String(200))
    business_code = Column(String(20))
    gross_revenue = Column(Float, default=0.0)
    expenses = Column(Float, default=0.0)
    cost_of_goods_sold = Column(Float, default=0.0)
    schedule_c_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="self_employment_income")
    tax_return = relationship("TaxReturn", back_populates="self_employment")

    @property
    def net_profit(self):
        return (self.gross_revenue or 0.0) - (self.expenses or 0.0) - (self.cost_of_goods_sold or 0.0)

    def __repr__(self):
        return f"<SelfEmploymentIncome {self.business_name} net={self.net_profit:.2f}>"


class Investment(Base):
    """A held investment position used to track cost basis."""

    __tablename__ = "investments"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    symbol = Column(String(30), nullable=False)
    name = Column(String(200))
    asset_type = Column(String(30), default="stock")
    quantity = Column(Float, default=0.0)
    purchase_date = Column(DateTime, nullable=False)
    cost_basis = Column(Float, nullable=False, default=0.0)
    current_value = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="investments")

    def __repr__(self):
        return f"<Investment {self.symbol} basis={self.cost_basis:.2f}>"


class InvestmentSale(Base):
    """A realized sale used to generate Schedule D."""

    __tablename__ = "investment_sales"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    investment_id = Column(Integer, ForeignKey("investments.id"), nullable=True)

    tax_year = Column(Integer, nullable=False, index=True)
    symbol = Column(String(30), nullable=False)
    description = Column(String(200))
    purchase_date = Column(DateTime, nullable=False)
    sale_date = Column(DateTime, nullable=False)
    proceeds = Column(Float, nullable=False)
    cost_basis = Column(Float, nullable=False)
    holding_period = Column(String(20), default="short")
    gain_loss = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="investment_sales")

    def __repr__(self):
        return f"<InvestmentSale {self.symbol} gain={self.gain_loss:.2f}>"


class RetirementAccount(Base):
    """Retirement account contribution tracking and limit comparison."""

    __tablename__ = "retirement_accounts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    tax_year = Column(Integer, nullable=False, index=True)
    account_type = Column(String(30), nullable=False)
    provider = Column(String(120))
    contributed_amount = Column(Float, default=0.0)
    balance = Column(Float, default=0.0)
    contribution_limit = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="retirement_accounts")

    def __repr__(self):
        return f"<RetirementAccount {self.account_type} contributed={self.contributed_amount:.2f}>"


class StateReturn(Base):
    """Per-state income allocation and calculated liability."""

    __tablename__ = "state_returns"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tax_return_id = Column(Integer, ForeignKey("tax_returns.id"), nullable=True, index=True)

    tax_year = Column(Integer, nullable=False, index=True)
    state = Column(String(2), nullable=False)
    residency_status = Column(String(30), default="resident")
    income_allocated = Column(Float, default=0.0)
    state_tax = Column(Float, default=0.0)
    form_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="state_returns")
    tax_return = relationship("TaxReturn", back_populates="state_returns")

    def __repr__(self):
        return f"<StateReturn {self.state} tax={self.state_tax:.2f}>"


class EfileSubmission(Base):
    """Mock IRS e-file submission tracking."""

    __tablename__ = "efile_submissions"

    id = Column(Integer, primary_key=True)
    tax_return_id = Column(Integer, ForeignKey("tax_returns.id"), nullable=False, index=True)

    status = Column(String(30), default="prepared")
    confirmation_number = Column(String(60))
    submission_id = Column(String(60))
    payload = Column(JSON)
    submitted_at = Column(DateTime)
    acknowledged_at = Column(DateTime)
    rejection_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    tax_return = relationship("TaxReturn", back_populates="efile_submissions")

    def __repr__(self):
        return f"<EfileSubmission {self.status} return={self.tax_return_id}>"
