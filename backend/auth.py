import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from flask import request, jsonify, g

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_EXPIRY_DAYS = 7


def _get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            TEXT PRIMARY KEY,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL
            )
        """)
        conn.commit()


def create_user(email: str, password: str):
    """Returns user dict or None if email already exists."""
    user_id = str(uuid.uuid4())
    hashed = generate_password_hash(password, method="pbkdf2:sha256")
    now = datetime.now(timezone.utc).isoformat()
    try:
        with _get_db() as conn:
            conn.execute(
                "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (user_id, email.lower().strip(), hashed, now),
            )
            conn.commit()
        return {"id": user_id, "email": email.lower().strip()}
    except sqlite3.IntegrityError:
        return None


def verify_user(email: str, password: str):
    """Returns user dict if credentials valid, else None."""
    with _get_db() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()
    if not row:
        return None
    if not check_password_hash(row["password_hash"], password):
        return None
    return {"id": row["id"], "email": row["email"]}


def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_token(token: str):
    """Returns user_id string or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except jwt.PyJWTError:
        return None


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authentication required"}), 401
        token = auth_header[7:]
        user_id = verify_token(token)
        if not user_id:
            return jsonify({"error": "Invalid or expired token"}), 401
        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated
