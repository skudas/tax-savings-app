"""
Dashboard routes: transactions and summary.
"""

from fastapi import APIRouter, HTTPException, Depends, Cookie, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import csv
import io

from database import get_db
from models import User, Transaction, Category, AuditLog
from auth import get_session
from transaction_categorizer import TransactionCategorizer
from encryption import encrypt

router = APIRouter()


def get_current_user(session: Optional[str] = Cookie(None), db: Session = Depends(get_db)) -> User:
    """Get current logged-in user."""
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Session expired")

    user = db.query(User).filter(User.id == session_data["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.get("/categories")
async def get_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get transaction categories for user."""
    categories = db.query(Category).filter(Category.user_id == current_user.id).all()

    # Create default categories if none exist
    if not categories:
        defaults = [
            ("Income", "income"),
            ("Expenses", "expense"),
            ("Software", "expense"),
            ("Travel", "expense"),
            ("Meals", "expense"),
            ("Office Supplies", "expense"),
        ]
        for name, type_ in defaults:
            cat = Category(user_id=current_user.id, name=name, type=type_)
            db.add(cat)
        db.commit()
        categories = db.query(Category).filter(Category.user_id == current_user.id).all()

    return [
        {"id": c.id, "name": c.name, "type": c.type}
        for c in categories
    ]


@router.post("/transactions/upload")
async def upload_transactions(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload transactions via CSV.

    CSV format: date, amount, description, bank_account_last_4
    Date format: YYYY-MM-DD
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be CSV")

    try:
        content = await file.read()
        reader = csv.DictReader(io.StringIO(content.decode()))

        uploaded_count = 0
        categorizer = TransactionCategorizer()

        for row in reader:
            # Parse row
            date = datetime.strptime(row["date"], "%Y-%m-%d")
            amount = float(row["amount"])
            description = row["description"]
            bank_account_last_4 = row.get("bank_account_last_4", "")

            # Encrypt bank account (never store full number)
            encrypted_account = encrypt(bank_account_last_4) if bank_account_last_4 else None

            # Try to auto-categorize
            suggestion = categorizer.suggest_category(description)
            category_id = None
            if suggestion:
                category_name = suggestion[0]
                cat = db.query(Category).filter(
                    Category.user_id == current_user.id,
                    Category.name == category_name
                ).first()
                if not cat:
                    # Create category if it doesn't exist
                    cat = Category(
                        user_id=current_user.id,
                        name=category_name,
                        type="income" if amount > 0 else "expense"
                    )
                    db.add(cat)
                    db.flush()
                category_id = cat.id

            # Create transaction
            txn = Transaction(
                user_id=current_user.id,
                date=date,
                amount=amount,
                description=description,
                bank_account_last_4=encrypted_account,
                category_id=category_id,
            )
            db.add(txn)
            uploaded_count += 1

        db.commit()
        return {"uploaded_count": uploaded_count}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing CSV: {str(e)}")


@router.get("/transactions")
async def get_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all transactions for user."""
    transactions = db.query(Transaction).filter(
        Transaction.user_id == current_user.id
    ).order_by(Transaction.date.desc()).all()

    return [
        {
            "id": t.id,
            "date": t.date.isoformat(),
            "amount": t.amount,
            "description": t.description,
            "category_id": t.category_id,
            "category_name": t.category.name if t.category else None,
        }
        for t in transactions
    ]


@router.patch("/transactions/{transaction_id}")
async def update_transaction(
    transaction_id: int,
    category_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update transaction category."""
    txn = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id
    ).first()

    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Log the change
    old_value = {"category_id": txn.category_id}

    txn.category_id = category_id
    db.commit()

    # Create audit log entry
    audit = AuditLog(
        user_id=current_user.id,
        entity_type="Transaction",
        entity_id=transaction_id,
        action="update",
        old_value_json=old_value,
        new_value_json={"category_id": category_id},
    )
    db.add(audit)
    db.commit()

    return {"message": "Transaction updated"}


@router.get("/summary")
async def get_monthly_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get monthly income/expense summary."""
    from sqlalchemy import func
    from datetime import datetime, timedelta

    # Get transactions from last 12 months
    cutoff_date = datetime.utcnow() - timedelta(days=365)

    transactions = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= cutoff_date
    ).all()

    # Group by month
    summary = {}
    for txn in transactions:
        month_key = txn.date.strftime("%Y-%m")
        if month_key not in summary:
            summary[month_key] = {"income": 0, "expenses": 0, "net": 0}

        if txn.amount > 0:
            summary[month_key]["income"] += txn.amount
        else:
            summary[month_key]["expenses"] += abs(txn.amount)

        summary[month_key]["net"] = summary[month_key]["income"] - summary[month_key]["expenses"]

    return [
        {"month": month, **data}
        for month, data in sorted(summary.items())
    ]
