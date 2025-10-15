from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship

from .base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    memberships = relationship("Membership", back_populates="user")
    assigned_tasks = relationship("Task", back_populates="assignee")
    otp_codes = relationship("OtpCode", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user")