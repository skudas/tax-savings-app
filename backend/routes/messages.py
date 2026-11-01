"""Direct messaging between clients and professionals."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from database import get_db
from models import User, Message
from .auth import get_current_user

router = APIRouter()


class MessageCreate(BaseModel):
    recipient_id: int
    content: str


class MessageResponse(BaseModel):
    id: int
    sender_id: int
    recipient_id: int
    content: str
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime]

    class Config:
        from_attributes = True


class MessageDetailResponse(MessageResponse):
    sender_email: str
    sender_name: str
    recipient_email: str
    recipient_name: str


class ConversationResponse(BaseModel):
    user_id: int
    user_email: str
    user_name: str
    last_message: Optional[str]
    last_message_at: Optional[datetime]
    unread_count: int


@router.post("/", response_model=MessageResponse)
async def send_message(
    message: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a message to another user."""
    # Verify recipient exists
    recipient = db.query(User).filter(User.id == message.recipient_id).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

    # Create message
    new_message = Message(
        sender_id=current_user.id,
        recipient_id=message.recipient_id,
        content=message.content
    )

    db.add(new_message)
    db.commit()
    db.refresh(new_message)

    return new_message


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all conversations for current user."""
    # Get unique users in conversations (both sent and received)
    from sqlalchemy import func, or_, and_

    # Get all messages involving this user
    messages = db.query(Message).filter(
        or_(
            Message.sender_id == current_user.id,
            Message.recipient_id == current_user.id
        )
    ).all()

    # Group by conversation partner
    conversations_dict = {}
    for msg in messages:
        other_user_id = msg.recipient_id if msg.sender_id == current_user.id else msg.sender_id

        if other_user_id not in conversations_dict:
            other_user = db.query(User).filter(User.id == other_user_id).first()
            conversations_dict[other_user_id] = {
                "user": other_user,
                "last_message": msg.content,
                "last_message_at": msg.created_at,
                "unread": 0
            }
        else:
            # Update if this message is newer
            if msg.created_at > conversations_dict[other_user_id]["last_message_at"]:
                conversations_dict[other_user_id]["last_message"] = msg.content
                conversations_dict[other_user_id]["last_message_at"] = msg.created_at

        # Count unread messages from this user
        if msg.recipient_id == current_user.id and not msg.is_read:
            conversations_dict[other_user_id]["unread"] += 1

    # Format response
    conversations = []
    for other_user_id, data in conversations_dict.items():
        other_user = data["user"]
        conversations.append(ConversationResponse(
            user_id=other_user.id,
            user_email=other_user.email,
            user_name=f"{other_user.first_name} {other_user.last_name}",
            last_message=data["last_message"],
            last_message_at=data["last_message_at"],
            unread_count=data["unread"]
        ))

    # Sort by last message time (newest first)
    conversations.sort(key=lambda x: x.last_message_at or datetime.min, reverse=True)

    return conversations


@router.get("/with/{user_id}", response_model=List[MessageDetailResponse])
async def get_conversation(
    user_id: int,
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get conversation history with a specific user."""
    # Verify the other user exists
    other_user = db.query(User).filter(User.id == user_id).first()
    if not other_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get messages between these two users
    messages = db.query(Message).filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.created_at.desc()).offset(skip).limit(limit).all()

    # Mark messages as read
    unread_messages = db.query(Message).filter(
        (Message.sender_id == user_id) &
        (Message.recipient_id == current_user.id) &
        (Message.is_read == False)
    ).all()

    for msg in unread_messages:
        msg.is_read = True
        msg.read_at = datetime.utcnow()

    db.commit()

    # Format response
    result = []
    for msg in reversed(messages):  # Reverse to get chronological order
        result.append(MessageDetailResponse(
            id=msg.id,
            sender_id=msg.sender_id,
            recipient_id=msg.recipient_id,
            content=msg.content,
            is_read=msg.is_read,
            created_at=msg.created_at,
            read_at=msg.read_at,
            sender_email=msg.sender.email,
            sender_name=f"{msg.sender.first_name} {msg.sender.last_name}",
            recipient_email=msg.recipient.email,
            recipient_name=f"{msg.recipient.first_name} {msg.recipient.last_name}"
        ))

    return result


@router.get("/unread", response_model=dict)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get count of unread messages."""
    unread_count = db.query(Message).filter(
        (Message.recipient_id == current_user.id) &
        (Message.is_read == False)
    ).count()

    return {"unread_count": unread_count}


@router.put("/{message_id}/read", response_model=MessageResponse)
async def mark_as_read(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a message as read."""
    message = db.query(Message).filter(Message.id == message_id).first()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Only recipient can mark as read
    if message.recipient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot mark message as read")

    message.is_read = True
    message.read_at = datetime.utcnow()

    db.commit()
    db.refresh(message)

    return message


@router.delete("/{message_id}")
async def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a message (soft delete by marking as archived)."""
    message = db.query(Message).filter(Message.id == message_id).first()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Only sender or recipient can delete
    if message.sender_id != current_user.id and message.recipient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot delete message")

    db.delete(message)
    db.commit()

    return {"message": "Message deleted"}
