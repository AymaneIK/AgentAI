import re
import json
from difflib import SequenceMatcher

WEIGHTS = {
    "annees_experience": 0.20,
    "niveau_etude": 0.15,
    "competences_techniques": 0.30,
    "langues_parlees": 0.10,
    "secteur_activite": 0.15,
    "nombre_experiences": 0.10
}

def parse_bac_level(bac_str: str) -> int:
    """Extracts integer N from 'Bac+N', defaults to 0"""
    if not bac_str or type(bac_str) is not str:
        return 0
    match = re.search(r'Bac\s*\+\s*(\d+)', bac_str, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0

def score_experience(cand_exp: int, req_exp: int) -> float:
    if req_exp == 0:
        return min(100.0, 50.0 + (cand_exp * 5))
    if cand_exp == req_exp:
        return 100.0
    if cand_exp > req_exp:
        # Overqualification slightly rewarded but strictly capped at 100
        return min(100.0, 80.0 + (cand_exp - req_exp) * 5.0)
    return max(0.0, (cand_exp / req_exp) * 100.0)

def score_education(cand_bac: str, req_bac: str) -> float:
    cand_level = parse_bac_level(cand_bac)
    req_level = parse_bac_level(req_bac)
    
    if cand_level == req_level:
        return 100.0
    if cand_level > req_level:
        return 100.0
    if cand_level == req_level - 1:
        return 75.0
    if cand_level == req_level - 2:
        return 50.0
    return 10.0

def fuzzy_match(s1: str, s2: str) -> float:
    ratio = SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
    return ratio if ratio > 0.6 else 0.0

def score_skills(cand_skills: list, req_skills: list) -> float:
    if not req_skills:
        return 100.0 if cand_skills else 50.0
    if not cand_skills:
        return 0.0
    
    matches_score = 0.0
    for req in req_skills:
        best_match = max([fuzzy_match(req, cand) for cand in cand_skills] + [0.0])
        matches_score += (best_match ** 2)
        
    base_score = (matches_score / len(req_skills)) * 100.0
    bonus = min(10.0, len(cand_skills) * 1.5)
    
    return min(100.0, base_score + bonus)

def score_languages(cand_langs: list, req_langs: list) -> float:
    if not req_langs:
        return 100.0 if cand_langs else 50.0
    if not cand_langs:
        return 0.0
        
    matches = 0
    for req in req_langs:
        best_match = max([fuzzy_match(req, cand) for cand in cand_langs] + [0.0])
        matches += best_match
    return min(100.0, (matches / len(req_langs)) * 100.0)

def score_sector(cand_sectors: list, req_sector: str) -> float:
    if not req_sector:
        return 100.0
    if not cand_sectors:
        return 10.0
    best_match = max([fuzzy_match(req_sector, c_sec) for c_sec in cand_sectors] + [0.0])
    return min(100.0, best_match * 100.0)

def score_num_experiences(num_exp: int) -> float:
    curve = {0: 10.0, 1: 40.0, 2: 75.0, 3: 95.0, 4: 100.0, 5: 100.0}
    return curve.get(num_exp, 100.0)

def calculate_all_scores(candidate_data: dict, job_profile: dict) -> dict:
    req_skills = json.loads(job_profile.get("required_skills", "[]"))
    req_exp = job_profile.get("experience_years", 0)
    req_bac = job_profile.get("education_level", "Bac+0")
    req_sector = job_profile.get("sector", "")
    
    cand_exp = candidate_data.get("annees_experience_totales") or 0
    cand_bac = candidate_data.get("education_niveau", "")
    cand_skills = candidate_data.get("competences_techniques", [])
    cand_langs = candidate_data.get("langues_parlees", [])
    cand_sectors = candidate_data.get("secteurs_activite", [])
    cand_num_exp = candidate_data.get("nombre_experiences_precedentes") or 0
    
    # We define French default req langs if we want or just skip
    req_langs = ["Franglais", "Anglais"] # Simplified example
    
    scores = {
        "annees_experience": score_experience(cand_exp, req_exp),
        "niveau_etude": score_education(cand_bac, req_bac),
        "competences_techniques": score_skills(cand_skills, req_skills),
        "langues_parlees": score_languages(cand_langs, req_langs),
        "secteur_activite": score_sector(cand_sectors, req_sector),
        "nombre_experiences": score_num_experiences(cand_num_exp)
    }
    
    final_score = sum(scores[k] * WEIGHTS[k] for k in scores.keys())
    
    return {
        "dimensions": scores,
        "final_score": final_score
    }
