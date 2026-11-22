"""Lanceur historique : pipeline OCR via l'API DeepSeek (voir brother_ocr.py).

Utilisé par numerisation.vbs au démarrage de Windows.
"""
from brother_ocr import main

if __name__ == "__main__":
    main(provider="deepseek")
