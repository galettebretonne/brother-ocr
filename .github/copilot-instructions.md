# Project instructions for brother-ocr

## Overview
This repository contains a cross-platform (Windows and Linux) OCR pipeline for Brother scanners. It watches an input folder (`C:\Brother\In` on Windows, `~/Brother/In` on Linux by default), converts new PDF files to images page by page, sends them to a vision-capable LLM API, and writes the extracted text as Markdown in the output folder (`C:\Brother\Out` / `~/Brother/Out`).

The project is intentionally small and script-oriented. There is no formal test suite.

## Repository layout
- `brother_ocr.py`: the single canonical implementation (configuration, watcher, confirmation dialog, OCR, Markdown export). All logic changes go here.
- `numer.py` / `numerisation.py`: thin launchers that call `brother_ocr.main(provider="opencode")` / `main(provider="deepseek")`. Keep them as launchers; do not duplicate logic in them.
- `numerisation.vbs`: Windows startup helper (runs `numerisation.py` with `pythonw.exe`).
- `linux/brother-ocr.service`: systemd user unit template (`@REPO_DIR@` is substituted by `linux/install.sh`).
- `linux/install.sh`: creates `.venv`, installs `requirements.txt`, creates `~/.config/brother-ocr/env`, installs and enables the unit.
- `requirements.txt`, `.env.example`, `.gitignore`.

## Coding expectations
- Keep the code working on both Windows and Linux. Use the existing helpers for platform-specific behavior:
  - `ask_yes_no()` / `show_error()`: zenity on Linux, tkinter on Windows (and as a fallback).
  - `open_file()`: `os.startfile` on Windows, `xdg-open` on Linux, `open` on macOS.
  - `wait_until_stable()`: waits for the file size to stop changing before processing.
- Use `os.path` / `pathlib`; never hardcode path separators or drive letters outside the OS-specific defaults.
- Scans are processed sequentially from a `queue.Queue` in the main thread so only one dialog is shown at a time; OCR itself runs in a worker thread.
- Keep configuration values centralized near the top of `brother_ocr.py` (`PROVIDERS`, defaults, prompt, DPI, timeouts). New providers are added as entries in `PROVIDERS`.
- Use UTF-8 for generated Markdown and preserve the French comments and user-facing text.
- Prefer small, targeted edits over broad refactors. Avoid adding dependencies.

## Configuration and secrets
- All settings come from environment variables (`OCR_PROVIDER`, `OCR_API_KEY`, `OPENCODE_API_KEY`, `DEEPSEEK_API_KEY`, `MODEL_NAME`, `WATCH_DIR`, `OUTPUT_DIR`), optionally loaded from a `.env` file next to the script, or from `~/.config/brother-ocr/env` via systemd on Linux.
- Never hardcode or commit API keys. `.env` is gitignored; `.env.example` must only contain empty placeholders.
- A missing key exits with code 78, which the systemd unit treats as non-restartable.

## API and OCR conventions
- The vision APIs accept OpenAI-style `chat/completions` payloads with base64-encoded PNG images.
- Keep the OCR prompt (`OCR_PROMPT`) and the `messages` payload structure consistent when editing the API flow.
- Treat the output Markdown as a faithful transcription; pages are joined with `---`. Do not add extra metadata unless explicitly required.

## Validation
- `python -m py_compile brother_ocr.py numer.py numerisation.py`
- `bash -n linux/install.sh` and, after substitution of `@REPO_DIR@`, `systemd-analyze --user verify` on the unit.
- If the change affects the pipeline, smoke-test by dropping a sample PDF in the watched folder.
