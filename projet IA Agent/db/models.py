from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
import json
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)

class JobProfile(Base):
    __tablename__ = "job_profiles"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    required_skills = Column(Text) # JSON string
    required_languages = Column(Text, default="[]") # JSON string
    education_level = Column(String) # e.g. "Bac+5"
    experience_years = Column(Integer)
    sector = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("ScreeningSession", back_populates="job_profile", cascade="all, delete-orphan")

class ScreeningSession(Base):
    __tablename__ = "screening_sessions"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("job_profiles.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    job_profile = relationship("JobProfile", back_populates="sessions")
    candidates = relationship("Candidate", back_populates="session", cascade="all, delete-orphan")

class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("screening_sessions.id"))
    name = Column(String, default="Anonyme")
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    is_anonymized = Column(Boolean, default=False)
    original_text = Column(Text)
    
    # Final aggregated score
    is_fit = Column(Boolean, default=True)
    rejection_reason = Column(Text, nullable=True)
    final_score = Column(Float, nullable=True)
    recommendation = Column(Text, nullable=True) # Claude's hiring note

    session = relationship("ScreeningSession", back_populates="candidates")
    dimension_scores = relationship("DimensionScore", back_populates="candidate", cascade="all, delete-orphan")

class DimensionScore(Base):
    __tablename__ = "dimension_scores"
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    dimension_name = Column(String)
    score = Column(Float)
    justification = Column(Text)

    candidate = relationship("Candidate", back_populates="dimension_scores")
