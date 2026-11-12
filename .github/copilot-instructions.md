# Project instructions for brother-ocr

## Overview
This repository contains a Windows-focused OCR pipeline for Brother scanners. It watches a networked or local input folder (`C:\Brother\In`), converts new PDF files to images page by page, sends them to a vision-capable LLM API, and writes the extracted text as Markdown in `C:\Brother\Out`.

The project is intentionally small and script-oriented. There is no formal test suite or package manifest; the main concerns are preserving the OCR workflow and keeping the code compatible with the Windows/desktop environment it runs in.

## Repository layout
- `numer.py` and `numerisation.py`: two nearly identical entry points for the OCR watcher. They both implement the same logic with different API provider settings.
- `numerisation.vbs`: a Windows startup helper that launches the Python script in the background.
- `README.md`: minimal project overview only.

When making changes, keep the two Python entry points consistent unless you intentionally want to standardize on a single canonical script. Divergence between them is easy to miss.

## Coding expectations
- Preserve the existing behavior of the file watcher, Tkinter confirmation dialog, and PDF-to-Markdown export flow unless the task explicitly changes those behaviors.
- Prefer small, targeted edits over broad refactors.
- Keep the code compatible with Python 3 and Windows-specific execution patterns (file system paths, `os.makedirs`, `os.system("start ...")`, `watchdog`, `tkinter`).
- Use UTF-8 for generated markdown output and preserve the existing French comments and user-facing text where appropriate.
- Keep configuration values centralized near the top of the file instead of scattering them through the code.
- Do not introduce hardcoded secrets or API tokens. If the code needs credentials, use environment variables or a local config pattern that is not committed to the repository.

## API and OCR conventions
- The project uses vision-model APIs that accept image payloads as base64-encoded PNG data.
- Keep the OCR prompt text and the structured `messages` payload consistent when editing the API flow.
- If you change the provider or model settings, update both duplicate scripts together unless the task clearly chooses one canonical implementation.
- Treat the output Markdown as a faithful transcription; avoid extra explanatory text or metadata unless explicitly required.

## Validation
Because this repository has no automated tests, validate changes with the smallest available checks:
- `python -m py_compile numer.py numerisation.py`
- If the change affects the OCR pipeline, smoke-test with a sample PDF that exercises the relevant path, or at minimum verify the script still compiles and the logic remains consistent between the duplicate entry points.

## Safety and maintenance
- Do not add or commit real credentials, session tokens, or API keys.
- Avoid feature creep; this repository is a focused automation utility rather than a general-purpose application.
- If you need to change default directories or OCR behavior, document the Windows assumptions clearly, because the script is not cross-platform by default.
