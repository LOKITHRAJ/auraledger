# AuraLedgerIQ

AI-powered bank statement intelligence and audit tool. Upload an Indian bank statement (Excel, CSV, or PDF — digital or scanned), and it parses, redacts PII, classifies every transaction via Google Gemini, and exports an auditor-ready styled Excel report — with zero raw PII ever leaving your machine.

See [PRD.md](PRD.md) for product scope, [TECH-SPEC.md](TECH-SPEC.md) for architecture, and [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md) for the current build status and what's still in progress.

---

## Requirements

- Python 3.10+ (developed against 3.12)
- A Google Gemini API key ([Google AI Studio](https://aistudio.google.com/apikey)) — the app defaults to Gemini as its AI provider
- Windows (for the packaged desktop executable / DPAPI-encrypted local API key storage — the Streamlit app itself runs on any OS)
- **For scanned/image PDF statements only:** [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) and [Poppler](https://github.com/oschwartz10612/poppler-windows/releases) installed and on your `PATH`. Digital (text-layer) PDFs, Excel, and CSV don't need either of these — only scanned statements route through OCR.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
   For desktop packaging or running the test suite locally, use `requirements-dev.txt` instead (it includes everything in `requirements.txt` plus `pystray`, `pyinstaller`, `pytest`, and `reportlab`). `requirements.txt` alone is what Streamlit Cloud installs — it's kept free of anything not needed to run the app itself.
2. Copy the environment template and fill in your Gemini API key:
   ```
   cp .env.example .env
   ```
   Then edit `.env` and set `GEMINI_API_KEY=...`. Never commit `.env` — it's already gitignored.
3. (Optional, for scanned-PDF OCR) Install Tesseract and Poppler using their normal installers — a standard install adds both to `PATH` automatically, and the app will find them with no further config. If you installed either to a non-standard location, set `TESSERACT_CMD` (full path to `tesseract.exe`) and `POPPLER_PATH` (path to the Poppler `bin` folder) in `.env` instead.

## Running the app

```
streamlit run app.py
```

Opens at `http://localhost:8501`. Log in with the default admin credentials:

- **Username:** `admin`
- **Password:** `admin123`

Change the password from the Settings screen after logging in (Account & Security section) — it's stored locally as a bcrypt hash, never in plaintext.

## Running the test suite

```
pytest tests/unit
```

Covers the PII redaction engine, the deterministic rule engine (bank charges/GST/interest/ATM), column-mapping logic, bank auto-detection, file validation, and PDF ingestion (digital + OCR). The OCR round-trip test skips automatically on a machine without Tesseract installed — everything else runs regardless.

## Deploying to Streamlit Community Cloud

The app has no Windows-only or local-machine dependencies at runtime — `pip install -r requirements.txt` plus the system packages in `packages.txt` (`tesseract-ocr`, `poppler-utils`, auto-installed by Streamlit Cloud) is enough.

1. Push this repo to GitHub (`.env` and any real bank statement files stay out automatically — see `.gitignore`).
2. On [share.streamlit.io](https://share.streamlit.io), create a new app pointing at this repo, branch, and `app.py`.
3. In the app's **Settings → Secrets**, add your keys in TOML format (not `.env`'s `KEY=value` syntax):
   ```
   GEMINI_API_KEY = "..."
   OPENAI_API_KEY = "..."
   ```
   Leave `TESSERACT_CMD` / `POPPLER_PATH` unset — the app already treats an empty value as "look it up on PATH," which is exactly where `packages.txt` installs the apt binaries.
4. Log in with the default admin credentials below. **Note:** Streamlit Cloud's filesystem is ephemeral — a changed admin password or saved Settings won't survive a redeploy/restart, since `ConfigManager` writes to local disk, not to any external store.

## Building the desktop executable (Windows)

```
pyinstaller AuraLedgerIQ.spec --noconfirm
```

Produces `dist/AuraLedgerIQ.exe` — a single-file Windows executable that launches a local Streamlit server, opens your default browser, and sits in the system tray. An Inno Setup installer script is available at `installer/setup.iss` for producing a distributable installer from the built exe.

## Supported bank statements

**Excel/CSV:** auto-detected by bank letterhead text (falls back to filename keywords, then to a generic best-effort column-mapping parser for anything unrecognized):

- HDFC Bank
- State Bank of India
- ICICI Bank
- Axis Bank
- City Union Bank
- Any other bank / CSV export — via the generic fallback parser

**PDF:** digital (text-layer) statements are parsed directly via table extraction; scanned/image-only statements fall back to OCR (word-position-based table reconstruction, not per-bank parsing) — works for any bank, with the caveat that OCR accuracy depends on scan quality, and dense alphanumeric codes (reference numbers) are more error-prone than dates and amounts.

## Project layout

```
app.py                  Streamlit entrypoint & page router
launcher.py              Desktop launcher (system tray, browser auto-open, single-instance lock)
screens/                 Login, Dashboard, Upload, Results, Settings
components/              Reusable UI pieces (sidebar, header, footer, charts, tables, metrics)
services/                Auth, file validation, classification orchestration, session storage
src/                     Core pipeline: parsers/, pdf_reader.py, PII anonymizer, preprocessor, AI client, Excel I/O
tests/unit/              Pytest suite
```
