import pytest
from core.scorer import (
    parse_bac_level, 
    score_experience, 
    score_education, 
    fuzzy_match, 
    score_skills, 
    calculate_all_scores
)

def test_parse_bac_level():
    assert parse_bac_level("Bac+5") == 5
    assert parse_bac_level("Master (Bac + 5)") == 5
    assert parse_bac_level("Licence bAC+3") == 3
    assert parse_bac_level("Inconnu") == 0

def test_score_experience():
    assert score_experience(5, 3) == 100.0
    assert score_experience(1, 2) == 50.0
    assert score_experience(0, 5) == 0.0

def test_score_education():
    # cand_level == req_level -> 100
    assert score_education("Bac+5", "Bac+5") == 100.0
    # cand_level > req_level -> 100
    assert score_education("Bac+5", "Bac+3") == 100.0
    # cand_level == req_level - 1 -> 75
    assert score_education("Bac+4", "Bac+5") == 75.0
    # cand_level == req_level - 2 -> 50
    assert score_education("Bac+3", "Bac+5") == 50.0

def test_fuzzy_match():
    assert fuzzy_match("Python", "Python") == 1.0
    assert fuzzy_match("Python", "python") == 1.0
    assert fuzzy_match("ReactJS", "React.js") > 0.8

def test_score_skills():
    req = ["Python", "SQL", "Docker"]
    cand = ["Python", "MySQL", "AWS"]
    score = score_skills(cand, req)
    # Python (100) + SQL (~80) + Docker (0) / 3 => ~60
    assert 40.0 < score < 80.0

def test_calculate_all_scores():
    job = {
        "required_skills": '["Python", "FastAPI"]',
        "experience_years": 3,
        "education_level": "Bac+5",
        "sector": "Tech"
    }
    cand = {
        "annees_experience_totales": 3, # 100 * 0.20 = 20
        "education_niveau": "Bac+5", # 100 * 0.15 = 15
        "competences_techniques": ["Python", "FastAPI"], # 100 * 0.30 = 30
        "langues_parlees": ["Français", "Anglais"], # pseudo 100 * 0.10 = 10
        "secteurs_activite": ["Tech"], # 100 * 0.15 = 15
        "nombre_experiences_precedentes": 3 # 100 * 0.10 = 10
    }
    
    res = calculate_all_scores(cand, job)
    assert res["final_score"] > 90.0
