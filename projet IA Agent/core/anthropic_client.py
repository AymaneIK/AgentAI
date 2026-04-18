import os
import json
import asyncio
import random
import re
import unicodedata
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from .prompts import CV_EXTRACTION_PROMPT, RECOMMENDATION_PROMPT, SINGLE_CANDIDATE_NOTE_PROMPT

# Force dotenv to look directly in the project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, '.env'))

api_key = os.getenv("ANTHROPIC_API_KEY")
is_mock_mode = False

if not api_key or api_key == "sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" or api_key == "dummy_key_awaiting_user_setup":
    api_key = "dummy_key_awaiting_user_setup"
    is_mock_mode = True

client = AsyncAnthropic(api_key=api_key)
MODEL_NAME = "claude-3-5-sonnet-20240620"

NAME_SECTION_HEADERS = {
    "about me",
    "a propos",
    "a propos de moi",
    "apropos",
    "apropos de moi",
    "profile",
    "profil",
    "profil professionnel",
    "professional summary",
    "summary",
    "resume summary",
    "objective",
    "career objective",
    "contact",
    "contact info",
    "informations personnelles",
    "personal information",
    "coordonnees",
    "coordonnees personnelles",
    "skills",
    "competences",
    "competences techniques",
    "technical skills",
    "experience",
    "work experience",
    "experiences",
    "education",
    "formation",
    "curriculum vitae",
    "cv",
}


def _normalize_text(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_value).strip().lower()


def _clean_name_candidate(line: str) -> str:
    cleaned = re.sub(r"[\|\u2022\u2023\u25E6\u2043\u2219]+", " ", line or "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(" -,:;/\\()[]{}")
    return cleaned


def _looks_like_person_name(value: str) -> bool:
    candidate = _clean_name_candidate(value)
    if not candidate or len(candidate) < 4 or len(candidate) > 60:
        return False
    if any(char.isdigit() for char in candidate):
        return False
    if "@" in candidate or "http" in candidate.lower():
        return False

    normalized = _normalize_text(candidate)
    if normalized in NAME_SECTION_HEADERS:
        return False
    if any(header in normalized for header in NAME_SECTION_HEADERS):
        return False

    tokens = candidate.split()
    if len(tokens) < 2 or len(tokens) > 4:
        return False

    allowed_token = re.compile(r"^[A-Za-z][A-Za-z'.-]*$")
    lowercase_noise = {
        "about", "me", "profil", "profile", "summary", "objective", "contact",
        "skills", "experience", "education", "formation", "curriculum", "vitae",
        "de", "du", "des", "sur", "avec", "pour", "dans", "the", "and",
    }
    uppercase_tokens = 0
    for token in tokens:
        stripped = token.strip(".")
        if not stripped or not allowed_token.match(stripped):
            return False
        if _normalize_text(stripped) in lowercase_noise:
            return False
        if stripped[0].isupper():
            uppercase_tokens += 1

    return uppercase_tokens >= 2


def extract_candidate_name_from_text(cv_text: str) -> str:
    lines = [_clean_name_candidate(line) for line in cv_text.splitlines()]
    lines = [line for line in lines if len(line) >= 4]

    for line in lines[:20]:
        if _looks_like_person_name(line):
            return line

    return "Candidat Anonyme"


def sanitize_candidate_name(raw_name: str | None, cv_text: str) -> str:
    if raw_name and _looks_like_person_name(raw_name):
        return _clean_name_candidate(raw_name)
    return extract_candidate_name_from_text(cv_text)

async def extract_cv_data(cv_text: str) -> dict:
    if is_mock_mode:
        await asyncio.sleep(0.5) # Simulate latency
        found_skills = [s for s in ["Python", "SQL", "Docker", "Java", "C++", "React", "AWS", "Linux", "Git", "FastAPI", "Bureautique", "Management", "Marketing"] if s.lower() in cv_text.lower() or s in cv_text]

        real_name = extract_candidate_name_from_text(cv_text)
                
        seed_value = len(cv_text) if cv_text else random.randint(100, 900)
        
        return {
            "nom_candidat": real_name,
            "email": f"{real_name.lower().replace(' ', '.')}@demo.io",
            "telephone": f"06 {seed_value % 99:02} 23 45 67",
            "education_niveau": ["Bac+2", "Bac+3", "Bac+4", "Bac+5"][seed_value % 4],
            "annees_experience_totales": (seed_value % 10) + 1,
            "competences_techniques": found_skills if found_skills else ["Communication"],
            "langues_parlees": ["Français", "Anglais"] if seed_value % 2 == 0 else ["Français", "Espagnol"],
            "secteurs_activite": ["Tech", "Finance", "Ingénierie"][seed_value % 3],
            "nombre_experiences_precedentes": (seed_value % 5) + 1
        }

    prompt = CV_EXTRACTION_PROMPT.format(cv_text=cv_text)
    
    response = await client.messages.create(
        model=MODEL_NAME, max_tokens=1024, temperature=0.0,
        messages=[{"role": "user", "content": prompt}]
    )
    
    resp_text = response.content[0].text
    try:
        json_start = resp_text.find('{')
        json_end = resp_text.rfind('}') + 1
        parsed = json.loads(resp_text[json_start:json_end])
        parsed["nom_candidat"] = sanitize_candidate_name(parsed.get("nom_candidat"), cv_text)
        return parsed
    except:
        return {"nom_candidat": extract_candidate_name_from_text(cv_text)}

async def generate_recommendation_note(job_title: str, required_skills: str, candidate_data: dict) -> str:
    if is_mock_mode:
        return f"[MODE CLAUDE DEMO] Analyse : Bonne compatibilité technique générale ({len(candidate_data.get('competences_techniques', []))} skills trouvés) pour le rôle de {job_title}."

    prompt = SINGLE_CANDIDATE_NOTE_PROMPT.format(
        job_title=job_title, required_skills=required_skills,
        candidate_data=json.dumps(candidate_data, ensure_ascii=False)
    )
    
    response = await client.messages.create(
        model=MODEL_NAME, max_tokens=256, temperature=0.5,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

async def generate_comparison(job_title: str, job_desc: str, candidates_info: str) -> str:
    if is_mock_mode:
        return "[MODE DEMO] Le candidat avec le meilleur score mathématique global devrait théoriquement être le meilleur choix d'après les pondérations."

    prompt = RECOMMENDATION_PROMPT.format(
        job_title=job_title, job_description=job_desc, candidates_data=candidates_info
    )
    
    response = await client.messages.create(
        model=MODEL_NAME, max_tokens=1024, temperature=0.2,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
