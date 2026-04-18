import json
import re
import unicodedata
from difflib import SequenceMatcher

WEIGHTS = {
    "annees_experience": 0.20,
    "niveau_etude": 0.15,
    "competences_techniques": 0.30,
    "langues_parlees": 0.10,
    "secteur_activite": 0.15,
    "nombre_experiences": 0.10,
}

EDUCATION_KEYWORDS = {
    8: ["doctorat", "phd"],
    5: ["master", "mba", "ingenieur", "ingénieur", "grande ecole", "grande école", "bac+5"],
    4: ["bac+4"],
    3: ["licence", "license", "bachelor", "bac+3"],
    2: ["bts", "dut", "deug", "bac+2"],
    1: ["bac", "baccalaureat", "baccalauréat", "bac+1"],
}

LANGUAGE_ALIASES = {
    "francais": {"francais", "français", "french"},
    "anglais": {"anglais", "english", "anglophone"},
    "espagnol": {"espagnol", "spanish", "castillan"},
    "arabe": {"arabe", "arabic"},
}

SKILL_ALIASES = {
    "recrutement": {"recrutement", "recruitment", "talent acquisition", "talent-acquisition"},
    "sourcing": {"sourcing", "candidate sourcing", "talent sourcing"},
    "tri des candidatures": {"tri des candidatures", "cv screening", "screening cv", "preselection", "présélection"},
    "preselection": {"preselection", "présélection", "shortlisting", "pre qualification"},
    "conduite d'entretiens": {"conduite d'entretiens", "entretiens", "interviewing", "interviews"},
    "redaction d'offres d'emploi": {"redaction d'offres d'emploi", "rédaction d'offres d'emploi", "job posting", "offres d'emploi"},
    "evaluation des candidats": {"evaluation des candidats", "évaluation des candidats", "assessment", "candidate evaluation"},
    "communication professionnelle": {"communication professionnelle", "communication", "relationnel"},
    "organisation": {"organisation", "coordination", "planning"},
    "outils de recrutement digitaux": {"outils de recrutement digitaux", "ats", "recruitment tools", "job boards"},
    "linkedin": {"linkedin", "linkedin recruiter"},
    "indeed": {"indeed"},
    "confidentialite": {"confidentialite", "confidentialité", "discretion", "discrétion"},
}


