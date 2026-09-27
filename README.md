# FoundRisk Edge — Integrated Private Due-Diligence Workspace

Flask + SQLite app with a premium landing page, account sign-up/sign-in, session-protected workspace, document intelligence, analysis, contradiction engine, evidence explorer, risk findings, local evidence-grounded copilot, benchmarks, and settings.

## Run locally

1. Python 3.10+ recommended.
2. Create and activate a virtual environment.
3. Install: `pip install -r requirements.txt`
4. Set a unique secret key before non-local deployment: `FOUNDRISK_SECRET_KEY`.
5. Start: `python run.py`
6. Open `http://127.0.0.1:5000`, create an account, and enter the workspace.

## Data and security notes

- Account passwords are stored as Werkzeug password hashes, never plaintext.
- Workspace pages and API endpoints require a session. Project access is scoped to the signed-in account.
- Forms use CSRF tokens; API write requests use the `X-CSRFToken` header.
- Set `COOKIE_SECURE=1` only when serving over HTTPS.
- Email verification, password-reset email, OAuth/social login, and production deployment hardening are not configured.
- The app performs local/rule-based extraction and evidence retrieval; it does not claim external verification.
- Qualcomm NPU/AI Hub results are shown only when a genuine report is imported. Do not claim device/NPU verification unless you actually run the hosted/device workflow.

## Test

`pytest -q`

The included test suite covers the pre-existing document parsing, normalization, extraction, provenance, API, and contradiction logic. Authentication behavior is additionally covered by `tests/test_auth.py`.


## Scanned PDF OCR

FoundRisk first reads a PDF text layer. If a page has little/no selectable text, it attempts local Tesseract OCR. Install the Tesseract OCR engine and its English language data on the same computer that runs the Flask app. On Windows, install Tesseract OCR and either add `tesseract.exe` to PATH or set `TESSERACT_CMD` to its full path. Optional environment settings: `FOUNDRISK_OCR_LANG` (default `eng`) and `FOUNDRISK_OCR_SCALE` (default `2`). OCR output is an extraction aid and still requires source review.

## 🛠️ Tech Stack

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white" />
  <img src="https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white" />
  <img src="https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" />
  <img src="https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white" />
  <img src="https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white" />
  <img src="https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white" />
</p>
