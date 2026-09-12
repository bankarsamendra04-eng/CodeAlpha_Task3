"""
AI Music Studio - Secure Initial Admin Account Initializer / Seeder CLI.
Initializes or updates the dedicated administrator account securely.

Security Guarantees:
- Reads admin identity and credentials securely from environment variables or interactive prompt.
- Never prints plaintext passwords in logs or terminal output.
- Hashes password using native bcrypt with 12 salt rounds before database storage.
- Idempotent: Safely creates account if missing, or synchronizes credentials/role if existing.
- Assigns role strictly to ADMIN with full privileges and ENTERPRISE tier.
"""

import os
import sys
import getpass
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from backend.database.connection import SessionLocal, init_db
from backend.database.models import User
from backend.services.auth_service import hash_password, verify_password

def seed_admin():
    # Ensure database schema is initialized
    init_db()

    admin_username = os.getenv("ADMIN_INITIAL_USERNAME", "samendra_bankar").strip().lower()
    admin_email = os.getenv("ADMIN_INITIAL_EMAIL", "bankarsamendra04@gmail.com").strip().lower()
    admin_password = os.getenv("ADMIN_INITIAL_PASSWORD")

    if not admin_password:
        # Prompt securely without echo if not provided via environment
        admin_password = getpass.getpass("Enter initial admin password: ")

    if not admin_password or len(admin_password) < 6:
        print("[ERROR] Password must be at least 6 characters long.", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        # Check by email or username
        existing_user = db.query(User).filter(
            (User.email == admin_email) | (User.username == admin_username)
        ).first()

        hashed_pw = hash_password(admin_password)

        if existing_user:
            # Update existing user to ensure ADMIN role, correct email, and updated hash
            existing_user.username = admin_username
            existing_user.email = admin_email
            existing_user.hashed_password = hashed_pw
            existing_user.role = "ADMIN"
            existing_user.subscription_tier = "ENTERPRISE"
            existing_user.is_active = True
            db.commit()
            db.refresh(existing_user)
            print(f"[SUCCESS] Updated existing user to ADMIN role (Username: {existing_user.username}, Email: {existing_user.email})")
        else:
            new_admin = User(
                username=admin_username,
                email=admin_email,
                hashed_password=hashed_pw,
                role="ADMIN",
                subscription_tier="ENTERPRISE",
                is_active=True,
            )
            db.add(new_admin)
            db.commit()
            db.refresh(new_admin)
            print(f"[SUCCESS] Initialized new ADMIN user (Username: {new_admin.username}, Email: {new_admin.email})")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Database error during admin seeding: {type(e).__name__}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    seed_admin()
