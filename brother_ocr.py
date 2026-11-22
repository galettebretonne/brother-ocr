"""Pipeline OCR pour scanner Brother (Windows et Linux).

Surveille un dossier d'entrée, demande confirmation à chaque nouveau PDF,
envoie chaque page à un modèle de vision LLM et écrit le texte en Markdown.

Toute la configuration se fait par variables d'environnement, ou via un
fichier `.env` placé à côté de ce script (voir `.env.example`).
"""
import base64
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pymupdf
import requests
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# ==============================================================================
# CONFIGURATION
# ==============================================================================
IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"

SCRIPT_DIR = Path(__file__).resolve().parent
ENV_FILE = SCRIPT_DIR / ".env"     # Fichier de configuration local facultatif

# Dossiers par défaut (modifiables via WATCH_DIR / OUTPUT_DIR)
if IS_WINDOWS:
    DEFAULT_WATCH_DIR = r"C:\Brother\In"     # Dossier d'entrée (scans de la Brother)
    DEFAULT_OUTPUT_DIR = r"C:\Brother\Out"   # Dossier de sortie (.md)
else:
    DEFAULT_WATCH_DIR = "~/Brother/In"
    DEFAULT_OUTPUT_DIR = "~/Brother/Out"

DEFAULT_PROVIDER = "opencode"      # Fournisseur si OCR_PROVIDER n'est pas défini

# Fournisseurs d'API vision (compatibles OpenAI chat/completions)
PROVIDERS = {
    "opencode": {
        "label": "OpenCode Zen",
        "endpoint": "https://opencode.ai/zen/v1/chat/completions",
        "model": "deepseek-v4.1-flash",          # Modèle Vision ultra-économique
        "key_env": "OPENCODE_API_KEY",
        # En-têtes requis par la passerelle OpenCode Zen / Go
        "extra_headers": {
            "x-opencode-session": "script-ocr",
            "HTTP-Referer": "https://opencode.ai",
            "X-Title": "Brother OCR Pipeline",
        },
    },
    "deepseek": {
        "label": "DeepSeek API",
        "endpoint": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-v4-flash-vision-exp",  # Modèle DeepSeek (supportant la vision)
        "key_env": "DEEPSEEK_API_KEY",
        "extra_headers": {},
    },
}

OCR_PROMPT = (
    "Fais un OCR exact et rigoureux de cette page. Transcris l'intégralité du texte "
    "en respectant fidèlement la structure (titres, paragraphes, tableaux au format "
    "Markdown). Ne rajoute aucun commentaire ni préambule, ne precise pas si il y a "
    "eu une rotation du texte. Réponds uniquement avec le texte transcrit."
)
RENDER_DPI = 150                   # Résolution de rendu des pages
API_TIMEOUT = 90                   # Délai max d'un appel API (s)
STABLE_INTERVAL = 1.0              # Intervalle de contrôle de la taille du fichier (s)
STABLE_TIMEOUT = 120               # Attente max de fin d'écriture d'un scan (s)
ERROR_DIALOG_TIMEOUT = 60          # Fermeture auto de la boîte d'erreur zenity (s)

EXIT_CONFIG_ERROR = 78             # Code de sortie si la configuration est invalide


# ==============================================================================
# CHARGEMENT DE LA CONFIGURATION
# ==============================================================================
def load_env_file(path):
    """Charge un fichier .env simple (CLE=valeur) sans écraser l'environnement."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not os.environ.get(key):
            os.environ[key] = value


def env(name, default=None):
    """Lit une variable d'environnement, une valeur vide valant « non définie »."""
    return os.environ.get(name) or default


def load_config(provider=None):
    """Construit la configuration effective. `provider` prime sur OCR_PROVIDER."""
    load_env_file(ENV_FILE)

    provider = (provider or env("OCR_PROVIDER", DEFAULT_PROVIDER)).lower()
    if provider not in PROVIDERS:
        raise ValueError(
            f"Fournisseur inconnu : '{provider}' (valeurs possibles : {', '.join(PROVIDERS)})"
        )
    spec = PROVIDERS[provider]

    api_key = env("OCR_API_KEY") or env(spec["key_env"])
    if not api_key:
        raise ValueError(
            f"Aucune clé API pour {spec['label']} : définissez OCR_API_KEY ou "
            f"{spec['key_env']} (variable d'environnement ou fichier {ENV_FILE})."
        )

    return {
        "provider": provider,
        "label": spec["label"],
        "endpoint": spec["endpoint"],
        "model": env("MODEL_NAME", spec["model"]),
        "api_key": api_key,
        "extra_headers": spec["extra_headers"],
        "watch_dir": os.path.abspath(os.path.expanduser(env("WATCH_DIR", DEFAULT_WATCH_DIR))),
        "output_dir": os.path.abspath(os.path.expanduser(env("OUTPUT_DIR", DEFAULT_OUTPUT_DIR))),
    }


