from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
import bcrypt
import os
import sys
import json
import asyncio
from werkzeug.utils import secure_filename
import secrets

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.db.database import SessionLocal, engine, migrate_sqlite_schema
from core.db import models, crud
from core.parser import parse_file
from core.anonymizer import anonymize_text
from core.anthropic_client import extract_cv_data, generate_recommendation_note
from core.scorer import calculate_all_scores
from core.excel_export import export_session_to_excel

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_dev_key")

PROJECT_JOB_PROFILE = {
    "title": "Charge(e) de Recrutement - Secteur Automobile",
    "description": (
        "Responsable du processus de recrutement pour une entreprise du secteur "
        "automobile: diffusion des offres, sourcing, tri des candidatures, "
        "entretiens, coordination avec les managers et suivi administratif."
    ),
    "skills": [
        "Recrutement",
        "Sourcing",
        "Tri des candidatures",
        "Preselection",
        "Conduite d'entretiens",
        "Redaction d'offres d'emploi",
        "Evaluation des candidats",
        "Communication professionnelle",
        "Organisation",
        "Outils de recrutement digitaux",
        "LinkedIn",
        "Indeed",
        "Confidentialite",
    ],
    "languages": ["Francais", "Anglais"],
    "education_level": "Bac+2",
    "experience_years": 1,
    "sector": "Automobile",
}

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

models.Base.metadata.create_all(bind=engine)
migrate_sqlite_schema()


def ensure_project_job_profile(db):
    return crud.upsert_singleton_job(
        db,
        title=PROJECT_JOB_PROFILE["title"],
        description=PROJECT_JOB_PROFILE["description"],
        skills=PROJECT_JOB_PROFILE["skills"],
        education_level=PROJECT_JOB_PROFILE["education_level"],
        experience_years=PROJECT_JOB_PROFILE["experience_years"],
        sector=PROJECT_JOB_PROFILE["sector"],
        languages=PROJECT_JOB_PROFILE["languages"],
    )


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


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = SessionLocal()
        user = crud.get_user_by_username(db, username)
        db.close()

        if user and bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
            auth_user = UserAuth(user.id, user.username)
            login_user(auth_user)
            return redirect(url_for("dashboard"))

        flash("Invalid username or password")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    db = SessionLocal()
    try:
        job = ensure_project_job_profile(db)
        sessions = db.query(models.ScreeningSession).order_by(models.ScreeningSession.timestamp.desc()).all()
        return render_template(
            "dashboard.html",
            job=job,
            sessions=sessions,
            job_skills=json.loads(job.required_skills or "[]"),
            job_languages=json.loads(job.required_languages or "[]"),
        )
    finally:
        db.close()


@app.route("/scoring-rules")
@login_required
def scoring_rules():
    return render_template("scoring_rules.html")


async def process_single_cv(job_id, session_id, path, is_anonymized, job_profile_dict):
    db = SessionLocal()
    try:
        job = crud.get_job(db, job_id)

        text = parse_file(path)
        if is_anonymized:
            text = anonymize_text(text)

        extracted = await extract_cv_data(text)

        name = extracted.get("nom_candidat", "Anonyme") if not is_anonymized else "[MASQUE]"
        email = extracted.get("email") if not is_anonymized else "[MASQUE]"
        phone = extracted.get("telephone") if not is_anonymized else "[MASQUE]"

        original_text_with_json = text + " ----JSON---- " + json.dumps(
            extracted.get("competences_techniques", [])
        )
        candidate = crud.create_candidate(
            db, session_id, name, email, phone, is_anonymized, original_text_with_json
        )

        score_results = calculate_all_scores(extracted, job_profile_dict)
        final_score = score_results["final_score"]
        is_fit = score_results["is_fit"]
        rejection_reason = score_results["rejection_reason"]

        for dim, score in score_results["dimensions"].items():
            crud.add_dimension_score(db, candidate.id, dim, score, "Scoring IA")

        if is_fit:
            note = await generate_recommendation_note(job.title, job.required_skills, extracted)
        else:
            note = "REJETE: " + rejection_reason

        crud.update_candidate_final_score(
            db, candidate.id, final_score, note, is_fit, rejection_reason
        )
    finally:
        db.close()


async def batch_dispatcher(job_id, session_id, saved_files, is_anonymized, job_profile_dict):
    tasks = [
        process_single_cv(job_id, session_id, path, is_anonymized, job_profile_dict)
        for path in saved_files
    ]
    await asyncio.gather(*tasks)


