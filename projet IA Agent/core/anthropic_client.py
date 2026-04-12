import os
import json
import asyncio
import random
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

async def extract_cv_data(cv_text: str) -> dict:
    if is_mock_mode:
        await asyncio.sleep(0.5) # Simulate latency
        found_skills = [s for s in ["Python", "SQL", "Docker", "Java", "C++", "React", "AWS", "Linux", "Git", "FastAPI", "Bureautique", "Management", "Marketing"] if s.lower() in cv_text.lower() or s in cv_text]
        
        # Heuristic to find the real name in the CV: first capitalized couple of words 
        lines = [line.strip() for line in cv_text.split('\n') if len(line.strip()) > 3]
        real_name = "Candidat Anonyme"
        for line in lines[:15]:
            words = line.split()
            if 1 < len(words) <= 3 and all(w and w[0].isupper() for w in words):
                real_name = line
                break
                
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
        return json.loads(resp_text[json_start:json_end])
    except:
        return {}

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
