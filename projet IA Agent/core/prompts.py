CV_EXTRACTION_PROMPT = """
Tu es un expert RH francophone chargé de parser des CVs.
Je vais te fournir le texte d'un CV.
Tu dois en extraire les informations suivantes au format JSON strict :
{{
    "nom_candidat": "Prénom Nom", (ou "Inconnu" si non trouvé)
    "email": "email@example.com", (ou null)
    "telephone": "numero", (ou null)
    "education_niveau": "Bac+5", (Déduis le meilleur niveau atteint selon l'échelle Bac+N : par exemple Master/Ingénieur = Bac+5, Licence = Bac+3, BTS/DUT = Bac+2. Retourne juste la string type 'Bac+N', ou 'Inconnu')
    "annees_experience_totales": 5, (Nombre entier reflétant le total des années d'expérience professionnelles pertinentes)
    "competences_techniques": ["Python", "SQL", "Docker"],
    "langues_parlees": ["Français", "Anglais"],
    "secteurs_activite": ["Finance", "SaaS", "E-commerce"],
    "nombre_experiences_precedentes": 3 (Nombre entier d'entreprises ou postes différents)
}}

Exemple 1 : "Master de Paris Dauphine" -> "education_niveau": "Bac+5"
Exemple 2 : "Bilingue anglais, courant espagnol" -> "langues_parlees": ["Français", "Anglais", "Espagnol"] (ajoute Français par défaut si le CV est en français)

Ne retourne que le JSON valide. Rien d'autre.

Voici le CV :
{cv_text}
"""

RECOMMENDATION_PROMPT = """
Tu es un directeur de recrutement.
Voici le profil du poste :
Titre : {job_title}
Description : {job_description}

Voici les profils des candidats avec leurs scores pour chaque dimension :
{candidates_data}

Rédige une courte recommandation (150 mots max) expliquant lequel de ces candidats est le meilleur choix et pourquoi, en mettant en évidence leurs points forts et les lacunes éventuelles. Sois objectif et professionnel.
"""

SINGLE_CANDIDATE_NOTE_PROMPT = """
Tu es un recruteur expert. Analyse cette candidature pour le poste de "{job_title}".
Compétences requises : {required_skills}

Profil du candidat :
{candidate_data}

Rédige une brève note de synthèse (3-4 phrases) pour le manager du poste, résumant pourquoi on devrait (ou non) engager ce candidat. Mets en avant les *gaps* éventuels.
"""
