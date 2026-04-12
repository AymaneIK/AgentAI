from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import bcrypt
import os
import sys
import json
import asyncio
from werkzeug.utils import secure_filename
import secrets

# Ensure parent directory is in path to import db and core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import SessionLocal, engine
from db import models, crud
from core.parser import parse_file
from core.anonymizer import anonymize_text
from core.anthropic_client import extract_cv_data, generate_recommendation_note
from core.scorer import calculate_all_scores
from core.excel_export import export_session_to_excel

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_dev_key")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

models.Base.metadata.create_all(bind=engine)

class UserAuth(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    db = SessionLocal()
    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    db.close()
    if user:
        return UserAuth(user.id, user.username)
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = SessionLocal()
        user = crud.get_user_by_username(db, username)
        db.close()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            auth_user = UserAuth(user.id, user.username)
            login_user(auth_user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    db = SessionLocal()
    try:
        jobs = crud.get_jobs(db)
        sessions = db.query(models.ScreeningSession).order_by(models.ScreeningSession.timestamp.desc()).all()
        return render_template('dashboard.html', jobs=jobs, sessions=sessions)
    finally:
        db.close()

@app.route('/job/create', methods=['POST'])
@login_required
def create_job():
    db = SessionLocal()
    title = request.form['title']
    description = request.form['description']
    skills = [s.strip() for s in request.form['skills'].split(',')]
    education_level = request.form['education_level']
    experience_years = int(request.form['experience_years'])
    sector = request.form['sector']
    
    crud.create_job(db, title, description, skills, education_level, experience_years, sector)
    db.close()
    flash("Fiche de poste créée !")
    return redirect(url_for('dashboard'))

async def process_single_cv(job_id, session_id, path, is_anonymized, job_profile_dict):
    db = SessionLocal()
    try:
        job = crud.get_job(db, job_id)
        
        text = parse_file(path)
        if is_anonymized:
            text = anonymize_text(text)
            
        # Heavy IO bound Async calls to Claude!
        extracted = await extract_cv_data(text)
        
        name = extracted.get("nom_candidat", "Anonyme") if not is_anonymized else "[MASQUÉ]"
        email = extracted.get("email") if not is_anonymized else "[MASQUÉ]"
        phone = extracted.get("telephone") if not is_anonymized else "[MASQUÉ]"
        
        original_text_with_json = text + " ----JSON---- " + json.dumps(extracted.get("competences_techniques", []))
        candidate = crud.create_candidate(db, session_id, name, email, phone, is_anonymized, original_text_with_json)
        
        score_results = calculate_all_scores(extracted, job_profile_dict)
        final_score = score_results["final_score"]
        
        for dim, s in score_results["dimensions"].items():
            crud.add_dimension_score(db, candidate.id, dim, s, "Scoring IA")
            
        note = await generate_recommendation_note(job.title, job.required_skills, extracted)
        crud.update_candidate_final_score(db, candidate.id, final_score, note)
    finally:
        db.close()

async def batch_dispatcher(job_id, session_id, saved_files, is_anonymized, job_profile_dict):
    # Run all CV extractions and scorings completely concurrently using asyncio
    tasks = [process_single_cv(job_id, session_id, path, is_anonymized, job_profile_dict) for path in saved_files]
    await asyncio.gather(*tasks)

@app.route('/job/screen', methods=['POST'])
def screen_job():
    job_id = int(request.form['job_id'])
    is_anonymized = request.form.get('anonymize') == 'true'
    files = request.files.getlist('cv_files')
    
    if not files:
        flash("Aucun fichier sélectionné.")
        return redirect(url_for('dashboard'))
        
    db = SessionLocal()
    job = crud.get_job(db, job_id)
    session = crud.create_screening_session(db, job_id)
    
    os.makedirs("temp_cvs", exist_ok=True)
    
    job_profile_dict = {
        "required_skills": job.required_skills,
        "experience_years": job.experience_years,
        "education_level": job.education_level,
        "sector": job.sector
    }
        
    saved_files = []
    for cv_file in files:
        if cv_file.filename == '':
            continue
        filename = secure_filename(cv_file.filename)
        path = os.path.join("temp_cvs", f"{secrets.token_hex(4)}_{filename}")
        cv_file.save(path)
        saved_files.append(path)
        
    db.close()
    
    # Execute truly concurrent async operations blocking the synchronous Flask route safely
    if saved_files:
        asyncio.run(batch_dispatcher(job_id, session.id, saved_files, is_anonymized, job_profile_dict))
        
    flash(f"{len(saved_files)} CVs analysés avec succès !")
    return redirect(url_for('dashboard'))

@app.route('/export/<int:session_id>')
@login_required
def export_session(session_id):
    db = SessionLocal()
    try:
        candidates = crud.get_candidates_by_session(db, session_id)
        if not candidates:
            flash("Aucun résultat pour cette session")
            return redirect(url_for('dashboard'))
        
        filename = f"export_session_{session_id}.xlsx"
        export_session_to_excel(candidates, filename)
        return send_file(filename, as_attachment=True)
    finally:
        db.close()

@app.route('/analytics')
@login_required
def analytics():
    db = SessionLocal()
    sessions = db.query(models.ScreeningSession).all()
    candidates = []
    
    # Track skills missing for gap analysis
    missing_skills_tally = {}

    for s in sessions:
        job = s.job_profile
        job_skills = json.loads(job.required_skills) if job.required_skills else []
        candidates.extend(s.candidates)
        
        for cand in s.candidates:
            # We sneaked the extracted skills into original_text after " ----JSON---- "
            if " ----JSON---- " in cand.original_text:
                json_part = cand.original_text.split(" ----JSON---- ")[-1]
                try:
                    cand_skills = json.loads(json_part)
                    cand_skills_lower = [str(sk).lower() for sk in cand_skills]
                    for j_skill in job_skills:
                        if j_skill.lower() not in cand_skills_lower:
                            missing_skills_tally[j_skill] = missing_skills_tally.get(j_skill, 0) + 1
                except:
                    pass

    # Basic data
    scores = [c.final_score for c in candidates if c.final_score is not None]
    
    # Average dimensions
    dim_sums = {}
    dim_counts = {}
    radar_data = []

    for c in candidates:
        c_dims = {}
        for d in c.dimension_scores:
            dim_sums[d.dimension_name] = dim_sums.get(d.dimension_name, 0) + d.score
            dim_counts[d.dimension_name] = dim_counts.get(d.dimension_name, 0) + 1
            c_dims[d.dimension_name] = d.score
        
        radar_data.append({"name": c.name, "dimensions": c_dims})

    avg_dimensions = { k: round(dim_sums[k]/dim_counts[k], 1) for k in dim_sums }

    # Top skills missing
    top_missing_skills = sorted(missing_skills_tally.items(), key=lambda x: x[1], reverse=True)[:5]
    
    try:
        return render_template('analytics.html', 
                               scores=scores, 
                               avg_dimensions=avg_dimensions, 
                               radar_data=radar_data,
                               top_missing_skills=top_missing_skills)
    finally:
        db.close()

@app.route('/compare', methods=['GET'])
@login_required
def compare():
    ids = request.args.get('ids', '')
    if not ids:
        return "Select candidates to compare", 400
        
    id_list = [int(i) for i in ids.split(',') if i.isdigit()]
    db = SessionLocal()
    try:
        candidates = db.query(models.Candidate).filter(models.Candidate.id.in_(id_list)).all()
        candidates.sort(key=lambda x: x.final_score or 0, reverse=True)
        return render_template('compare.html', candidates=candidates)
    finally:
        db.close()

if __name__ == '__main__':
    db = SessionLocal()
    admin = crud.get_user_by_username(db, "admin")
    if not admin:
        crud.create_user(db, "admin", "admin")
    db.close()
    app.run(debug=True, port=5000)
