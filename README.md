# Brother OCR

Ce dépôt contient un petit pipeline OCR pour un scanner Brother, conçu pour surveiller un dossier d'entrée, détecter les nouveaux PDF, puis extraire le texte de chaque page via un modèle de vision LLM et enregistrer le résultat au format Markdown.

Le script est conçu pour fonctionner sur Windows, avec des chemins locaux typiques comme `C:\Brother\In` et `C:\Brother\Out`, ainsi qu'avec un fichier `.vbs` pour démarrer l'application au lancement du système.

## Objectif

Le but est de transformer automatiquement les scans PDF déposés dans un dossier d'attente en documents texte lisibles et exploitable, en gardant une sortie structurée en Markdown.

Le flux principal est le suivant :

1. Surveillance d'un dossier d'entrée.
2. Détection d'un nouveau fichier PDF.
3. Ouverture du document avec PyMuPDF.
4. Conversion de chaque page en image.
5. Envoi de l'image à une API de vision LLM.
6. Récupération du texte OCR.
7. Assemblage du résultat en un fichier Markdown.
8. Ouverture du document généré.

## Contenu du dépôt

- `numer.py` : script principal de surveillance et d'OCR.
- `numerisation.py` : version quasi identique, utilisée pour un autre point d'entrée / fournisseur d'API.
- `numerisation.vbs` : lanceur Windows qui démarre le script Python en arrière-plan.
- `.github/copilot-instructions.md` : instruction projet pour les agents et assistants de développement.

## Dépendances

Le projet utilise les bibliothèques Python suivantes :

- `pymupdf`
- `requests`
- `watchdog`
- `tkinter` (fourni avec Python standard sur Windows)

Installation typique :

```powershell
pip install pymupdf requests watchdog
```

## Configuration

Les paramètres principaux sont définis en haut des scripts :

```python
WATCH_DIR = r"C:\Brother\In"
OUTPUT_DIR = r"C:\Brother\Out"
```

Et la configuration de l'API (respectivement sur les différentes variantes) :

```python
OPENCODE_ENDPOINT = "https://opencode.ai/zen/v1/chat/completions"
OPENCODE_API_KEY = "..."
MODEL_NAME = "deepseek-v4.1-flash"
```

ou

```python
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEEPSEEK_API_KEY = "..."
MODEL_NAME = "deepseek-v4-flash-vision-exp"
```

Important : la clé API ne doit pas être commitée en clair dans un dépôt partagé. Dans un usage réel, il vaut mieux la stocker dans une variable d’environnement ou dans un fichier de configuration local non versionné.

## Fonctionnement

### Démarrage

Sur Windows, on peut lancer le script directement :

```powershell
python numerisation.py
```

Ou le démarrer automatiquement via le batch/launcher VBS :

```powershell
wscript numerisation.vbs
```

### Comportement

- Le script surveille le dossier `C:\Brother\In`.
- Lorsqu'un fichier `.pdf` est détecté, il attend quelques secondes pour laisser la copie se terminer.
- Une boîte de dialogue Tkinter demande confirmation avant de lancer l'OCR.
- Chaque page du PDF est convertie en image PNG et envoyée à l'API LLM de vision.
- Le texte extrait est regroupé en Markdown et sauvegardé dans `C:\Brother\Out`.
- Le fichier généré est ensuite ouvert par le système.

## Limites et points importants

- Ce projet est fortement orienté Windows et dépend de chemins fixes.
- Il n'inclut pas de tests automatisés ni de framework de validation.
- La fiabilité de l'OCR dépend directement du modèle visuel choisi et de la qualité du scan.
- Le script est pensé comme un outil d'automatisation locale, pas comme un service web multi-utilisateurs.

## Exemple de structure de sortie

Un fichier généré ressemble à ceci :

```md
# Titre de page

Texte extrait récupéré par le modèle...

---

Autre page de document
```

## Sécurité et bonnes pratiques

- Ne pas versionner les clés API.
- Vérifier les permissions d'accès aux dossiers d'entrée/sortie.
- Préférer un environnement Windows dédié au poste scanner.
- Conserver les scripts en arrière-plan avec supervision, car le système dépend d'une API externe et d'un dossier partagé.

## À noter

Le dépôt contient deux variantes de script avec des configurations API différentes. Elles ont le même objectif, mais doivent être maintenues cohérentes si l'on change la logique d'OCR ou le service backend.
