import sqlite3
import os
import hashlib
from datetime import datetime
from src.models.entities import Student, Course, TimetableSlot

class DatabaseManager:
    def __init__(self, db_path="data/db/attendance.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 1. Users (Added is_admin)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                is_admin INTEGER DEFAULT 0
            )
        """)

        # 2. Courses
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                teacher_id INTEGER,
                FOREIGN KEY(teacher_id) REFERENCES users(id)
            )
        """)

        # 3. Timetable
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS timetable (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER,
                day_of_week INTEGER,
                start_time TEXT, 
                end_time TEXT,
                FOREIGN KEY(course_id) REFERENCES courses(id)
            )
        """)

        # 4. Students
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                roll_number TEXT UNIQUE NOT NULL,
                encoding_file_path TEXT NOT NULL
            )
        """)

        # 5. Enrollment
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS enrollment (
                student_id INTEGER,
                course_id INTEGER,
                FOREIGN KEY(student_id) REFERENCES students(id),
                FOREIGN KEY(course_id) REFERENCES courses(id),
                PRIMARY KEY (student_id, course_id)
            )
        """)

        # 6. Attendance
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                course_id INTEGER,
                timestamp DATETIME,
                status TEXT,
                FOREIGN KEY(student_id) REFERENCES students(id),
                FOREIGN KEY(course_id) REFERENCES courses(id)
            )
        """)

        # --- Create Default Admin ---
        admin_user = "admin"
        admin_pass = self._hash_password("Qqwerty123!")
        try:
            cursor.execute("INSERT INTO users (username, password_hash, full_name, is_admin) VALUES (?, ?, ?, ?)", 
                           (admin_user, admin_pass, "System Administrator", 1))
            print("Admin account created.")
        except sqlite3.IntegrityError:
            pass # Admin already exists

        conn.commit()
        conn.close()

    # --- Authentication ---
    def _hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def register_user(self, username, password, full_name):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        pwd_hash = self._hash_password(password)
        try:
            cursor.execute("INSERT INTO users (username, password_hash, full_name, is_admin) VALUES (?, ?, ?, 0)", 
                           (username, pwd_hash, full_name))
            conn.commit()
            return True, "Registration successful!"
        except sqlite3.IntegrityError:
            return False, "Username taken."
        finally:
            conn.close()

    def login_user(self, username, password):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        hashed = self._hash_password(password)
        cursor.execute("SELECT id, username, full_name, is_admin FROM users WHERE username=? AND password_hash=?", 
                       (username, hashed))
        row = cursor.fetchone()
        conn.close()
        if row:
            # Return dict with is_admin flag
            return True, {"id": row[0], "username": row[1], "full_name": row[2], "is_admin": row[3]}
        return False, None

    # --- ADMIN METHODS ---
    def get_all_teachers(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, full_name FROM users WHERE is_admin=0")
        rows = cursor.fetchall()
        conn.close()
        return [{"id": r[0], "username": r[1], "full_name": r[2]} for r in rows]

    def add_course(self, code, name, teacher_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO courses (code, name, teacher_id) VALUES (?, ?, ?)", (code, name, teacher_id))
        conn.commit()
        conn.close()

    def delete_course(self, course_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM courses WHERE id=?", (course_id,))
        cursor.execute("DELETE FROM timetable WHERE course_id=?", (course_id,))
        conn.commit()
        conn.close()

    def get_timetable_for_course(self, course_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, day_of_week, start_time, end_time FROM timetable WHERE course_id=? ORDER BY day_of_week, start_time", (course_id,))
        rows = cursor.fetchall()
        conn.close()
        return [{"id":r[0], "day":r[1], "start":r[2], "end":r[3]} for r in rows]

    def add_timetable_slot(self, course_id, day, start, end):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO timetable (course_id, day_of_week, start_time, end_time) VALUES (?, ?, ?, ?)", 
                       (course_id, day, start, end))
        conn.commit()
        conn.close()

    def delete_timetable_slot(self, slot_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM timetable WHERE id=?", (slot_id,))
        conn.commit()
        conn.close()

    # --- TEACHER METHODS ---
    def get_courses_for_teacher(self, teacher_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, code, name, teacher_id FROM courses WHERE teacher_id=?", (teacher_id,))
        rows = cursor.fetchall()
        conn.close()
        return [Course(id=r[0], code=r[1], name=r[2], teacher_id=r[3]) for r in rows]

    def get_active_course_for_teacher(self, teacher_id):
        now = datetime.now()
        current_day = now.weekday()
        current_time = now.strftime("%H:%M")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = """
            SELECT c.id, c.code, c.name, c.teacher_id
            FROM courses c
            JOIN timetable t ON c.id = t.course_id
            WHERE c.teacher_id = ?
              AND t.day_of_week = ?
              AND ? BETWEEN t.start_time AND t.end_time
            LIMIT 1
        """
        cursor.execute(query, (teacher_id, current_day, current_time))
        row = cursor.fetchone()
        conn.close()

        if row:
            return Course(id=row[0], code=row[1], name=row[2], teacher_id=row[3])
        return None
    
    # --- STUDENT/GENERIC METHODS ---
    def get_all_courses(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, code, name, teacher_id FROM courses")
        rows = cursor.fetchall()
        conn.close()
        return [Course(id=r[0], code=r[1], name=r[2], teacher_id=r[3]) for r in rows]

    def add_student(self, name, roll, path):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO students (name, roll_number, encoding_file_path) VALUES (?, ?, ?)", (name, roll, path))
            sid = cursor.lastrowid
            # Auto enroll in all courses for demo
            cursor.execute("SELECT id FROM courses")
            c_ids = cursor.fetchall()
            for cid in c_ids:
                cursor.execute("INSERT OR IGNORE INTO enrollment (student_id, course_id) VALUES (?, ?)", (sid, cid[0]))
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()

    def get_all_students(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, roll_number, encoding_file_path FROM students")
        rows = cursor.fetchall()
        conn.close()
        return [Student(id=r[0], name=r[1], roll_number=r[2], encoding_path=r[3]) for r in rows]

    def get_students_for_course(self, course_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.id, s.name, s.roll_number, s.encoding_file_path 
            FROM students s
            JOIN enrollment e ON s.id = e.student_id
            WHERE e.course_id = ?
        """, (course_id,))
        rows = cursor.fetchall()
        conn.close()
        return [Student(id=r[0], name=r[1], roll_number=r[2], encoding_path=r[3]) for r in rows]

    def mark_attendance(self, student_id, course_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM attendance WHERE student_id=? AND course_id=? AND date(timestamp)=date('now')", (student_id, course_id))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO attendance (student_id, course_id, timestamp, status) VALUES (?, ?, datetime('now','localtime'), 'PRESENT')", (student_id, course_id))
            conn.commit()
            conn.close()
            return True
        conn.close()
        return False

    def get_todays_attendance(self, course_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT student_id, status FROM attendance WHERE course_id=? AND date(timestamp)=date('now')", (course_id,))
        return {r[0]: r[1] for r in cursor.fetchall()}
    
    def generate_next_roll_number(self):
        """Calculates the next available roll number."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # We try to find the highest number currently in use
        # We cast to integer to ensure '10' comes after '9', not '1'
        try:
            cursor.execute("SELECT MAX(CAST(roll_number AS INTEGER)) FROM students")
            row = cursor.fetchone()
            max_id = row[0] if row[0] is not None else 0
            next_id = max_id + 1
            return str(next_id)
        except Exception as e:
            # Fallback if something goes wrong (e.g., non-numeric IDs exist)
            return "1001" 
        finally:
            conn.close()