import sqlite3
import os
import hashlib
from datetime import datetime
from src.models.entities import Student, Course

class DatabaseManager:
    def __init__(self, db_path="data/db/attendance.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 1. Users (Teachers)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT
            )
        """)

        # 2. Courses (Now linked to teacher_id)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                teacher_id INTEGER,
                FOREIGN KEY(teacher_id) REFERENCES users(id)
            )
        """)

        # 3. Timetable (New Table)
        # day_of_week: 0=Monday, 6=Sunday
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
            cursor.execute("INSERT INTO users (username, password_hash, full_name) VALUES (?, ?, ?)", 
                           (username, pwd_hash, full_name))
            conn.commit()
            user_id = cursor.lastrowid
            
            # Seed data for this new teacher so they have something to test
            self._seed_data_for_teacher(user_id, cursor)
            conn.commit()
            
            return True, "Registration successful! Demo classes added."
        except sqlite3.IntegrityError:
            return False, "Username taken."
        finally:
            conn.close()

    def _seed_data_for_teacher(self, teacher_id, cursor):
        """Creates dummy courses and a timetable slot for RIGHT NOW."""
        # 1. Add a generic course
        cursor.execute("INSERT INTO courses (code, name, teacher_id) VALUES (?, ?, ?)", 
                       ("CS101", "Computer Science", teacher_id))
        cs_id = cursor.lastrowid
        
        # 2. Add a course that is active RIGHT NOW (Smart Seeding)
        now = datetime.now()
        day = now.weekday() # 0-6
        # Start 1 hour ago, End 1 hour from now
        start_h = max(0, now.hour - 1)
        end_h = min(23, now.hour + 1)
        
        start_str = f"{start_h:02d}:00"
        end_str = f"{end_h:02d}:00"
        
        cursor.execute("INSERT INTO courses (code, name, teacher_id) VALUES (?, ?, ?)", 
                       ("LIVE100", "Current Live Class", teacher_id))
        live_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO timetable (course_id, day_of_week, start_time, end_time) VALUES (?, ?, ?, ?)",
                       (live_id, day, start_str, end_str))

    def login_user(self, username, password):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        hashed = self._hash_password(password)
        cursor.execute("SELECT id, username, full_name FROM users WHERE username=? AND password_hash=?", 
                       (username, hashed))
        row = cursor.fetchone()
        conn.close()
        if row:
            return True, {"id": row[0], "username": row[1], "full_name": row[2]}
        return False, None

    # --- Course & Timetable Logic ---
    def get_courses_for_teacher(self, teacher_id):
        """Returns only courses owned by this teacher."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, code, name, teacher_id FROM courses WHERE teacher_id=?", (teacher_id,))
        rows = cursor.fetchall()
        conn.close()
        return [Course(id=r[0], code=r[1], name=r[2], teacher_id=r[3]) for r in rows]

    def get_active_course_for_teacher(self, teacher_id):
        """
        Finds which course is currently scheduled based on Time and Day.
        Returns Course object or None.
        """
        now = datetime.now()
        current_day = now.weekday() # 0=Monday
        current_time = now.strftime("%H:%M") # "14:30"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Join Courses and Timetable to find a match
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

    # --- Student & Attendance (Existing methods kept brief for context) ---
    def add_student(self, name, roll, path):
        # (Standard implementation from previous step)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO students (name, roll_number, encoding_file_path) VALUES (?, ?, ?)", (name, roll, path))
            sid = cursor.lastrowid
            # Auto enroll in all courses (for demo simplicity)
            # In a real app, you'd select specific courses
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