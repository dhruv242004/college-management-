"""Create or reset default admin user. Works with both MySQL and PostgreSQL."""
from werkzeug.security import generate_password_hash
from database import db_cursor

ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@college.edu"
ADMIN_PASSWORD = "admin123"

def seed_admin():
    print("🌱 Seeding Admin user...")
    pw = generate_password_hash(ADMIN_PASSWORD)
    try:
        with db_cursor() as (conn, cur):
            # 1. Ensure roles exist (just in case)
            cur.execute("SELECT COUNT(*) as c FROM roles")
            if cur.fetchone()['c'] == 0:
                print("⚠️ Roles missing. Inserting default roles...")
                roles = [('admin',), ('faculty',), ('student',), ('accountant',)]
                cur.executemany("INSERT INTO roles (name) VALUES (%s)", roles)

            # 2. Insert or update admin user
            cur.execute("SELECT id FROM users WHERE username = %s", (ADMIN_USERNAME,))
            if cur.fetchone():
                cur.execute(
                    "UPDATE users SET password_hash = %s, email = %s WHERE username = %s",
                    (pw, ADMIN_EMAIL, ADMIN_USERNAME),
                )
                print("✅ Admin password reset. Use: admin / admin123")
            else:
                cur.execute(
                    "INSERT INTO users (role_id, email, username, password_hash) VALUES (1, %s, %s, %s)",
                    (ADMIN_EMAIL, ADMIN_USERNAME, pw),
                )
                print("✅ Admin user created: admin / admin123")
    except Exception as e:
        print(f"❌ Error seeding admin: {e}")

if __name__ == "__main__":
    seed_admin()
