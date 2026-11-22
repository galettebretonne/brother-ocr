# Brother OCR

Ce dépôt contient un petit pipeline OCR pour un scanner Brother. Il surveille un dossier d'entrée, détecte les nouveaux PDF, extrait le texte de chaque page via un modèle de vision LLM et enregistre le résultat au format Markdown.

Il fonctionne sous **Windows** et sous **Linux** (et, en principe, macOS).

## Objectif

Transformer automatiquement les scans PDF déposés dans un dossier d'attente en documents texte lisibles et exploitables, avec une sortie structurée en Markdown.

Le flux principal est le suivant :

1. Surveillance d'un dossier d'entrée.
2. Détection d'un nouveau fichier PDF, puis attente de la fin de sa copie.
3. Demande de confirmation à l'utilisateur.
4. Ouverture du document avec PyMuPDF et conversion de chaque page en image.
5. Envoi de l'image à une API de vision LLM et récupération du texte OCR.
6. Assemblage du résultat en un fichier Markdown.
7. Ouverture du document généré dans l'éditeur par défaut.

## Contenu du dépôt

- `brother_ocr.py` : script unique de surveillance et d'OCR (toute la logique).
- `numer.py` : lanceur qui force le fournisseur OpenCode Zen.
- `numerisation.py` : lanceur qui force le fournisseur DeepSeek (utilisé par le `.vbs`).
- `numerisation.vbs` : démarrage en arrière-plan sous Windows.
- `linux/brother-ocr.service` : service systemd utilisateur.
- `linux/install.sh` : installation sous Linux (venv, configuration, service).
- `requirements.txt` : dépendances Python.
- `.env.example` : modèle de configuration.
- `.github/copilot-instructions.md` : instructions projet pour les assistants de développement.

## Configuration

Aucune clé n'est écrite dans le code. Tous les réglages se font par variables d'environnement, ou par un fichier de configuration (voir `.env.example`) :

| Variable | Rôle | Défaut |
|---|---|---|
| `OCR_PROVIDER` | `opencode` ou `deepseek` (ignoré par `numer.py` / `numerisation.py`, qui le fixent) | `opencode` |
| `OPENCODE_API_KEY` / `DEEPSEEK_API_KEY` | Clé API du fournisseur | — |
| `OCR_API_KEY` | Clé API prioritaire, quel que soit le fournisseur | — |
| `MODEL_NAME` | Modèle vision | `deepseek-v4.1-flash` (OpenCode), `deepseek-v4-flash-vision-exp` (DeepSeek) |
| `WATCH_DIR` | Dossier surveillé | `C:\Brother\In` / `~/Brother/In` |
| `OUTPUT_DIR` | Dossier de sortie | `C:\Brother\Out` / `~/Brother/Out` |

Le script lit aussi un fichier `.env` placé à côté de `brother_ocr.py`. Les variables d'environnement déjà définies sont prioritaires. Ce fichier est ignoré par Git.

Si aucune clé n'est trouvée, le script affiche une erreur et s'arrête.

## Windows

### Installation

```powershell
pip install -r requirements.txt
copy .env.example .env
notepad .env   # renseigner la clé API
```

### Démarrage

```powershell
python numerisation.py    # DeepSeek
python numer.py           # OpenCode Zen
python brother_ocr.py     # fournisseur choisi par OCR_PROVIDER
```

Pour un démarrage automatique, placez un raccourci vers `numerisation.vbs` dans le dossier de démarrage (`shell:startup`). Le `.vbs` lance `C:\Brother\Script\numerisation.py` avec `pythonw.exe` : **`brother_ocr.py` et `.env` doivent être copiés dans ce même dossier**.

La boîte de confirmation utilise tkinter, fourni avec Python sous Windows.

## Linux

Testé sous Ubuntu (GNOME, Wayland).

### Prérequis

```bash
sudo apt install python3-venv zenity xdg-utils
```

- `zenity` affiche la boîte de confirmation native. S'il est absent, le script se rabat sur tkinter (`python3-tk`).
- `xdg-open` ouvre le Markdown généré dans l'application par défaut.

### Installation en service

```bash
linux/install.sh
```

Ce script :

1. crée un environnement virtuel `.venv` dans le dépôt et installe les dépendances ;
2. crée `~/.config/brother-ocr/env` (droits `600`) à partir de `.env.example`, s'il n'existe pas ;
3. installe et active le service systemd utilisateur `brother-ocr.service`, lancé avec la session graphique ;
4. démarre le service si une clé est déjà renseignée.

Renseignez ensuite la clé, puis redémarrez le service :

```bash
nano ~/.config/brother-ocr/env
systemctl --user restart brother-ocr
```

Le chemin du dépôt ne doit pas contenir d'espace. Si vous déplacez le dépôt, relancez `linux/install.sh`.

### Commandes utiles

```bash
systemctl --user status brother-ocr     # état
journalctl --user -u brother-ocr -f     # logs en direct
systemctl --user stop brother-ocr       # arrêt
systemctl --user disable --now brother-ocr && rm ~/.config/systemd/user/brother-ocr.service   # désinstallation
```

### Lancement manuel (sans service)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env
.venv/bin/python brother_ocr.py
```

### Faire arriver les scans sur Linux

Le script surveille simplement un dossier local (`~/Brother/In` par défaut). Quelques options :

- **Partage Samba** : partager `~/Brother/In` (Nautilus > Propriétés > Partage local, ou `/etc/samba/smb.conf`) et configurer la Brother en « Numérisation vers réseau » (SMB) sur ce partage.
- **Dossier synchronisé** : pointer `WATCH_DIR` vers un dossier alimenté par Syncthing, Nextcloud, etc.
- **Numérisation locale** : enregistrer les PDF produits par `brscan` / Simple Scan dans `~/Brother/In`.

## Comportement

- Le script surveille le dossier d'entrée (création, renommage et fermeture de fichiers `.pdf`).
- Il attend que la taille du fichier ne change plus, ce qui garantit la fin de la copie réseau.
- Les scans sont proposés un par un : une seule boîte de confirmation à la fois, et un même fichier n'est proposé qu'une fois.
- Chaque page est convertie en image PNG (150 dpi) et envoyée à l'API.
- Le texte extrait est regroupé en Markdown (pages séparées par `---`) dans le dossier de sortie, puis ouvert dans l'éditeur par défaut.

## Exemple de structure de sortie

```md
# Titre de page

Texte extrait récupéré par le modèle...

---

Autre page de document
```

## Limites

- Pas de tests automatisés.
- La fiabilité de l'OCR dépend du modèle choisi et de la qualité du scan.
- Outil d'automatisation locale pour un poste avec session graphique, pas un service web multi-utilisateurs.

## Sécurité

- Ne jamais versionner de clé API : utilisez `.env` (ignoré par Git) ou `~/.config/brother-ocr/env`.
- Vérifier les permissions d'accès aux dossiers d'entrée et de sortie, surtout s'ils sont partagés sur le réseau.
