# AI Resume Parser

A production-oriented Flask web application for parsing PDF resumes into structured candidate data. It uses SQLite for persistence, session-based authentication for the web app, bearer-token authentication for REST APIs, `pdfplumber` for PDF text extraction, and regex/heuristic parsing. It does not use spaCy.

## Features

- Public landing page with Three.js and GSAP animation
- Login and registration with hashed passwords
- Authenticated dashboard with upload, ranking, score analytics, and charts
- Resume history page
- PDF upload validation and `pdfplumber` text extraction
- Regex-based extraction for name, email, phone, skills, education, and experience
- Resume score out of 100 with AI-style improvement suggestions
- Dark/light theme with local preference persistence
- Glassmorphism responsive mobile-first UI
- SQLite database integration
- JSON and CSV downloads
- Token-authenticated REST API endpoints
- Error handling for invalid type, oversized files, unreadable PDFs, missing auth, and unauthorized access

## Project Structure

```text
resume_parser/
├── app.py
├── auth.py
├── parser.py
├── requirements.txt
├── API_DOCUMENTATION.md
├── README.md
├── uploads/
├── static/
│   ├── css/styles.css
│   └── js/app.js
└── templates/
    ├── landing.html
    ├── dashboard.html
    ├── history.html
    ├── result.html
    ├── login.html
    ├── register.html
    ├── profile.html
    ├── api_docs.html
    └── 404.html
```

## Installation

Python 3.14 compatible: the app avoids spaCy and other heavyweight NLP model dependencies.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Deploy

This repository includes `render.yaml`, `Procfile`, and `wsgi.py` for production deployment.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/aryansinha21/Resume_Parser)

Recommended Render settings if creating the service manually:

```text
Environment: Python
Build command: pip install -r requirements.txt
Start command: python -m waitress --host=0.0.0.0 --port=$PORT wsgi:app
```

Environment variables:

```text
SECRET_KEY=<generate a long random value>
PYTHON_VERSION=3.14
FLASK_DEBUG=0
SESSION_COOKIE_SECURE=1
```

For Python launchers without `py -3.14`, use:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

## Configuration

Set these environment variables before running in production:

```powershell
$env:SECRET_KEY = "replace-with-a-long-random-secret"
$env:FLASK_DEBUG = "0"
$env:SESSION_COOKIE_SECURE = "1"
python app.py
```

`SESSION_COOKIE_SECURE=1` should be used behind HTTPS. The local development URL is HTTP, so leave it unset locally.

## Main Routes

- `/` public landing page
- `/register` create an account
- `/login` sign in
- `/dashboard` upload resumes and view analytics
- `/history` view parsed resume history
- `/result/<id>` view parsed fields, score, suggestions, and exports
- `/profile` manage API tokens
- `/api/docs` quick API reference

## REST API

Generate a token from `/profile`, then call:

```bash
curl -X POST http://127.0.0.1:5000/api/parse \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "resume=@resume.pdf"
```

Endpoints:

```text
POST /api/parse
GET  /api/resumes?limit=10
GET  /api/resume/<id>
GET  /api/analytics
```

## Parser Notes

The parser is intentionally deterministic and model-free:

- `pdfplumber` extracts selectable PDF text.
- Regex finds email and phone numbers.
- Header heuristics infer the candidate name.
- Section detection and keyword hints extract education, experience, certifications, and skills.
- Scoring combines contact details, skills, education, experience, and certifications into a 100-point score.

To expand skills, edit `SKILLS_DB` in `parser.py`.

## Production Notes

- Use a strong `SECRET_KEY`.
- Run behind HTTPS and set `SESSION_COOKIE_SECURE=1`.
- Put the app behind a WSGI server such as Waitress or Gunicorn in real deployments.
- Keep `uploads/` and `resumes.db` out of version control.
- SQLite is suitable for local/small deployments; move to PostgreSQL for concurrent multi-user production traffic.
