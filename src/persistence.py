import sqlite3
import os
from datetime import datetime
from src.models.entities import Student, Course, AttendanceRecord


class DatabaseManager:
    def __init__(self, db_path="data/db/attendance.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        self._seed_courses()  # Helper to add dummy courses

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 1. Courses Table (New)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL
            )
        """
        )

        # 2. Students Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                roll_number TEXT UNIQUE NOT NULL,
                encoding_file_path TEXT NOT NULL
            )
        """
        )

        # 3. Enrollment Table (Link Student to Course) (New)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS enrollment (
                student_id INTEGER,
                course_id INTEGER,
                FOREIGN KEY(student_id) REFERENCES students(id),
                FOREIGN KEY(course_id) REFERENCES courses(id),
                PRIMARY KEY (student_id, course_id)
            )
        """
        )

        # 4. Attendance Table (Updated with course_id)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                course_id INTEGER,
                timestamp DATETIME,
                status TEXT,
                FOREIGN KEY(student_id) REFERENCES students(id),
                FOREIGN KEY(course_id) REFERENCES courses(id)
            )
        """
        )
        conn.commit()
        conn.close()

    def _seed_courses(self):
        """Adds placeholder courses if none exist."""
        if not self.get_all_courses():
            self.add_course("CS101", "Intro to Programming")
            self.add_course("MATH202", "Linear Algebra")

    # --- Course Methods ---
    def add_course(self, code, name):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO courses (code, name) VALUES (?, ?)", (code, name)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # Course exists
        finally:
            conn.close()

    def get_all_courses(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, code, name FROM courses")
        rows = cursor.fetchall()
        conn.close()
        return [Course(id=r[0], code=r[1], name=r[2]) for r in rows]

    # --- Student Methods ---
    def add_student(self, name, roll_number, encoding_path):
        # ... (Same as before) ...
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO students (name, roll_number, encoding_file_path) VALUES (?, ?, ?)",
                (name, roll_number, encoding_path),
            )
            student_id = cursor.lastrowid

            # Auto-enroll in all courses for simplicity in this demo
            courses = self.get_all_courses()
            for course in courses:
                cursor.execute(
                    "INSERT OR IGNORE INTO enrollment (student_id, course_id) VALUES (?, ?)",
                    (student_id, course.id),
                )

            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_all_students(self):
        # ... (Same as before) ...
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, roll_number, encoding_file_path FROM students")
        rows = cursor.fetchall()
        conn.close()
        return [
            Student(id=r[0], name=r[1], roll_number=r[2], encoding_path=r[3])
            for r in rows
        ]

    def get_students_for_course(self, course_id):
        """Used to populate the attendance list for a selected course."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        query = """
            SELECT s.id, s.name, s.roll_number, s.encoding_file_path 
            FROM students s
            JOIN enrollment e ON s.id = e.student_id
            WHERE e.course_id = ?
        """
        cursor.execute(query, (course_id,))
        rows = cursor.fetchall()
        conn.close()
        return [
            Student(id=r[0], name=r[1], roll_number=r[2], encoding_path=r[3])
            for r in rows
        ]

    # --- Attendance Methods ---
    def mark_attendance(self, student_id, course_id, status="PRESENT"):
        """Marks attendance for a specific course session today."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if already marked for this course TODAY
        cursor.execute(
            """
            SELECT id FROM attendance 
            WHERE student_id = ? AND course_id = ? AND date(timestamp) = date('now')
        """,
            (student_id, course_id),
        )

        if cursor.fetchone() is None:
            cursor.execute(
                """
                INSERT INTO attendance (student_id, course_id, timestamp, status) 
                VALUES (?, ?, datetime('now', 'localtime'), ?)
            """,
                (student_id, course_id, status),
            )
            conn.commit()
            print(f"Marked {status} for Student {student_id} in Course {course_id}")
            conn.close()
            return True

        conn.close()
        return False

    def get_todays_attendance(self, course_id):
        """Gets the list of who is PRESENT today for the UI list."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        query = """
            SELECT a.student_id, a.status
            FROM attendance a
            WHERE a.course_id = ? AND date(a.timestamp) = date('now')
        """
        cursor.execute(query, (course_id,))
        rows = cursor.fetchall()
        conn.close()
        # Return a dictionary: {student_id: 'PRESENT'}
        return {row[0]: row[1] for row in rows}
