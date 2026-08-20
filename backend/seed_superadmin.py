"""
Seeds the ONE demo SuperAdmin account into MongoDB, and keeps it usable.

- Idempotent: running this multiple times never creates duplicate accounts.
- Self-healing: if a SuperAdmin record already exists for the demo email but
  its password hash does not match the configured demo password (e.g. an
  earlier run used a different SEED_SUPERADMIN_PASSWORD, or the record was
  edited by hand), the hash is regenerated and updated in place. The
  existing user_id and every other field are preserved -- the account is
  synchronized, never replaced.
- Connects through database/mongodb.py, the exact same connection module the
  running FastAPI app uses (same MONGO_URL / DB_NAME / `users` collection),
  so this can never seed a different database than the API reads from.
- Passwords are hashed with bcrypt via utils/security.py -- the project's
  existing hashing utility, not a second implementation. The plain password
  is never written to the database.

Usage:
    python seed_superadmin.py
"""
import asyncio
from datetime import datetime, timezone

from config import settings
from database.mongodb import connect_to_mongo, close_mongo_connection, get_db
from utils.security import hash_password, verify_password, generate_id


async def seed():
    await connect_to_mongo()
    db = get_db()

    print("Checking SuperAdmin...")
    existing = await db.users.find_one({"email": settings.SEED_SUPERADMIN_EMAIL})

    if not existing:
        user_doc = {
            "user_id": generate_id("USR"),
            "name": settings.SEED_SUPERADMIN_NAME,
            "email": settings.SEED_SUPERADMIN_EMAIL,
            "mobile": settings.SEED_SUPERADMIN_MOBILE,
            "password_hash": hash_password(settings.SEED_SUPERADMIN_PASSWORD),
            "role": "SUPERADMIN",
            "status": "ACTIVE",
            "created_date": datetime.now(timezone.utc),
        }
        await db.users.insert_one(user_doc)
        print("[seed] Demo SuperAdmin created successfully.")
    else:
        print("SuperAdmin exists.")
        print("Verifying password...")

        updates = {}

        password_ok = verify_password(settings.SEED_SUPERADMIN_PASSWORD, existing.get("password_hash", ""))
        if not password_ok:
            print("Password mismatch detected.")
            print("Updating SuperAdmin password hash...")
            updates["password_hash"] = hash_password(settings.SEED_SUPERADMIN_PASSWORD)
        else:
            print("Password verified.")

        # Ensure role/status invariants without touching anything else --
        # user_id and all other existing fields are preserved as-is.
        if existing.get("role") != "SUPERADMIN":
            updates["role"] = "SUPERADMIN"
        if existing.get("status") != "ACTIVE":
            updates["status"] = "ACTIVE"
        # `is_active` is not part of this project's user schema (only
        # `status` is used), so there is nothing further to normalize there.

        if updates:
            await db.users.update_one({"_id": existing["_id"]}, {"$set": updates})
            print("SuperAdmin account synchronized successfully.")
        else:
            print("SuperAdmin demo account is already configured correctly.")

    print("[seed] Demo SuperAdmin ready.")
    print(f"[seed]   Demo Email:    {settings.SEED_SUPERADMIN_EMAIL}")
    print(f"[seed]   Demo Password: {settings.SEED_SUPERADMIN_PASSWORD}")
    print("[seed]   Status: ACTIVE")
    print("[seed]   Role:   SUPERADMIN")
    print(f"[seed]   Demo OTP for mobile login: {settings.DEMO_OTP}")

    await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(seed())
