# Guide de Démarrage Rapide 🚀

Ce document vous explique comment lancer le projet **CV Screening AI Agent** sur votre machine.

## 1. Résolution des Conflits
J'ai détecté que des dossiers nommés `flask` et `flask_login` dans le répertoire `web/` créaient des conflits d'importation. 
**Action effectuée** : J'ai renommé ces dossiers en `custom_flask_logic` et `custom_flask_login_logic`. Le projet peut désormais importer la vraie bibliothèque Flask.

---

## 2. Installation des Dépendances (Indispensable)

Si vous obtenez une erreur "Externally Managed Environment" ou "ModuleNotFoundError", suivez ces étapes :

### Option A : Utiliser un Environnement Virtuel (Recommandé)
Cela évite de polluer votre système :
```bash
# 1. Créez l'environnement (si python3-venv est installé sur votre système)
python3 -m venv venv

# 2. Activez-le
source venv/bin/activate

# 3. Installez les dépendances
pip install -r requirements.txt
```

### Option B : Installation Directe (Si l'Option A échoue)
Si vous ne pouvez pas créer de venv et que vous êtes sur une machine de test :
```bash
pip install --break-system-packages -r requirements.txt
```

---

## 3. Configuration de l'API
Pour utiliser l'IA Claude d'Anthropic, créez un fichier `.env` à la racine :
```text
ANTHROPIC_API_KEY=votre_cle_api_ici
```
*Sans clé, le projet fonctionnera en **Mode Mock** (simulé).*

---

## 4. Lancer l'Interface Web
Une fois les dépendances installées :
```bash
# Si vous utilisez un venv :
./venv/bin/python web/app.py

# Sinon :
python3 web/app.py
```
Accédez à : **http://127.0.0.1:5000**
> **Admin** : `admin` / **Password** : `admin`

---

## 5. Dépannage
Si vous avez toujours des erreurs d'importation, vérifiez qu'aucun fichier ou dossier nommé `flask.py` ou `flask/` ne se trouve dans votre répertoire de travail actuel.