# ==============================================================================
# FONCTIONS SYSTÈME (multiplateformes)
# ==============================================================================
def has_display():
    """Indique si une interface graphique est disponible."""
    if IS_WINDOWS or IS_MACOS:
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def use_zenity():
    """Zenity est utilisé hors Windows/macOS lorsqu'il est disponible."""
    return (not IS_WINDOWS and not IS_MACOS and has_display()
            and shutil.which("zenity") is not None)


def ask_yes_no(title, message):
    """Pose une question oui/non à l'utilisateur. Renvoie True si « Oui »."""
    if not has_display():
        print("Aucun affichage graphique disponible : scan ignoré.")
        return False
    if use_zenity():
        result = subprocess.run(
            ["zenity", "--question", "--no-markup", "--width=420",
             f"--title={title}", f"--text={message}",
             "--ok-label=Oui", "--cancel-label=Non"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if result.returncode in (0, 1):
            return result.returncode == 0
        print(f"Erreur zenity (code {result.returncode}), affichage impossible.")
        return False

    if not IS_WINDOWS and not IS_MACOS:
        print("Avertissement : zenity introuvable, repli sur tkinter.")
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()                     # Cache la fenêtre principale Tkinter
    root.attributes("-topmost", True)   # Pop-up au premier plan
    try:
        return messagebox.askyesno(title, message, parent=root)
    finally:
        root.destroy()


def show_error(title, message):
    """Affiche une erreur (console + boîte de dialogue si possible)."""
    print(f"{title} : {message}", file=sys.stderr)
    if not has_display():
        return
    try:
        if use_zenity():
            subprocess.run(
                ["zenity", "--error", "--no-markup", "--width=420",
                 f"--timeout={ERROR_DIALOG_TIMEOUT}",
                 f"--title={title}", f"--text={message}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=ERROR_DIALOG_TIMEOUT + 5,
            )
        else:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(title, message, parent=root)
            root.destroy()
    except Exception:
        pass  # Pas d'affichage graphique disponible : le message console suffit


def open_file(path):
    """Ouvre un fichier avec l'application par défaut du système."""
    try:
        if IS_WINDOWS:
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            opener = "open" if IS_MACOS else "xdg-open"
            subprocess.Popen(
                [opener, path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
    except Exception as e:
        print(f"Impossible d'ouvrir {path} : {e}")


def wait_until_stable(path, interval=STABLE_INTERVAL, timeout=STABLE_TIMEOUT):
    """Attend que la taille du fichier ne change plus (fin de copie réseau).

    Renvoie la signature (taille, mtime) du fichier, ou None s'il a disparu
    ou n'a pas fini d'être écrit dans le délai imparti.
    """
    deadline = time.monotonic() + timeout
    previous = None
    while time.monotonic() < deadline:
        try:
            st = os.stat(path)
        except FileNotFoundError:
            return None
        current = (st.st_size, st.st_mtime_ns)
        if current == previous and st.st_size > 0:
            return current
        previous = current
        time.sleep(interval)
    return None


# ==============================================================================
# FONCTIONS DE TRAITEMENT
# ==============================================================================
def process_pdf(pdf_path, config):
    """Extraction OCR par LLM Vision et génération du fichier Markdown"""
    try:
        print(f"Lancement du traitement OCR pour : {pdf_path}")
        pdf_doc = pymupdf.open(pdf_path)
        extracted_pages = []

        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            **config["extra_headers"],
        }

        for page_num in range(len(pdf_doc)):
            print(f"Traitement page {page_num + 1}/{len(pdf_doc)} via {config['label']}...")
            page = pdf_doc[page_num]
            pix = page.get_pixmap(dpi=RENDER_DPI)
            img_bytes = pix.tobytes("png")
            base64_image = base64.b64encode(img_bytes).decode("utf-8")

            payload = {
                "model": config["model"],
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": OCR_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_image}"},
                            },
                        ],
                    }
                ],
            }

            response = requests.post(config["endpoint"], json=payload, headers=headers,
                                     timeout=API_TIMEOUT)
            if response.status_code == 200:
                text_extracted = response.json()["choices"][0]["message"]["content"]
                extracted_pages.append(text_extracted)
            else:
                print(f"Erreur API (Page {page_num+1}): {response.status_code} - {response.text}")

        pdf_doc.close()

        if not extracted_pages:
            print("Aucun texte n'a pu être extrait du document.")
            return

        # Création et écriture du fichier Markdown final
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_file_path = os.path.join(config["output_dir"], f"{base_name}.md")

        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write("\n\n---\n\n".join(extracted_pages))

        print(f"Succès : Fichier généré dans {output_file_path}")

        # Ouverture automatique dans l'éditeur par défaut
        open_file(output_file_path)

    except Exception as e:
        print(f"Erreur inattendue pendant l'OCR : {e}")