def normalize_text(value) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.lower()
    value = re.sub(r"[^a-z0-9+\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def coerce_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        return [item.strip() for item in re.split(r"[,;/\n]", stripped) if item.strip()]
    return [str(value).strip()]


def safe_json_loads(value, default):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value if value is not None else default


def parse_bac_level(bac_str: str) -> int:
    if not bac_str or not isinstance(bac_str, str):
        return 0

    match = re.search(r"bac\s*\+\s*(\d+)", bac_str, re.IGNORECASE)
    if match:
        return int(match.group(1))

    normalized = normalize_text(bac_str)
    for level, keywords in EDUCATION_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return level
    return 0


def score_experience(cand_exp: int, req_exp: int) -> float:
    cand_exp = max(0, int(cand_exp or 0))
    req_exp = max(0, int(req_exp or 0))
    if req_exp == 0:
        return min(100.0, 55.0 + (cand_exp * 5))
    if cand_exp >= req_exp:
        return 100.0
    if cand_exp == 0:
        return 50.0 if req_exp <= 1 else 45.0
    return max(0.0, min(100.0, (cand_exp / req_exp) * 100.0))


def score_education(cand_bac: str, req_bac: str) -> float:
    cand_level = parse_bac_level(cand_bac)
    req_level = parse_bac_level(req_bac)

    if req_level == 0:
        return 100.0
    if cand_level == 0:
        return 60.0
    if cand_level >= req_level:
        return 100.0
    if cand_level == req_level - 1:
        return 80.0
    if cand_level == req_level - 2:
        return 55.0
    return 40.0


def fuzzy_match(s1: str, s2: str) -> float:
    left = normalize_text(s1)
    right = normalize_text(s2)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if left in right or right in left:
        return 0.92
    ratio = SequenceMatcher(None, left, right).ratio()
    return ratio if ratio > 0.58 else 0.0


def expand_skill_aliases(skill: str) -> set[str]:
    normalized = normalize_text(skill)
    aliases = {normalized}
    for canonical, related in SKILL_ALIASES.items():
        normalized_group = {normalize_text(item) for item in related | {canonical}}
        if normalized in normalized_group:
            aliases |= normalized_group
    return aliases


def score_skill_match(required_skill: str, candidate_skills: list[str]) -> float:
    required_aliases = expand_skill_aliases(required_skill)
    candidate_norm = [normalize_text(skill) for skill in candidate_skills if normalize_text(skill)]

    if not candidate_norm:
        return 0.0

    best_score = 0.0
    required_tokens = set(normalize_text(required_skill).split())

    for candidate_skill in candidate_norm:
        candidate_aliases = expand_skill_aliases(candidate_skill)
        if required_aliases & candidate_aliases:
            best_score = max(best_score, 1.0)
            continue

        ratio = max(fuzzy_match(alias, candidate_skill) for alias in required_aliases)
        candidate_tokens = set(candidate_skill.split())
        token_overlap = 0.0
        if required_tokens and candidate_tokens:
            token_overlap = len(required_tokens & candidate_tokens) / len(required_tokens)
        best_score = max(best_score, ratio, token_overlap)

    return best_score


def score_skills(cand_skills: list, req_skills: list) -> float:
    req_skills = coerce_list(req_skills)
    cand_skills = coerce_list(cand_skills)
    if not req_skills:
        return 100.0 if cand_skills else 50.0
    if not cand_skills:
        return 40.0

    matches_score = 0.0
    for req in req_skills:
        best_match = score_skill_match(req, cand_skills)
        matches_score += best_match

    coverage_score = (matches_score / len(req_skills)) * 100.0
    bonus = min(10.0, max(0, len(cand_skills) - 2) * 2.0)
    return min(100.0, coverage_score + bonus)


def normalize_language(lang: str) -> str:
    normalized = normalize_text(lang)
    for canonical, aliases in LANGUAGE_ALIASES.items():
        if normalized in {normalize_text(item) for item in aliases} | {canonical}:
            return canonical
    return normalized


def score_languages(cand_langs: list, req_langs: list) -> float:
    req_langs = [normalize_language(lang) for lang in coerce_list(req_langs)]
    cand_langs = [normalize_language(lang) for lang in coerce_list(cand_langs)]
    if not req_langs:
        return 100.0 if cand_langs else 50.0
    if not cand_langs:
        return 45.0

    matches = 0.0
    for req in req_langs:
        best_match = max([fuzzy_match(req, cand) for cand in cand_langs] + [0.0])
        matches += best_match
    return min(100.0, (matches / len(req_langs)) * 100.0)


def score_sector(cand_sectors: list, req_sector: str) -> float:
    req_sector = normalize_text(req_sector)
    cand_sectors = [normalize_text(item) for item in coerce_list(cand_sectors)]
    if not req_sector:
        return 100.0
    if not cand_sectors:
        return 55.0
    best_match = max([fuzzy_match(req_sector, sector) for sector in cand_sectors] + [0.0])
    return min(100.0, max(best_match, 0.4) * 100.0 if best_match > 0 else 50.0)


def score_num_experiences(num_exp: int) -> float:
    curve = {0: 50.0, 1: 65.0, 2: 80.0, 3: 90.0, 4: 100.0, 5: 100.0}
    return curve.get(int(num_exp or 0), 100.0)


def calculate_all_scores(candidate_data: dict, job_profile: dict) -> dict:
    req_skills = safe_json_loads(job_profile.get("required_skills", "[]"), [])
    req_langs = safe_json_loads(job_profile.get("required_languages", "[]"), [])
    req_exp = job_profile.get("experience_years", 0)
    req_bac = job_profile.get("education_level", "Bac+0")
    req_sector = job_profile.get("sector", "")

    cand_exp = candidate_data.get("annees_experience_totales") or 0
    cand_bac = candidate_data.get("education_niveau", "")
    cand_skills = coerce_list(candidate_data.get("competences_techniques", []))
    cand_langs = coerce_list(candidate_data.get("langues_parlees", []))
    cand_sectors = coerce_list(candidate_data.get("secteurs_activite", []))
    cand_num_exp = candidate_data.get("nombre_experiences_precedentes") or 0

    if not req_langs:
        req_langs = ["Francais", "Anglais"]

    scores = {
        "annees_experience": score_experience(cand_exp, req_exp),
        "niveau_etude": score_education(cand_bac, req_bac),
        "competences_techniques": score_skills(cand_skills, req_skills),
        "langues_parlees": score_languages(cand_langs, req_langs),
        "secteur_activite": score_sector(cand_sectors, req_sector),
        "nombre_experiences": score_num_experiences(cand_num_exp),
    }

    # Always fit - let the score decide
    is_fit = True
    rejection_reason = None

    final_score = sum(scores[key] * WEIGHTS[key] for key in scores.keys())

    return {
        "dimensions": scores,
        "final_score": round(final_score, 2),
        "is_fit": is_fit,
        "rejection_reason": rejection_reason,
    }
