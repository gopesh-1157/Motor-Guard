"""
MotorGuard — Production Security & Credential Rotation Tool

Generates cryptographically random 256-bit JWT secret keys, verifies password
entropy, and updates administrative accounts in MongoDB for production deployments.
"""

import os
import sys
import secrets
import re
from pymongo import MongoClient
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "motorguard_db")


def generate_secure_secret_key() -> str:
    """Generate 64-character hex string (256-bit cryptographic entropy)."""
    return secrets.token_hex(32)


def validate_password_strength(password: str) -> bool:
    """Enforce industrial password policy: >=10 chars, uppercase, lowercase, number, symbol."""
    if len(password) < 10:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True


def rotate_user_password(username: str, new_password: str) -> bool:
    """Update password hash for a registered account in MongoDB."""
    if not validate_password_strength(new_password):
        print(f"[ERROR] Password for '{username}' does not meet complexity standards.")
        print("Requirements: Min 10 characters, including uppercase, lowercase, number, and symbol.")
        return False

    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    hashed = pwd_context.hash(new_password)

    result = db.users.update_one(
        {"username": username},
        {"$set": {"password_hash": hashed}}
    )

    if result.matched_count == 0:
        print(f"[WARN] User '{username}' not found in MongoDB database.")
        return False

    print(f"[OK] Password updated for user '{username}'.")
    return True


def audit_production_security(env_path: str = ".env"):
    """Audit .env for production compliance."""
    print("=" * 60)
    print("  MotorGuard Production Security Audit")
    print("=" * 60)

    if not os.path.isfile(env_path):
        print(f"[FAIL] Configuration file '{env_path}' not found.")
        return

    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. SECRET_KEY check
    secret_match = re.search(r"SECRET_KEY\s*=\s*(.+)", content)
    if secret_match:
        secret = secret_match.group(1).strip()
        if "change_this" in secret or len(secret) < 32:
            print("[WARN] SECRET_KEY is using development placeholder or is under 32 characters!")
            suggested = generate_secure_secret_key()
            print(f"       Suggested production key: {suggested}")
        else:
            print("[PASS] SECRET_KEY has sufficient entropy (length >= 32).")

    # 2. ENVIRONMENT check
    env_match = re.search(r"ENVIRONMENT\s*=\s*(.+)", content)
    if env_match:
        env_val = env_match.group(1).strip().lower()
        print(f"[INFO] Current ENVIRONMENT: {env_val}")

    # 3. MongoDB accounts audit
    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB_NAME]
        users = list(db.users.find({}, {"username": 1, "role": 1, "is_active": 1}))
        print(f"[INFO] Total registered users in MongoDB: {len(users)}")
        for u in users:
            print(f"       - {u.get('username')}: Role={u.get('role')} Active={u.get('is_active')}")
    except Exception as e:
        print(f"[WARN] Could not connect to MongoDB for user audit: {e}")

    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--rotate":
        user = sys.argv[2]
        pwd = sys.argv[3] if len(sys.argv) > 3 else secrets.token_urlsafe(14) + "A1!"
        rotate_user_password(user, pwd)
        print(f"Generated password for {user}: {pwd}")
    else:
        audit_production_security()
