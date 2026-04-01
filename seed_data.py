"""Seed the database with realistic Indian sample data for students and faculty."""
from werkzeug.security import generate_password_hash
from database import db_cursor
from datetime import date, timedelta
import random

# Default password for all sample accounts
DEFAULT_PW = generate_password_hash("password123")

def seed_sample_data():
    print("🚀 Seeding realistic Indian sample data...")
    
    try:
        with db_cursor() as (conn, cur):
            # 1. Insert Departments
            print("🏢 Inserting Departments...")
            depts = [
                ('Computer Science & Engineering', 'CSE'),
                ('Information Technology', 'IT'),
                ('Electronics & Communication', 'ECE'),
                ('Mechanical Engineering', 'ME'),
                ('Business Administration', 'BBA')
            ]
            cur.executemany("INSERT INTO departments (name, code) VALUES (%s, %s) ON CONFLICT (code) DO NOTHING", depts)
            
            # Get dept IDs
            cur.execute("SELECT id, code FROM departments")
            dept_map = {row['code']: row['id'] for row in cur.fetchall()}

            # 2. Insert Courses
            print("🎓 Inserting Courses...")
            courses = [
                (dept_map['CSE'], 'B.Tech Computer Science', 'BTECH-CSE', 4),
                (dept_map['IT'], 'Master of Computer Applications', 'MCA', 2),
                (dept_map['BBA'], 'Bachelor of Business Admin', 'BBA', 3)
            ]
            cur.executemany("INSERT INTO courses (department_id, name, code, duration_years) VALUES (%s, %s, %s, %s) ON CONFLICT (department_id, code) DO NOTHING", courses)
            
            # Get course IDs
            cur.execute("SELECT id, code FROM courses")
            course_map = {row['code']: row['id'] for row in cur.fetchall()}

            # 3. Insert Subjects
            print("📚 Inserting Subjects...")
            subjects = [
                (course_map['BTECH-CSE'], 'Data Structures', 'CS101', 1, 4),
                (course_map['BTECH-CSE'], 'Database Management', 'CS102', 1, 4),
                (course_map['MCA'], 'Advanced Java', 'MCA201', 1, 4),
                (course_map['MCA'], 'Cloud Computing', 'MCA202', 1, 3),
                (course_map['BBA'], 'Principles of Management', 'BBA101', 1, 3)
            ]
            cur.executemany("INSERT INTO subjects (course_id, name, code, semester, credits) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (course_id, semester, code) DO NOTHING", subjects)

            # 4. Insert Faculty
            print("👨‍🏫 Inserting Faculty...")
            faculty_data = [
                ('rajesh.kumar', 'rajesh@college.edu', 'Rajesh', 'Kumar', 'CSE', 'Professor', '9876543210'),
                ('sunita.sharma', 'sunita@college.edu', 'Sunita', 'Sharma', 'IT', 'Associate Professor', '9876543211'),
                ('amit.patel', 'amit@college.edu', 'Amit', 'Patel', 'ECE', 'Assistant Professor', '9876543212')
            ]
            
            for username, email, fname, lname, dcode, desg, phone in faculty_data:
                # Create User
                cur.execute("SELECT id FROM users WHERE username = %s", (username,))
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO users (role_id, email, username, password_hash) VALUES (2, %s, %s, %s) RETURNING id",
                        (email, username, DEFAULT_PW)
                    )
                    uid = cur.fetchone()['id']
                    
                    # Create Faculty Record
                    emp_id = f"EMP{random.randint(1000, 9999)}"
                    cur.execute(
                        """
                        INSERT INTO faculty (user_id, emp_id, first_name, last_name, email, phone, department_id, designation, joined_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (uid, emp_id, fname, lname, email, phone, dept_map[dcode], desg, date.today() - timedelta(days=365))
                    )

            # 5. Insert Students
            print("👨‍🎓 Inserting Students...")
            student_names = [
                ('rahul.verma', 'rahul@gmail.com', 'Rahul', 'Verma', 'BTECH-CSE', 'M'),
                ('priya.singh', 'priya@gmail.com', 'Priya', 'Singh', 'BTECH-CSE', 'F'),
                ('arjun.reddy', 'arjun@gmail.com', 'Arjun', 'Reddy', 'MCA', 'M'),
                ('sneha.gupta', 'sneha@gmail.com', 'Sneha', 'Gupta', 'MCA', 'F'),
                ('vikram.malhotra', 'vikram@gmail.com', 'Vikram', 'Malhotra', 'BBA', 'M')
            ]

            for username, email, fname, lname, ccode, gender in student_names:
                cur.execute("SELECT id FROM users WHERE username = %s", (username,))
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO users (role_id, email, username, password_hash) VALUES (3, %s, %s, %s) RETURNING id",
                        (email, username, DEFAULT_PW)
                    )
                    uid = cur.fetchone()['id']
                    
                    enroll = f"{ccode}2025{random.randint(100, 999)}"
                    cur.execute(
                        """
                        INSERT INTO students (user_id, enrollment_no, first_name, last_name, email, gender, course_id, current_semester, admission_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (uid, enroll, fname, lname, email, gender, course_map[ccode], 1, date.today() - timedelta(days=60))
                    )

            # 6. Assign Faculty to Subjects (FSA)
            print("🔗 Assigning Faculty to Subjects...")
            cur.execute("SELECT id FROM faculty LIMIT 3")
            fids = [r['id'] for r in cur.fetchall()]
            cur.execute("SELECT id, course_id, semester FROM subjects LIMIT 5")
            sids = cur.fetchall()
            
            for i, sub in enumerate(sids):
                fid = fids[i % len(fids)]
                cur.execute(
                    """
                    INSERT INTO faculty_subject_assignment (faculty_id, subject_id, course_id, semester, academic_year)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (fid, sub['id'], sub['course_id'], sub['semester'], "2024-25")
                )

            # 7. Insert Timetable Data
            print("📅 Inserting Timetable Data...")
            # For each assigned subject, add a slot on Monday/Tuesday
            for i, sub in enumerate(sids):
                fid = fids[i % len(fids)]
                day = (i % 5) + 1 # Monday to Friday
                start_hour = 9 + (i % 4)
                start_time = f"{start_hour:02d}:00:00"
                end_time = f"{start_hour + 1:02d}:00:00"
                room = f"Room-{101 + i}"
                
                cur.execute(
                    """
                    INSERT INTO timetable (course_id, subject_id, faculty_id, semester, day_of_week, start_time, end_time, room, academic_year)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (sub['course_id'], sub['id'], fid, sub['semester'], day, start_time, end_time, room, "2024-25")
                )

            print("✅ Data Seeding Completed Successfully!")
            print(f"🔑 Use password: 'password123' for all accounts.")

    except Exception as e:
        print(f"❌ Error seeding data: {e}")

if __name__ == "__main__":
    seed_sample_data()
