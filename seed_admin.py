"""Create or reset default admin user. Run after schema.sql."""
import mysql.connector
from werkzeug.security import generate_password_hash
from config import config

ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@college.edu"
ADMIN_PASSWORD = "admin123"


def seed_admin():
    conn = mysql.connector.connect(
        host=config.MYSQL_HOST,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
        port=config.MYSQL_PORT,
    )
    cur = conn.cursor()
    pw = generate_password_hash(ADMIN_PASSWORD)
    try:
        cur.execute(
            "INSERT INTO users (role_id, email, username, password_hash) VALUES (1, %s, %s, %s)",
            (ADMIN_EMAIL, ADMIN_USERNAME, pw),
        )
        conn.commit()
        print("Admin user created: admin / admin123")
    except mysql.connector.IntegrityError:
        cur.execute(
            "UPDATE users SET password_hash = %s, email = %s WHERE username = %s",
            (pw, ADMIN_EMAIL, ADMIN_USERNAME),
        )
        conn.commit()
        print("Admin password reset. Use admin / admin123 to log in.")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    seed_admin()