@app.route("/job/screen", methods=["POST"])
def screen_job():
    db = SessionLocal()
    job = ensure_project_job_profile(db)
    job_id = job.id

    is_anonymized = request.form.get("anonymize") == "true"
    files = request.files.getlist("cv_files")

    if not files:
        flash("Aucun fichier selectionne.")
        db.close()
        return redirect(url_for("dashboard"))

    session = crud.create_screening_session(db, job_id)

    os.makedirs("temp_cvs", exist_ok=True)

    job_profile_dict = {
        "required_skills": job.required_skills,
        "required_languages": job.required_languages,
        "experience_years": job.experience_years,
        "education_level": job.education_level,
        "sector": job.sector,
    }

    saved_files = []
    for cv_file in files:
        if cv_file.filename == "":
            continue
        filename = secure_filename(cv_file.filename)
        path = os.path.join("temp_cvs", f"{secrets.token_hex(4)}_{filename}")
        cv_file.save(path)
        saved_files.append(path)

    db.close()

    if saved_files:
        asyncio.run(batch_dispatcher(job_id, session.id, saved_files, is_anonymized, job_profile_dict))

    flash(f"{len(saved_files)} CVs analyses avec succes.")
    return redirect(url_for("dashboard"))


@app.route("/export/<int:session_id>")
@login_required
def export_session(session_id):
    db = SessionLocal()
    try:
        candidates = crud.get_candidates_by_session(db, session_id)
        if not candidates:
            flash("Aucun resultat pour cette session")
            return redirect(url_for("dashboard"))

        filename = f"export_session_{session_id}.xlsx"
        export_session_to_excel(candidates, filename)
        return send_file(filename, as_attachment=True)
    finally:
        db.close()


@app.route("/analytics")
@login_required
def analytics():
    db = SessionLocal()
    sessions = db.query(models.ScreeningSession).all()
    candidates = []
    missing_skills_tally = {}

    for screening_session in sessions:
        job = screening_session.job_profile
        job_skills = json.loads(job.required_skills) if job.required_skills else []
        candidates.extend(screening_session.candidates)

        for candidate in screening_session.candidates:
            if " ----JSON---- " in candidate.original_text:
                json_part = candidate.original_text.split(" ----JSON---- ")[-1]
                try:
                    cand_skills = json.loads(json_part)
                    cand_skills_lower = [str(skill).lower() for skill in cand_skills]
                    for job_skill in job_skills:
                        if job_skill.lower() not in cand_skills_lower:
                            missing_skills_tally[job_skill] = missing_skills_tally.get(job_skill, 0) + 1
                except Exception:
                    pass

    scores = [candidate.final_score for candidate in candidates if candidate.final_score is not None]
    dim_sums = {}
    dim_counts = {}
    radar_data = []

    for candidate in candidates:
        candidate_dimensions = {}
        for dimension in candidate.dimension_scores:
            dim_sums[dimension.dimension_name] = dim_sums.get(dimension.dimension_name, 0) + dimension.score
            dim_counts[dimension.dimension_name] = dim_counts.get(dimension.dimension_name, 0) + 1
            candidate_dimensions[dimension.dimension_name] = dimension.score

        radar_data.append({"name": candidate.name, "dimensions": candidate_dimensions})

    avg_dimensions = {key: round(dim_sums[key] / dim_counts[key], 1) for key in dim_sums}
    top_missing_skills = sorted(missing_skills_tally.items(), key=lambda item: item[1], reverse=True)[:5]

    try:
        return render_template(
            "analytics.html",
            scores=scores,
            avg_dimensions=avg_dimensions,
            radar_data=radar_data,
            top_missing_skills=top_missing_skills,
        )
    finally:
        db.close()


@app.route("/compare", methods=["GET"])
@login_required
def compare():
    ids = request.args.get("ids", "")
    if not ids:
        return "Select candidates to compare", 400

    id_list = [int(item) for item in ids.split(",") if item.isdigit()]
    db = SessionLocal()
    try:
        candidates = db.query(models.Candidate).filter(models.Candidate.id.in_(id_list)).all()
        candidates.sort(key=lambda candidate: candidate.final_score or 0, reverse=True)
        return render_template("compare.html", candidates=candidates)
    finally:
        db.close()


if __name__ == "__main__":
    db = SessionLocal()
    ensure_project_job_profile(db)
    admin = crud.get_user_by_username(db, "admin")
    if not admin:
        crud.create_user(db, "admin", "admin")
    db.close()
    app.run(debug=True, port=5000)
