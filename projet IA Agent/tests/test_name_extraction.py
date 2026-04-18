from core.anthropic_client import (
    extract_candidate_name_from_text,
    sanitize_candidate_name,
)


def test_extract_candidate_name_skips_section_headers():
    cv_text = """
    ABOUT ME
    Experienced recruiter with 5 years of experience.
    Contact
    sara.bennani@example.com
    Sara Bennani
    Casablanca, Morocco
    """

    assert extract_candidate_name_from_text(cv_text) == "Sara Bennani"


def test_extract_candidate_name_accepts_uppercase_name():
    cv_text = """
    AMINE EL HADDAD
    amine@example.com
    +212 600 00 00 00
    """

    assert extract_candidate_name_from_text(cv_text) == "AMINE EL HADDAD"


def test_sanitize_candidate_name_replaces_invalid_model_output():
    cv_text = """
    Profile
    Full-stack engineer
    Leila O'Malley
    leila@example.com
    """

    assert sanitize_candidate_name("About Me", cv_text) == "Leila O'Malley"


def test_sanitize_candidate_name_keeps_valid_name():
    cv_text = "Random CV body"
    assert sanitize_candidate_name("Youssef Ben Ali", cv_text) == "Youssef Ben Ali"
