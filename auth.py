"""
Authentication and user management module.
"""
import sqlite3
import re
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import current_app, session, redirect, url_for, flash
from flask_login import UserMixin, LoginManager
from werkzeug.security import generate_password_hash, check_password_hash


BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "resumes.db"


# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."


class User(UserMixin):
    """User class for Flask-Login."""
    
    def __init__(self, user_id, username, email, created_at):
        self.id = user_id
        self.username = username
        self.email = email
        self.created_at = created_at


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID from database."""
    user_data = get_user_by_id(user_id)
    if user_data:
        return User(
            user_data["id"],
            user_data["username"],
            user_data["email"],
            user_data["created_at"]
        )
    return None


# ============================================================================
# Database Helper Functions
# ============================================================================

def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_user_db():
    """Initialize users table."""
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()


def get_user_by_id(user_id):
    """Get user by ID."""
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()


def get_user_by_username(username):
    """Get user by username."""
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()


def get_user_by_email(email):
    """Get user by email."""
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()


def create_user(username, email, password):
    """Create a new user."""
    username = username.strip()
    email = email.strip().lower()

    if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", username):
        return None, "Username must be 3-20 characters and use only letters, numbers, or underscores."

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return None, "Enter a valid email address."

    if get_user_by_username(username):
        return None, "Username already exists."
    
    if get_user_by_email(email):
        return None, "Email already registered."
    
    if len(password) < 6:
        return None, "Password must be at least 6 characters."
    
    password_hash = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)
    now = datetime.utcnow().isoformat(timespec="seconds")
    
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (username, email, password_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (username, email, password_hash, now)
        )
        conn.commit()
        return cursor.lastrowid, None


def verify_user_password(username, password):
    """Verify user credentials."""
    user = get_user_by_username(username.strip())
    if user and check_password_hash(user["password_hash"], password):
        return user
    return None


def update_user_password(user_id, new_password):
    """Update user password."""
    if len(new_password) < 6:
        return False, "Password must be at least 6 characters."
    
    password_hash = generate_password_hash(new_password, method="pbkdf2:sha256", salt_length=16)
    
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id)
        )
        conn.commit()
    
    return True, "Password updated successfully."


# ============================================================================
# API Token Management
# ============================================================================

def generate_api_token(user_id, expires_in_days=30):
    """Generate a new API token for a user."""
    now = datetime.utcnow()
    expires_at = now + timedelta(days=expires_in_days)
    
    payload = {
        "user_id": user_id,
        "exp": expires_at,
        "iat": now
    }
    
    token = jwt.encode(
        payload,
        current_app.config["SECRET_KEY"],
        algorithm="HS256"
    )
    
    expires_at_str = expires_at.isoformat(timespec="seconds")
    created_at_str = now.isoformat(timespec="seconds")
    
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO api_tokens (user_id, token, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, token, created_at_str, expires_at_str)
        )
        conn.commit()
    
    return token


def verify_api_token(token):
    """Verify API token and return user_id."""
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"]
        )
        user_id = payload.get("user_id")
        
        # Verify token exists in database
        with get_db_connection() as conn:
            db_token = conn.execute(
                "SELECT * FROM api_tokens WHERE token = ? AND user_id = ?",
                (token, user_id)
            ).fetchone()
        
        return user_id if db_token else None
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_user_tokens(user_id):
    """Get all active tokens for a user."""
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT id, token, created_at, expires_at FROM api_tokens WHERE user_id = ?",
            (user_id,)
        ).fetchall()


def revoke_api_token(token):
    """Revoke an API token."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM api_tokens WHERE token = ?", (token,))
        conn.commit()


def revoke_all_user_tokens(user_id):
    """Revoke all tokens for a user."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM api_tokens WHERE user_id = ?", (user_id,))
        conn.commit()


# ============================================================================
# Decorators
# ============================================================================

def token_auth_required(f):
    """Decorator for API endpoints requiring token authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        
        # Check Authorization header
        from flask import request
        if "Authorization" in request.headers:
            auth_header = request.headers.get("Authorization")
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return {"error": "Invalid authorization header format"}, 401
        
        if not token:
            return {"error": "API token required"}, 401
        
        user_id = verify_api_token(token)
        if not user_id:
            return {"error": "Invalid or expired token"}, 401
        
        return f(user_id, *args, **kwargs)
    
    return decorated_function
