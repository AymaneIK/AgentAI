from sqlalchemy.orm import Session
from . import models
import json
import bcrypt

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, username: str, password: str):
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db_user = models.User(username=username, password_hash=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_job(db: Session, job_id: int):
    return db.query(models.JobProfile).filter(models.JobProfile.id == job_id).first()

def get_jobs(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.JobProfile).offset(skip).limit(limit).all()

def create_job(db: Session, title: str, description: str, skills: list, education_level: str, experience_years: int, sector: str):
    db_job = models.JobProfile(
        title=title, 
        description=description, 
        required_skills=json.dumps(skills),
        required_languages=json.dumps([]),
        education_level=education_level,
        experience_years=experience_years,
        sector=sector
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job

def create_screening_session(db: Session, job_id: int):
    db_session = models.ScreeningSession(job_id=job_id)
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

def create_candidate(db: Session, session_id: int, name: str, email: str, phone: str, is_anonymized: bool, original_text: str):
    db_candidate = models.Candidate(
        session_id=session_id,
        name=name,
        email=email,
        phone=phone,
        is_anonymized=is_anonymized,
        original_text=original_text
    )
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    return db_candidate

def add_dimension_score(db: Session, candidate_id: int, dimension_name: str, score: float, justification: str):
    db_score = models.DimensionScore(
        candidate_id=candidate_id,
        dimension_name=dimension_name,
        score=score,
        justification=justification
    )
    db.add(db_score)
    db.commit()
    db.refresh(db_score)
    return db_score

def update_candidate_final_score(db: Session, candidate_id: int, final_score: float, recommendation: str, is_fit: bool = True, rejection_reason: str = None):
    db_candidate = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    if db_candidate:
        db_candidate.final_score = final_score
        db_candidate.recommendation = recommendation
        db_candidate.is_fit = is_fit
        db_candidate.rejection_reason = rejection_reason
        db.commit()
        db.refresh(db_candidate)
    return db_candidate

def get_candidates_by_session(db: Session, session_id: int):
    return db.query(models.Candidate).filter(models.Candidate.session_id == session_id).all()


def upsert_singleton_job(
    db: Session,
    title: str,
    description: str,
    skills: list,
    education_level: str,
    experience_years: int,
    sector: str,
    languages: list | None = None,
):
    job = db.query(models.JobProfile).order_by(models.JobProfile.id.asc()).first()
    serialized_skills = json.dumps(skills)
    serialized_languages = json.dumps(languages or [])

    if job is None:
        job = models.JobProfile(
            title=title,
            description=description,
            required_skills=serialized_skills,
            required_languages=serialized_languages,
            education_level=education_level,
            experience_years=experience_years,
            sector=sector,
        )
        db.add(job)
    else:
        job.title = title
        job.description = description
        job.required_skills = serialized_skills
        job.required_languages = serialized_languages
        job.education_level = education_level
        job.experience_years = experience_years
        job.sector = sector

    db.commit()
    db.refresh(job)
    return job
