import csv
import io
import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename

from parser import PDFParseError, parse_resume
from auth import (
    init_user_db,
    login_manager,
    User,
    create_user,
    verify_user_password,
    get_user_by_id,
    generate_api_token,
    get_user_tokens,
    revoke_api_token,
    revoke_all_user_tokens,
    token_auth_required,
)


# ============================================================================
# Flask Configuration
# ============================================================================
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
DATABASE = BASE_DIR / "resumes.db"
ALLOWED_EXTENSIONS = {"pdf"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-resume-parser-secret")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE") == "1"

UPLOAD_FOLDER.mkdir(exist_ok=True)

# Initialize Flask-Login
login_manager.init_app(app)


# ============================================================================
# Database Helpers
# ============================================================================

def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables."""
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                parsed_json TEXT NOT NULL,
                score INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(resumes)").fetchall()
        }
        if "user_id" not in columns:
            conn.execute("ALTER TABLE resumes ADD COLUMN user_id INTEGER DEFAULT 1")
        conn.commit()
    # Also initialize user database
    init_user_db()


def save_resume_record(user_id, original_filename, stored_filename, parsed_data):
    """Save resume parsing result to database."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO resumes (
                user_id, original_filename, stored_filename, parsed_json, score, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                original_filename,
                stored_filename,
                json.dumps(parsed_data),
                parsed_data["score"]["total"],
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
        return cursor.lastrowid


def get_resume_record(resume_id):
    """Get a single resume record by ID."""
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT * FROM resumes WHERE id = ?", (resume_id,)
        ).fetchone()


