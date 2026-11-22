#!/usr/bin/env bash
# Installation de Brother OCR sous Linux :
#   - environnement virtuel Python (.venv) et dépendances
#   - fichier de configuration ~/.config/brother-ocr/env
#   - service systemd utilisateur brother-ocr.service
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/brother-ocr"
CONFIG_FILE="$CONFIG_DIR/env"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIT_FILE="$UNIT_DIR/brother-ocr.service"

case "$REPO_DIR" in
  *[[:space:]]*) echo "Erreur : le chemin du dépôt ne doit pas contenir d'espace ($REPO_DIR)." >&2; exit 1 ;;
esac

command -v python3 >/dev/null || { echo "Erreur : python3 introuvable." >&2; exit 1; }
python3 -c 'import venv, ensurepip' 2>/dev/null || {
  echo "Erreur : module venv indisponible. Installez-le : sudo apt install python3-venv" >&2; exit 1; }
command -v zenity >/dev/null || echo "Avertissement : zenity absent (sudo apt install zenity), repli sur tkinter."
command -v xdg-open >/dev/null || echo "Avertissement : xdg-open absent (sudo apt install xdg-utils)."

echo "==> Environnement virtuel : $REPO_DIR/.venv"
[ -x "$REPO_DIR/.venv/bin/python" ] || python3 -m venv "$REPO_DIR/.venv"
"$REPO_DIR/.venv/bin/python" -m pip install --quiet --upgrade pip
"$REPO_DIR/.venv/bin/python" -m pip install --quiet -r "$REPO_DIR/requirements.txt"

echo "==> Configuration : $CONFIG_FILE"
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_FILE" ]; then
  install -m 600 "$REPO_DIR/.env.example" "$CONFIG_FILE"
  echo "    Fichier créé : renseignez votre clé API dedans."
else
  chmod 600 "$CONFIG_FILE"
  echo "    Fichier existant conservé."
fi

echo "==> Service systemd utilisateur : $UNIT_FILE"
mkdir -p "$UNIT_DIR"
sed "s|@REPO_DIR@|$REPO_DIR|g" "$REPO_DIR/linux/brother-ocr.service" > "$UNIT_FILE"
systemctl --user daemon-reload
systemctl --user enable brother-ocr.service

if grep -Eq '^[[:space:]]*(OCR_API_KEY|OPENCODE_API_KEY|DEEPSEEK_API_KEY)=[^[:space:]]' "$CONFIG_FILE"; then
  systemctl --user restart brother-ocr.service
  echo "==> Service démarré. Logs : journalctl --user -u brother-ocr -f"
else
  echo
  echo "Aucune clé API trouvée dans $CONFIG_FILE."
  echo "Ajoutez-la, puis lancez : systemctl --user restart brother-ocr"
fi
