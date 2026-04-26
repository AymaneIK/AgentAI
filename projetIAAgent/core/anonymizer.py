import re

def anonymize_text(text: str) -> str:
    """
    Redacts emails, phone numbers, and basic PII.
    """
    # Redact email
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    text = re.sub(email_pattern, '[EMAIL MASQUÉ]', text)
    
    # Redact French phone numbers (e.g. 06 12 34 56 78, +33 6 12...)
    phone_pattern = r'(?:(?:\+|00)33|0)\s*[1-9](?:[\s.-]*\d{2}){4}'
    text = re.sub(phone_pattern, '[TÉLÉPHONE MASQUÉ]', text)

    # Basic LinkedIn URLs
    linkedin_pattern = r'linkedin\.com/in/[a-zA-Z0-9_-]+'
    text = re.sub(linkedin_pattern, '[LINKEDIN MASQUÉ]', text)
    
    return text