class ScanHandler(FileSystemEventHandler):
    """Place chaque PDF détecté dans une file, sans doublon en attente."""

    def __init__(self, scan_queue):
        super().__init__()
        self.scan_queue = scan_queue
        self.pending = set()
        self.lock = threading.Lock()

    def _enqueue(self, path):
        if not path.lower().endswith(".pdf"):
            return
        path = os.path.abspath(path)
        with self.lock:
            if path in self.pending:
                return
            self.pending.add(path)
        self.scan_queue.put(path)

    def release(self, path):
        with self.lock:
            self.pending.discard(path)

    def on_created(self, event):
        if not event.is_directory:
            self._enqueue(event.src_path)

    def on_moved(self, event):
        # Cas d'un fichier temporaire renommé en .pdf en fin de copie
        if not event.is_directory:
            self._enqueue(event.dest_path)

    def on_closed(self, event):
        # Linux (inotify) : fichier fermé après écriture
        if not event.is_directory:
            self._enqueue(event.src_path)


def handle_scan(pdf_path, config, handler, handled):
    """Attend la fin d'écriture, demande confirmation puis lance l'OCR."""
    signature = wait_until_stable(pdf_path)
    handler.release(pdf_path)
    if signature is None:
        return
    # Un même fichier (même taille et date) n'est proposé qu'une seule fois
    if handled.get(pdf_path) == signature:
        return
    handled[pdf_path] = signature

    file_name = os.path.basename(pdf_path)
    answer = ask_yes_no(
        "Nouveau scan détecté",
        f"Un nouveau document a été numérisé :\n\n'{file_name}'\n\n"
        "Souhaitez-vous exécuter l'OCR par IA et l'ouvrir dans l'éditeur par défaut ?",
    )

    if answer:
        threading.Thread(target=process_pdf, args=(pdf_path, config), daemon=True).start()
    else:
        print(f"Scan ignoré par l'utilisateur : {file_name}")


# ==============================================================================
# POINT D'ENTRÉE
# ==============================================================================
def main(provider=None):
    try:
        config = load_config(provider)
    except ValueError as e:
        show_error("Brother OCR - configuration", str(e))
        sys.exit(EXIT_CONFIG_ERROR)

    os.makedirs(config["watch_dir"], exist_ok=True)
    os.makedirs(config["output_dir"], exist_ok=True)

    scan_queue = queue.Queue()
    event_handler = ScanHandler(scan_queue)
    observer = Observer()
    observer.schedule(event_handler, config["watch_dir"], recursive=False)
    observer.start()

    print(f"=== Surveillance active du dossier : {config['watch_dir']} ===")
    print(f"=== Fournisseur : {config['label']} ({config['model']}) -> {config['output_dir']} ===")

    # Les scans sont traités un par un dans le thread principal :
    # une seule boîte de dialogue à la fois.
    handled = {}
    try:
        while True:
            try:
                pdf_path = scan_queue.get(timeout=1)
            except queue.Empty:
                continue
            handle_scan(pdf_path, config, event_handler, handled)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
