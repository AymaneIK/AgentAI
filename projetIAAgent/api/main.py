from fastapi import FastAPI, Depends, File, UploadFile, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import os
import secrets
from core.db import models, crud
from core.db.database import engine, get_db
from core.parser import parse_file
from core.anonymizer import anonymize_text
from core.anthropic_client import extract_cv_data, generate_recommendation_note
from core.scorer import calculate_all_scores

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="CV Screening AI Agent API")

@app.post("/jobs")
def create_job(title: str, description: str, skills: str, education_level: str, experience_years: int, sector: str, db: Session = Depends(get_db)):
    # skills is passed as a comma-separated string for simplicity in form data
    skills_list = [s.strip() for s in skills.split(',')] if skills else []
    job = crud.create_job(db, title, description, skills_list, education_level, experience_years, sector)
    return {"id": job.id, "title": job.title}

@app.get("/jobs")
def get_jobs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    jobs = crud.get_jobs(db, skip, limit)
    return jobs

@app.post("/jobs/{job_id}/screen")
async def screen_cvs(job_id: int, background_tasks: BackgroundTasks, files: List[UploadFile] = File(...), anonymize: bool = False, db: Session = Depends(get_db)):
    job = crud.get_job(db, job_id)
    if not job:
        return {"error": "Job not found"}
    
    session = crud.create_screening_session(db, job_id)
    
    # Process files
    os.makedirs("temp_cvs", exist_ok=True)
    
    for file in files:
        file_path = f"temp_cvs/{secrets.token_hex(4)}_{file.filename}"
        with open(file_path, "wb") as f:
            f.write(await file.read())
            
        # Parse
        raw_text = parse_file(file_path)
        
        # Anonymize if requested
        if anonymize:
            raw_text = anonymize_text(raw_text)
            
        # We will dispatch processing to background tasks for true async batch
        background_tasks.add_task(process_candidate_data, db, session.id, job, raw_text, anonymize)
        
    return {"message": f"Screening session started with {len(files)} CVs", "session_id": session.id}

async def process_candidate_data(db_session, session_id, job, text, is_anonymized):
    # This needs its own db session conceptually, but for simplicity we reuse the request one or fetch a new one.
    db = next(get_db())
    try:
        # Extract fields
        extracted = await extract_cv_data(text)
        
        name = extracted.get("nom_candidat", "Anonyme") if not is_anonymized else "[MASQUÉ]"
        email = extracted.get("email") if not is_anonymized else "[MASQUÉ]"
        phone = extracted.get("telephone") if not is_anonymized else "[MASQUÉ]"
        
        candidate = crud.create_candidate(db, session_id, name, email, phone, is_anonymized, text)
        
        # Score
        job_profile_dict = {
            "required_skills": job.required_skills,
            "experience_years": job.experience_years,
            "education_level": job.education_level,
            "sector": job.sector
        }
        
        score_results = calculate_all_scores(extracted, job_profile_dict)
        final_score = score_results["final_score"]
        
        for dim, s in score_results["dimensions"].items():
            crud.add_dimension_score(db, candidate.id, dim, s, "Justification auto")
            
        # Generate note
        note = await generate_recommendation_note(job.title, job.required_skills, extracted)
        crud.update_candidate_final_score(db, candidate.id, final_score, note)
    finally:
        db.close()

@app.get("/sessions/{session_id}/results")
def get_session_results(session_id: int, db: Session = Depends(get_db)):
    candidates = crud.get_candidates_by_session(db, session_id)
    # Sort by final score descending
    candidates.sort(key=lambda c: c.final_score or 0, reverse=True)
    return [
        {
            "id": c.id,
            "name": c.name,
            "score": c.final_score,
            "recommendation": c.recommendation
        }
        for c in candidates
    ]
