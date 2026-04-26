# Rapport Technique Détaillé : Système d'Agent IA pour le Screening de CV

---

> [!NOTE]
> **Statut du Projet** : Version 1.2 (Production Ready)
> **Auteur** : Équipe Technique
> **Technologies** : Python, FastAPI, Flask, Anthropic Claude 3.5

---

## Sommaire
1. [Introduction](#1-introduction-et-contexte-du-projet)
2. [Architecture Globale](#2-architecture-globale-du-système)
3. [Moteur d'Analyse (Module core)](#3-le-cœur-du-moteur--analyse-et-extraction-module-core)
4. [Algorithme de Scoring](#4-algorithme-de-scoring-avancé-corescorerpy)
5. [Persistance des Données](#5-modélisation-et-persistance-des-données-db)
6. [Interface Utilisateur](#6-linterface-utilisateur-web-app---flask)
7. [Interface API RESTful](#7-linterface-api-restful-fastapi)
8. [Reporting et Exportation](#8-reporting-et-exportation-coreexcel_exportpy)
9. [Script de Démonstration](#9-le-script-de-démonstration-cli-agentpy)
10. [Conclusion et Sécurité](#10-conclusion-sécurité-et-perspectives-dévolution)




---

## 1. Introduction et Contexte du Projet

Le recrutement moderne fait face à un défi majeur : le volume massif de candidatures à traiter pour chaque offre d'emploi. L'analyse manuelle des Curriculum Vitae (CV) est une tâche chronophage, sujette aux biais cognitifs et souvent inefficace. C'est dans ce contexte que s'inscrit le projet **"CV Screening AI Agent"**.

Ce projet consiste en une solution complète et automatisée permettant l'ingestion, l'anonymisation, l'analyse sémantique, et le scoring de CV à l'aide de l'Intelligence Artificielle (en l'occurrence, le modèle Claude 3.5 Sonnet d'Anthropic). L'objectif est de fournir aux recruteurs un outil d'aide à la décision puissant, capable de classer les candidats selon des critères objectifs définis par le profil du poste, tout en générant des recommandations justifiées.

### 1.1. Objectifs Principaux
- **Automatisation du tri** : Réduire le temps passé à lire des CV non pertinents.
- **Objectivité** : Appliquer un barème strict et identique à tous les candidats (années d'expérience, niveau d'étude, compétences).
- **Anonymisation** : Lutter contre les discriminations à l'embauche en masquant les informations personnelles (Nom, Email, Téléphone).
- **Explicabilité** : Fournir une justification claire pour chaque note attribuée.

### 1.2. Technologies Utilisées
Le projet repose sur une stack Python moderne et robuste :

| Composant | Technologie | Rôle |
| :--- | :--- | :--- |
| **Backend / API** | FastAPI | Webhooks et traitements asynchrones |
| **Interface Web** | Flask | Dashboard et interface recruteur |
| **Base de Données** | SQLite / SQLAlchemy | Persistance et ORM |
| **Intelligence Artificielle** | Anthropic Claude 3.5 | Analyse sémantique et extraction |
| **Traitement Docs** | pdfplumber / docx | Extraction de texte brut |
| **Exportation** | openpyxl | Génération de rapports Excel stylisés |




---

## 2. Architecture Globale du Système

Le système est divisé en plusieurs modules interdépendants, garantissant une séparation claire des responsabilités (Separation of Concerns). 

L'architecture s'articule autour des dossiers suivants :
- **`core/`** : Contient le cœur logique de l'application (parsing, scoring, requêtes IA, exports).
- **`db/`** : Gère la persistance des données, les modèles SQLAlchemy et les opérations CRUD (Create, Read, Update, Delete).
- **`api/`** : Expose une interface RESTful via FastAPI pour une utilisation programmatique du système.
- **`web/`** : Contient l'application Flask qui sert d'interface graphique pour les utilisateurs finaux (recruteurs).
- **`agent.py`** : Point d'entrée pour un mode démonstration en ligne de commande (CLI) utilisant la bibliothèque `rich` pour un affichage interactif.

### 2.1. Flux de traitement (Pipeline)

> [!TIP]
> Le pipeline est conçu pour être **résilient** : chaque étape dispose d'un mécanisme de "fallback" (secours) en cas d'erreur de parsing ou d'indisponibilité de l'API.

1. **Upload** : L'utilisateur télécharge un lot de CV (PDF, DOCX) via l'interface web ou l'API.
2. **Parsing** : Le texte brut est extrait des documents.
3. **Anonymisation (Optionnelle)** : Les données personnelles sont remplacées par des balises via RegEx.
4. **Extraction IA** : Claude analyse le texte brut et le convertit en un objet JSON structuré.
5. **Scoring** : L'algorithme interne calcule des scores dimensionnels pondérés.
6. **Recommandation** : L'IA génère une note de synthèse justificative.
7. **Restitution** : Résultats affichés sur le dashboard et exportables.




---

## 3. Le Cœur du Moteur : Analyse et Extraction (Module `core`)

### 3.1. Extraction de texte (`core/parser.py`)
Le système doit être capable de lire divers formats de fichiers. Le module `parser.py` implémente cette flexibilité.
- **PDF** : Utilisation de `pdfplumber` pour une extraction précise du texte. En cas d'échec (ex: PDF scanné), le système déploie automatiquement une solution de secours avec `pytesseract` pour la reconnaissance optique de caractères (OCR). Une méthode `parse_pdf_fallback` utilisant `PyPDF2` est également prévue pour garantir qu'aucun document n'est rejeté.
- **DOCX** : Utilisation de la bibliothèque `python-docx` pour itérer sur les paragraphes du document.
- **TXT** : Lecture native en UTF-8.

```python
def parse_pdf(file_path: str) -> str:
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                else:
                    # Fallback to OCR if image-based
                    im = page.to_image()
                    text += pytesseract.image_to_string(im.original) + "\n"
    except Exception as e:
        text = parse_pdf_fallback(file_path)
    return text.strip()
```

### 3.2. Intégration Anthropic (`core/anthropic_client.py`)
Ce module est essentiel car il fait le lien entre l'application et le Modèle de Langage (LLM). Il utilise `AsyncAnthropic` pour des appels non bloquants, ce qui est crucial lors du traitement de dizaines de CV simultanément.

**Gestion du nom du candidat :**
Une logique très poussée est implémentée pour retrouver le nom du candidat même si l'IA échoue. Des fonctions comme `_looks_like_person_name` et `extract_candidate_name_from_text` filtrent le texte brut en évitant les en-têtes classiques (ex: "Expérience", "Formation") et les mots de liaison pour isoler le nom complet.

**Mode Mock (Démo) :**
Si aucune clé API valide n'est fournie, le système bascule intelligemment en `is_mock_mode = True`. Dans ce mode, il simule une réponse de l'IA avec des données aléatoires (générées via un seed basé sur la longueur du texte), permettant de tester l'interface sans consommer de crédits API.

**Anonymisation avancée (`core/anonymizer.py`) :**
Pour garantir la protection des données (RGPD), le système utilise des expressions régulières complexes pour masquer les informations sensibles avant l'envoi au LLM.

```python
def anonymize_text(text: str) -> str:
    # Masquage des emails
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    text = re.sub(email_pattern, '[EMAIL MASQUÉ]', text)
    
    # Masquage des numéros de téléphone (format FR)
    phone_pattern = r'(?:(?:\+|00)33|0)\s*[1-9](?:[\s.-]*\d{2}){4}'
    text = re.sub(phone_pattern, '[TÉLÉPHONE MASQUÉ]', text)
    
    return text
```

**Prompts :**
Les instructions envoyées à l'IA sont cruciales. Le système utilise des prompts définis (comme `CV_EXTRACTION_PROMPT`) pour forcer Claude à répondre strictement au format JSON, extrayant des champs tels que `nom_candidat`, `annees_experience_totales`, et `competences_techniques`.

```json
{
    "nom_candidat": "Prénom Nom",
    "education_niveau": "Bac+5",
    "annees_experience_totales": 5,
    "competences_techniques": ["Python", "SQL", "Docker"],
    "langues_parlees": ["Français", "Anglais"],
    "secteurs_activite": ["Finance", "SaaS"],
    "nombre_experiences_precedentes": 3
}
```




---

## 4. Algorithme de Scoring Avancé (`core/scorer.py`)

Une fois les données structurées par l'IA, le fichier `scorer.py` prend le relais. Il ne s'agit pas d'une simple vérification par mots-clés, mais d'un algorithme déterministe complexe qui attribue une note sur 100 au candidat.

### 4.1. Pondérations (Weights)
Le système accorde une importance différente à chaque dimension du profil :
- Compétences techniques : 30%
- Années d'expérience : 20%
- Niveau d'étude : 15%
- Secteur d'activité : 15%
- Langues parlées : 10%
- Stabilité (Nombre d'expériences) : 10%

```python
WEIGHTS = {
    "annees_experience": 0.20,
    "niveau_etude": 0.15,
    "competences_techniques": 0.30,
    "langues_parlees": 0.10,
    "secteur_activite": 0.15,
    "nombre_experiences": 0.10,
}
```

### 4.2. Normalisation et Fuzzy Matching
Pour éviter qu'un candidat soit pénalisé pour une faute de frappe, le code utilise une normalisation Unicode (`NFKD`) et un algorithme de similarité de chaîne.

```python
def fuzzy_match(s1: str, s2: str) -> float:
    left = normalize_text(s1)
    right = normalize_text(s2)
    if left == right: return 1.0
    if left in right or right in left: return 0.92
    
    # Utilisation de SequenceMatcher pour la tolérance aux fautes
    ratio = SequenceMatcher(None, left, right).ratio()
    return ratio if ratio > 0.58 else 0.0
```

### 4.3. Évaluation des Compétences (Skill Matching)
C'est le composant le plus sophistiqué. Il utilise un dictionnaire de synonymes (`SKILL_ALIASES`). Par exemple, si le recruteur demande la compétence "Tri des candidatures", le système validera également "cv screening", "preselection", ou "shortlisting".
La fonction `score_skills` calcule un pourcentage de couverture des compétences requises et attribue même un bonus (jusqu'à 10 points) si le candidat possède des compétences supplémentaires.

### 4.4. Calcul de l'expérience et des études
- **Expérience** : Une règle mathématique proportionnelle est appliquée. Si le candidat a 2 ans d'expérience et que 4 sont requis, il obtient 50/100.
- **Études** : Les diplômes sont traduits en niveaux numériques (Doctorat = 8, Master = 5, BTS = 2). La note décroît progressivement si le niveau du candidat est inférieur au niveau requis (-20 points par niveau d'écart).




---

## 5. Modélisation et Persistance des Données (`db/`)

Le projet utilise SQLAlchemy, un ORM (Object-Relational Mapping) Python robuste, pour interagir avec une base de données SQLite.

### 5.1. Schéma de la Base de Données (`db/models.py`)
Cinq entités principales régissent la logique de données :
1. **User** : Gère l'authentification des recruteurs (nom d'utilisateur, hash du mot de passe avec `bcrypt`).
2. **JobProfile** : Définit l'offre d'emploi (Titre, description, JSON des compétences requises, niveau d'étude, secteur).
3. **ScreeningSession** : Représente une campagne d'analyse (un lot de CV scannés à un instant T pour un profil de poste).
4. **Candidate** : Stocke toutes les informations d'un postulant. Les données brutes, les informations de contact (ou leur version anonymisée), ainsi que la note finale (`final_score`) et la recommandation textuelle de l'IA.
5. **DimensionScore** : Table relationnelle stockant le détail de la note d'un candidat pour chaque critère.

```python
class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(Integer, primary_key=True)
    name = Column(String, default="Anonyme")
    final_score = Column(Float, nullable=True)
    recommendation = Column(Text, nullable=True) # Claude's hiring note
    is_fit = Column(Boolean, default=True)
```

### 5.2. Opérations CRUD (`db/crud.py`)
Ce fichier abstrait la complexité des requêtes SQL. On y trouve des fonctions essentielles comme :
- `create_candidate()` : Insère un candidat et gère la relation avec la session de screening.
- `update_candidate_final_score()` : Met à jour la fiche du candidat une fois l'analyse asynchrone terminée.
- `upsert_singleton_job()` : Garantit l'existence d'au moins un profil de poste par défaut pour la démo.




---

## 6. L'Interface Utilisateur (Web App - Flask)

L'application web, hébergée dans `web/app.py`, est l'interface principale pour le recruteur. Elle utilise le framework Flask et le moteur de templates Jinja2.

### 6.1. Sécurité et Authentification
Les routes sont protégées par le décorateur `@login_required` fourni par `flask_login`. Les mots de passe sont hachés de manière sécurisée via `bcrypt`. Au démarrage, le script s'assure qu'un utilisateur administrateur ("admin" / "admin") existe par défaut.

### 6.2. Traitement Asynchrone des Fichiers
Lorsqu'un recruteur téléverse 15 CV, le traitement séquentiel serait trop lent. L'application Flask contourne ce problème en utilisant `asyncio`.
La fonction `batch_dispatcher` crée une série de tâches asynchrones (coroutines) via `asyncio.gather()`. Chaque CV est ainsi traité en parallèle (parsing + appel API Anthropic + calcul du score). C'est une excellente optimisation de performance.

```python
async def batch_dispatcher(job_id, session_id, saved_files, is_anonymized, job_profile_dict):
    tasks = [
        process_single_cv(job_id, session_id, path, is_anonymized, job_profile_dict)
        for path in saved_files
    ]
    await asyncio.gather(*tasks)
```

### 6.3. Pages et Fonctionnalités
- **Dashboard (`/`)** : Affiche les sessions de recrutement passées, les paramètres du poste, et permet l'upload de nouveaux CV via un formulaire gérant les fichiers multiples.
- **Analytics (`/analytics`)** : Une vue analytique puissante. Le code agrège les données pour calculer les compétences les plus fréquemment manquantes chez les candidats (`missing_skills_tally`), les moyennes des scores par dimension, et prépare des données formatées pour l'affichage de graphiques radar.
- **Comparateur (`/compare`)** : Permet de sélectionner plusieurs candidats et de les comparer côte à côte.




---

## 7. L'Interface API RESTful (FastAPI)

En parallèle de l'interface graphique, le projet offre une API complète dans `api/main.py`. Cette approche duale est excellente pour une architecture orientée microservices ou pour permettre l'intégration du moteur de scoring dans des outils ATS existants (Applicant Tracking Systems comme Workday ou Taleo).

### 7.1. Gestion Asynchrone Optimale (Background Tasks)
Contrairement à Flask, FastAPI est nativement asynchrone. L'endpoint `/jobs/{job_id}/screen` utilise les `BackgroundTasks` pour ne pas faire attendre l'utilisateur pendant l'analyse IA.

```python
@app.post("/jobs/{job_id}/screen")
async def screen_cvs(job_id: int, background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    # ... initialisation ...
    for file in files:
        # On délègue le traitement lourd à une tâche de fond
        background_tasks.add_task(process_candidate_data, db, session_id, job, raw_text)
        
    return {"message": "Screening session started", "session_id": session_id}
```




---

## 8. Reporting et Exportation (`core/excel_export.py`)

Les recruteurs travaillent souvent sur Excel. Le module `excel_export.py` utilise `openpyxl` pour générer des rapports de haute qualité.
- **Onglet "Résumé"** : Un classement général des candidats avec une coloration syntaxique conditionnelle (Vert pour >80, Rouge pour <50, Jaune entre les deux).
- **Onglets Détaillés** : Chaque candidat possède un onglet dédié résumant ses informations de contact, la note de l'IA, et un tableau listant ses scores dimensionnels.
- **Graphiques Intégrés** : Un graphique en barres (`BarChart`) est automatiquement généré dans l'onglet "Graphiques", illustrant visuellement la distribution des scores des candidats.




---

## 9. Le Script de Démonstration CLI (`agent.py`)

Pour les développeurs ou les présentations techniques, un mode console est disponible. Il utilise la librairie `rich` pour offrir une expérience utilisateur agréable en ligne de commande (Tableaux stylisés, barres de statut, couleurs).
En lançant `python agent.py --demo`, le script simule le cycle de vie complet du produit (Initialisation, Création du Job, Parsing, Scoring via IA) et affiche un tableau récapitulatif directement dans le terminal.




---

## 10. Conclusion, Sécurité et Perspectives d'Évolution

### 10.1. Sécurité
Le système gère la sécurité à plusieurs niveaux :
- Stockage des fichiers temporaires via `secrets.token_hex(4)` pour éviter les collisions et les accès prédictifs.
- Hachage cryptographique des mots de passe.
- Nettoyage des chaînes de caractères avant exécution.

### 10.2. Perspectives d'Amélioration
Bien que l'architecture soit robuste, plusieurs améliorations pourraient être apportées :
1. **Stockage Cloud** : Actuellement, les CV sont sauvegardés localement dans `temp_cvs`. Une migration vers AWS S3 ou Google Cloud Storage serait recommandée pour la mise en production.
2. **File d'attente robuste** : Remplacer les tâches asynchrones en mémoire par un broker de messages externe comme Celery couplé à Redis ou RabbitMQ, pour garantir la résilience en cas de redémarrage du serveur.
3. **Vector Database** : Ajouter une recherche sémantique via une base vectorielle (ex: Pinecone, Milvus) pour retrouver des candidats passés dont le profil correspondrait à une nouvelle offre d'emploi.
4. **Internationalisation (i18n)** : Traduire l'interface Flask et FastAPI pour permettre le déploiement sur plusieurs marchés internationaux.

En conclusion, ce projet de "CV Screening AI Agent" démontre une maîtrise technique approfondie. Il combine intelligemment les frameworks web (Flask, FastAPI), les algorithmes classiques de comparaison de chaînes (Fuzzy Matching), et les technologies LLM de pointe (Claude 3.5) pour résoudre un problème d'entreprise très concret avec un haut niveau de performance et de résilience.
