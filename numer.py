import os
import time
import base64
import threading
import tkinter as tk
from tkinter import messagebox
import pymupdf
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ==============================================================================
# CONFIGURATION
# ==============================================================================
WATCH_DIR = r"C:\Brother\In"      # Dossier d'entrée (scans de la Brother)
OUTPUT_DIR = r"C:\Brother\Out"    # Dossier de sortie (.md)

# Configuration API OpenCode Zen / Go
OPENCODE_ENDPOINT = "https://opencode.ai/zen/v1/chat/completions"
OPENCODE_API_KEY = "***REMOVED***"  # Remplace par ta vraie clé d'API OpenCode Zen
MODEL_NAME = "deepseek-v4.1-flash" # Modèle Vision ultra-économique

# ==============================================================================
# FONCTIONS DE TRAITEMENT
# ==============================================================================
def process_pdf(pdf_path):
    """Extraction OCR par LLM Vision et génération du fichier Markdown"""
    try:
        print(f"Lancement du traitement OCR pour : {pdf_path}")
        pdf_doc = pymupdf.open(pdf_path)
        extracted_pages = []
        
        for page_num in range(len(pdf_doc)):
            print(f"Traitement page {page_num + 1}/{len(pdf_doc)} via OpenCode Zen...")
            page = pdf_doc[page_num]
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            base64_image = base64.b64encode(img_bytes).decode('utf-8')
            
            # En-têtes requis par la passerelle OpenCode Zen / Go
            headers = {
                "Authorization": f"Bearer {OPENCODE_API_KEY}",
                "Content-Type": "application/json",
                "x-opencode-session": "script-ocr-win",
                "HTTP-Referer": "https://opencode.ai",
                "X-Title": "Brother OCR Pipeline"
            }
            
            payload = {
                "model": MODEL_NAME,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text", 
                                "text": "Fais un OCR exact et rigoureux de cette page. Transcris l'intégralité du texte en respectant fidèlement la structure (titres, paragraphes, tableaux au format Markdown). Ne rajoute aucun commentaire ni préambule, ne precise pas si il y a eu une rotation du texte. Réponds uniquement avec le texte transcrit."
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                            }
                        ]
                    }
                ]
            }
            
            response = requests.post(OPENCODE_ENDPOINT, json=payload, headers=headers, timeout=90)
            if response.status_code == 200:
                text_extracted = response.json()['choices'][0]['message']['content']
                extracted_pages.append(text_extracted)
            else:
                print(f"Erreur API (Page {page_num+1}): {response.status_code} - {response.text}")

        pdf_doc.close()
        
        if not extracted_pages:
            print("Aucun texte n'a pu être extrait du document.")
            return

        # Création et écriture du fichier Markdown final
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_file_path = os.path.join(OUTPUT_DIR, f"{base_name}.md")
        
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write("\n\n---\n\n".join(extracted_pages))
            
        print(f"Succès : Fichier généré dans {output_file_path}")
        
        # Ouverture automatique dans ONLYOFFICE (ou l'éditeur par défaut)
        os.system(f'start "" "{output_file_path}"')

    except Exception as e:
        print(f"Erreur inattendue pendant l'OCR : {e}")

def ask_user_confirmation(pdf_path):
    """Affiche une boîte de dialogue pour valider le traitement du fichier"""
    root = tk.Tk()
    root.withdraw()                   # Cache la fenêtre principale Tkinter
    root.attributes("-topmost", True)  # Pop-up au premier plan
    
    file_name = os.path.basename(pdf_path)
    answer = messagebox.askyesno(
        "Nouveau scan détecté",
        f"Un nouveau document a été numérisé :\n\n'{file_name}'\n\nSouhaitez-vous exécuter l'OCR par IA et l'ouvrir dans ONLYOFFICE ?",
        parent=root
    )
    root.destroy()
    
    if answer:
        threading.Thread(target=process_pdf, args=(pdf_path,), daemon=True).start()
    else:
        print(f"Scan ignoré par l'utilisateur : {file_name}")

class ScanHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory or not event.src_path.lower().endswith('.pdf'):
            return
        
        pdf_path = event.src_path
        # Pause temporaire pour attendre la fin d'écriture du fichier par le réseau
        time.sleep(3)
        
        ask_user_confirmation(pdf_path)

# ==============================================================================
# POINT D'ENTRÉE
# ==============================================================================
if __name__ == "__main__":
    os.makedirs(WATCH_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    event_handler = ScanHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIR, recursive=False)
    observer.start()
    
    print(f"=== Surveillance active du dossier : {WATCH_DIR} ===")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()