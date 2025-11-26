import sqlite3
import os
from datetime import datetime

# Updated import path
from src.models.entities import Student


class DatabaseManager:
    def __init__(self, db_path="data/db/attendance.db"):
        self.db_path = db_path
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create Students Table
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

        # Create Attendance Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                timestamp DATETIME,
                status TEXT,
                FOREIGN KEY(student_id) REFERENCES students(id)
            )
        """
        )
        conn.commit()
        conn.close()

    def add_student(self, name, roll_number, encoding_path):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO students (name, roll_number, encoding_file_path) VALUES (?, ?, ?)",
                (name, roll_number, encoding_path),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Roll number exists
        finally:
            conn.close()

    def get_all_students(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, roll_number, encoding_file_path FROM students")
        rows = cursor.fetchall()
        conn.close()
        return [
            Student(id=r[0], name=r[1], roll_number=r[2], encoding_path=r[3])
            for r in rows
        ]

    def mark_attendance(self, student_id, status="PRESENT"):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Debounce: Check if attended in the last minute
        cursor.execute(
            """
            SELECT id FROM attendance 
            WHERE student_id = ? AND timestamp > datetime('now', '-1 minute')
        """,
            (student_id,),
        )

        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO attendance (student_id, timestamp, status) VALUES (?, datetime('now'), ?)",
                (student_id, status),
            )
            conn.commit()
            print(f"Attendance marked for ID: {student_id}")

        conn.close()