def get_ranked_resumes(user_id=None, limit=10):
    """Get ranked resumes, optionally filtered by user."""
    with get_db_connection() as conn:
        if user_id:
            rows = conn.execute(
                """
                SELECT id, original_filename, parsed_json, score, created_at
                FROM resumes
                WHERE user_id = ?
                ORDER BY score DESC, created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, original_filename, parsed_json, score, created_at
                FROM resumes
                ORDER BY score DESC, created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    ranked = []
    for index, row in enumerate(rows, start=1):
        parsed = json.loads(row["parsed_json"])
        ranked.append(
            {
                "rank": index,
                "id": row["id"],
                "filename": row["original_filename"],
                "name": parsed.get("full_name") or "Unknown candidate",
                "score": row["score"],
                "created_at": row["created_at"],
            }
        )
    return ranked


def get_resume_history(user_id, limit=100):
    """Get a user's resume records newest first."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, original_filename, parsed_json, score, created_at
            FROM resumes
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

    history = []
    for row in rows:
        parsed = json.loads(row["parsed_json"])
        history.append(
            {
                "id": row["id"],
                "filename": row["original_filename"],
                "name": parsed.get("full_name") or "Unknown candidate",
                "email": parsed.get("email") or "",
                "skills_count": len(parsed.get("skills", [])),
                "score": row["score"],
                "label": parsed.get("ranking_label", ""),
                "created_at": row["created_at"],
            }
        )
    return history


def get_dashboard_stats(user_id):
    """Build small analytics payload for the dashboard charts."""
    history = get_resume_history(user_id)
    scores = [item["score"] for item in history]
    labels = [item["filename"][:18] for item in history[:8]]
    chart_scores = [item["score"] for item in history[:8]]
    return {
        "total_resumes": len(history),
        "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "best_score": max(scores) if scores else 0,
        "latest_score": scores[0] if scores else 0,
        "chart_labels": labels,
        "chart_scores": chart_scores,
    }


# ============================================================================
# Helper Functions
# ============================================================================

def allowed_file(filename):
    """Check if file has allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def store_uploaded_file(file_storage):
    """Store uploaded file and return filenames."""
    original_filename = secure_filename(file_storage.filename)
    unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
    destination = app.config["UPLOAD_FOLDER"] / unique_filename
    file_storage.save(destination)
    return original_filename, unique_filename, destination


def record_to_payload(record):
    """Convert database record to API payload."""
    if not record:
        return None
    payload = json.loads(record["parsed_json"])
    payload["resume_id"] = record["id"]
    payload["filename"] = record["original_filename"]
    payload["created_at"] = record["created_at"]
    return payload


def csv_safe(value):
    """Escape CSV values to prevent injection."""
    text = str(value)
    if text.startswith(("=", "+", "-", "@")):
        return f"'{text}"
    return text


# ============================================================================
# Authentication Routes
# ============================================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register a new user."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        
        if not username:
            flash("Username is required.", "danger")
        elif not email:
            flash("Email is required.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        else:
            user_id, error = create_user(username, email, password)
            if error:
                flash(error, "danger")
            else:
                # Load and login the user
                user = get_user_by_id(user_id)
                login_user(User(user["id"], user["username"], user["email"], user["created_at"]))
                flash("Registration successful! Welcome!", "success")
                return redirect(url_for("dashboard"))
    
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login user."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        if not username or not password:
            flash("Username and password are required.", "danger")
        else:
            user_data = verify_user_password(username, password)
            if user_data:
                user = User(user_data["id"], user_data["username"], user_data["email"], user_data["created_at"])
                login_user(user)
                next_page = request.args.get("next")
                flash(f"Welcome back, {username}!", "success")
                return redirect(next_page or url_for("dashboard"))
            else:
                flash("Invalid username or password.", "danger")
    
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    """Logout user."""
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/profile")
@login_required
def profile():
    """User profile page with API token management."""
    tokens = get_user_tokens(current_user.id)
    return render_template("profile.html", tokens=tokens, user=current_user)


@app.route("/api-token/generate", methods=["POST"])
@login_required
def generate_token():
    """Generate new API token."""
    expires_days = request.form.get("expires_days", 30, type=int)
    token = generate_api_token(current_user.id, expires_days)
    flash(f"API token generated. Copy it now: {token}", "success")
    return redirect(url_for("profile"))


@app.route("/api-token/revoke/<token>", methods=["POST"])
@login_required
def revoke_token(token):
    """Revoke an API token."""
    # Verify user owns this token
    tokens = get_user_tokens(current_user.id)
    if any(t["token"] == token for t in tokens):
        revoke_api_token(token)
        flash("API token revoked.", "success")
    else:
        flash("Token not found.", "danger")
    return redirect(url_for("profile"))


@app.route("/api-token/revoke-all", methods=["POST"])
@login_required
def revoke_all_tokens():
    """Revoke all user tokens."""
    revoke_all_user_tokens(current_user.id)
    flash("All API tokens revoked.", "success")
    return redirect(url_for("profile"))


# ============================================================================
# Web Routes
# ============================================================================

@app.route("/")
def landing():
    """Public landing page with 3D animation."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    """User dashboard: upload, analytics, and recent rankings."""
    if request.method == "POST":
        file = request.files.get("resume")

        if not file or not file.filename:
            flash("Please choose a PDF resume before parsing.", "danger")
            return redirect(url_for("dashboard"))

        if not allowed_file(file.filename):
            flash("Only PDF files are supported.", "danger")
            return redirect(url_for("dashboard"))

        original_filename, stored_filename, file_path = store_uploaded_file(file)

        try:
            parsed_data = parse_resume(file_path)
        except PDFParseError as exc:
            file_path.unlink(missing_ok=True)
            flash(str(exc), "danger")
            return redirect(url_for("dashboard"))
        except Exception:
            file_path.unlink(missing_ok=True)
            flash("The resume could not be parsed. Please upload a valid PDF.", "danger")
            return redirect(url_for("dashboard"))

        resume_id = save_resume_record(current_user.id, original_filename, stored_filename, parsed_data)
        return redirect(url_for("result", resume_id=resume_id))

    rankings = get_ranked_resumes(current_user.id)
    stats = get_dashboard_stats(current_user.id)
    return render_template("dashboard.html", rankings=rankings, stats=stats, user=current_user)


@app.route("/history")
@login_required
def history():
    """Resume history page."""
    return render_template("history.html", resumes=get_resume_history(current_user.id), user=current_user)


@app.route("/result/<int:resume_id>")
@login_required
def result(resume_id):
    """View resume parsing result."""
    record = get_resume_record(resume_id)
    if not record:
        flash("Resume result not found.", "warning")
        return redirect(url_for("dashboard"))
    
    # Check ownership
    if record["user_id"] != current_user.id:
        flash("You do not have permission to view this resume.", "danger")
        return redirect(url_for("dashboard"))

    parsed_data = json.loads(record["parsed_json"])
    return render_template(
        "result.html",
        resume_id=resume_id,
        filename=record["original_filename"],
        parsed=parsed_data,
        rankings=get_ranked_resumes(current_user.id),
        user=current_user,
    )


# ============================================================================
# Download Routes
# ============================================================================

@app.route("/download/<int:resume_id>/json")
@login_required
def download_json(resume_id):
    """Download resume as JSON."""
    record = get_resume_record(resume_id)
    if not record or record["user_id"] != current_user.id:
        return jsonify({"error": "Resume not found"}), 404

    payload = record_to_payload(record)
    memory_file = io.BytesIO(json.dumps(payload, indent=2).encode("utf-8"))
    return send_file(
        memory_file,
        mimetype="application/json",
        as_attachment=True,
        download_name=f"resume_{resume_id}.json",
    )


@app.route("/download/<int:resume_id>/csv")
@login_required
def download_csv(resume_id):
    """Download resume as CSV."""
    record = get_resume_record(resume_id)
    if not record or record["user_id"] != current_user.id:
        return jsonify({"error": "Resume not found"}), 404

    payload = record_to_payload(record)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Field", "Value"])
    rows = [
        ("Resume ID", payload["resume_id"]),
        ("Filename", payload["filename"]),
        ("Full Name", payload.get("full_name", "")),
        ("Email", payload.get("email", "")),
        ("Phone", payload.get("phone", "")),
        ("Skills", ", ".join(payload.get("skills", []))),
        ("Education", " | ".join(payload.get("education", []))),
        ("Experience", " | ".join(payload.get("experience", []))),
        ("Certifications", " | ".join(payload.get("certifications", []))),
        ("Score", payload.get("score", {}).get("total", 0)),
        ("Recommendations", " | ".join(payload.get("recommendations", []))),
    ]
    writer.writerows((label, csv_safe(value)) for label, value in rows)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=resume_{resume_id}.csv"},
    )


# ============================================================================
# REST API Routes
# ============================================================================

@app.route("/api/parse", methods=["POST"])
@token_auth_required
def api_parse_resume(user_id):
    """API endpoint to parse resume (requires API token)."""
    file = request.files.get("resume")

    if not file or not file.filename:
        return jsonify({"error": "Upload a PDF file using the 'resume' field."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF files are supported."}), 400

    original_filename, stored_filename, file_path = store_uploaded_file(file)

    try:
        parsed_data = parse_resume(file_path)
    except PDFParseError as exc:
        file_path.unlink(missing_ok=True)
        return jsonify({"error": str(exc)}), 400
    except Exception:
        file_path.unlink(missing_ok=True)
        return jsonify({"error": "The uploaded PDF could not be parsed."}), 400

    resume_id = save_resume_record(user_id, original_filename, stored_filename, parsed_data)
    parsed_data["resume_id"] = resume_id
    parsed_data["filename"] = original_filename
    return jsonify(parsed_data), 201


@app.route("/api/resume/<int:resume_id>", methods=["GET"])
@token_auth_required
def api_get_resume(user_id, resume_id):
    """API endpoint to get a specific resume (requires API token)."""
    record = get_resume_record(resume_id)
    if not record or record["user_id"] != user_id:
        return jsonify({"error": "Resume not found"}), 404
    
    return jsonify(record_to_payload(record))


@app.route("/api/resumes", methods=["GET"])
@token_auth_required
def api_list_resumes(user_id):
    """API endpoint to list user's resumes (requires API token)."""
    limit = request.args.get("limit", 10, type=int)
    rankings = get_ranked_resumes(user_id, limit)
    return jsonify({"resumes": rankings, "total": len(rankings)})


@app.route("/api/analytics", methods=["GET"])
@token_auth_required
def api_analytics(user_id):
    """API endpoint for dashboard analytics."""
    return jsonify(get_dashboard_stats(user_id))


@app.route("/api/docs")
def api_docs():
    """Lightweight API documentation page."""
    return render_template("api_docs.html")


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(413)
def file_too_large(_error):
    """Handle file too large error."""
    flash("The uploaded PDF is too large. Maximum size is 8 MB.", "danger")
    return redirect(url_for("dashboard") if current_user.is_authenticated else url_for("landing"))


@app.errorhandler(404)
def not_found(_error):
    """Handle 404 errors."""
    return render_template("404.html"), 404


# ============================================================================
# Initialization
# ============================================================================

init_db()

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
