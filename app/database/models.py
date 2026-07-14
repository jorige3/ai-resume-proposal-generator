from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DbUserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # SQLite JSON columns will host the nested lists/Pydantic schemas
    skills: Mapped[List[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    experience: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    projects: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    education: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    certifications: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Backwards relation with cascade deletions
    sessions: Mapped[List["DbGenerationSession"]] = relationship(
        "DbGenerationSession",
        back_populates="profile",
        cascade="all, delete-orphan",
    )


class DbGenerationSession(Base):
    __tablename__ = "generation_sessions"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_profiles.id"), nullable=False
    )
    job_title: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    job_description: Mapped[str] = mapped_column(String, nullable=False)

    # Stored outputs/analysis structures
    job_analysis: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    match_score: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    generated_resume: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    generated_proposal: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    profile: Mapped["DbUserProfile"] = relationship(
        "DbUserProfile", back_populates="sessions"
    )
