import sqlite3
import os
import hashlib
from datetime import datetime
from src.models.entities import Student, Course, Group, TimetableSlot


class DatabaseManager:
    def __init__(self, db_path="data/db/attendance.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 1. Users (Teachers/Admins)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                is_admin INTEGER DEFAULT 0
            )
        """
        )

        # 2. Student Groups (NEW: e.g. "CS-SL-26-1")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS student_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """
        )

        # 3. Students (Updated: Linked to Group)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                roll_number TEXT UNIQUE NOT NULL,
                encoding_file_path TEXT,
                group_id INTEGER,
                FOREIGN KEY(group_id) REFERENCES student_groups(id)
            )
        """
        )

        # 4. Courses
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                teacher_id INTEGER,
                FOREIGN KEY(teacher_id) REFERENCES users(id)
            )
        """
        )

        # 5. Timetable (Updated: Links Course + Group + Time)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS timetable (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER,
                group_id INTEGER,
                day_of_week INTEGER,
                start_time TEXT, 
                end_time TEXT,
                FOREIGN KEY(course_id) REFERENCES courses(id),
                FOREIGN KEY(group_id) REFERENCES student_groups(id)
            )
        """
        )

        # 6. Attendance
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                course_id INTEGER,
                group_id INTEGER, 
                timestamp DATETIME,
                status TEXT,
                FOREIGN KEY(student_id) REFERENCES students(id),
                FOREIGN KEY(course_id) REFERENCES courses(id),
                FOREIGN KEY(group_id) REFERENCES student_groups(id)
            )
        """
        )

        # Create Default Admin
        admin_user = "admin"
        admin_pass = self._hash_password("Qqwerty123!")
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash, full_name, is_admin) VALUES (?, ?, ?, ?)",
                (admin_user, admin_pass, "System Administrator", 1),
            )
        except sqlite3.IntegrityError:
            pass

        # Create a Default Group so system isn't empty
        try:
            cursor.execute(
                "INSERT INTO student_groups (name) VALUES (?)", ("CS-SL-26-1",)
            )
        except:
            pass

        conn.commit()
        conn.close()

    # --- Authentication ---
    def _hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def register_user(self, username, password, full_name):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash, full_name, is_admin) VALUES (?, ?, ?, 0)",
                (username, self._hash_password(password), full_name),
            )
            conn.commit()
            return True, "Success"
        except:
            return False, "Username taken"
        finally:
            conn.close()

    def login_user(self, username, password):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, full_name, is_admin FROM users WHERE username=? AND password_hash=?",
            (username, self._hash_password(password)),
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return True, {
                "id": row[0],
                "username": row[1],
                "full_name": row[2],
                "is_admin": row[3],
            }
        return False, None

    # --- GROUP MANAGEMENT ---
    def add_group(self, name):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO student_groups (name) VALUES (?)", (name,))
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()

    def get_all_groups(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM student_groups ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        return [Group(id=r[0], name=r[1]) for r in rows]

    def delete_group(self, group_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Delete group, its students, and its timetable slots
        cursor.execute("DELETE FROM student_groups WHERE id=?", (group_id,))
        cursor.execute("DELETE FROM students WHERE group_id=?", (group_id,))
        cursor.execute("DELETE FROM timetable WHERE group_id=?", (group_id,))
        conn.commit()
        conn.close()

    # --- STUDENT MANAGEMENT ---
    def generate_next_roll_number(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT MAX(CAST(roll_number AS INTEGER)) FROM students")
            row = cursor.fetchone()
            max_id = row[0] if row[0] is not None else 0
            return str(max_id + 1)
        except:
            return "1001"
        finally:
            conn.close()

    def add_student(self, name, roll, group_id, path=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO students (name, roll_number, group_id, encoding_file_path) VALUES (?, ?, ?, ?)",
                (name, roll, group_id, path),
            )
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()

    def get_all_students(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT s.id, s.name, s.roll_number, s.encoding_file_path, s.group_id, g.name 
            FROM students s 
            LEFT JOIN student_groups g ON s.group_id = g.id
        """
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            Student(
                id=r[0],
                name=r[1],
                roll_number=r[2],
                encoding_path=r[3],
                group_id=r[4],
                group_name=r[5],
            )
            for r in rows
        ]

    def delete_student(self, student_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM students WHERE id=?", (student_id,))
        cursor.execute("DELETE FROM attendance WHERE student_id=?", (student_id,))
        conn.commit()
        conn.close()

    def update_student_face(self, student_id, path):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE students SET encoding_file_path=? WHERE id=?", (path, student_id)
        )
        conn.commit()
        conn.close()

    # --- ACADEMIC MANAGEMENT (Courses & Timetable) ---
    def get_all_teachers(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, full_name FROM users WHERE is_admin=0")
        return [
            {"id": r[0], "username": r[1], "full_name": r[2]} for r in cursor.fetchall()
        ]

    def get_groups_for_teacher(self, teacher_id):
        return self.get_all_groups()

    def get_timetable_for_teacher_and_group(self, teacher_id, group_id):
        query = """
            SELECT * FROM timetable 
            WHERE group_id = ? 
            ORDER BY day_of_week, start_time
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = (
            sqlite3.Row
        )  # This ensures we can access columns by name later
        cursor = conn.cursor()
        try:
            cursor.execute(query, (group_id,))
            rows = cursor.fetchall()
            # Convert rows to a list of dictionaries so the UI can use them easily
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"Timetable Fetch Error: {e}")
            return []
        finally:
            conn.close()

    def add_timetable_slot_direct(self, group_id, day, start, end):
        # We insert '0' or NULL for course_id since we aren't using it.
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO timetable (day_of_week, start_time, end_time, group_id, course_id) 
                VALUES (?, ?, ?, ?, 0)
            """,
                (day, start, end, group_id),
            )
            conn.commit()
            return True
        except Exception as e:
            print(e)
            return False
        finally:
            conn.close()

    def get_active_session_info(self, teacher_id):
        # Simplified: Just find a slot matching current time and group
        # NOTE: This assumes the 'timetable' table logic links groups to time.
        # Since we removed "Course", we just check if ANY group has a slot now.
        now = datetime.now()
        day = now.weekday()  # 0=Mon
        current_time = now.strftime("%H:%M")

        # We need to find which group corresponds to the logged-in teacher?
        # If the database doesn't link Teacher->Timetable directly,
        # this function might need to return ANY active group slot
        # or rely on a specific link.
        # For this fix, we will assume we just want the active group slot.

        query = """
            SELECT t.id, t.start_time, t.end_time, g.id as group_id, g.name as group_name
            FROM timetable t
            JOIN groups g ON t.group_id = g.id
            WHERE t.day_of_week = ? 
            AND ? BETWEEN t.start_time AND t.end_time
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, (day, current_time))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def add_course(self, name, teacher_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO courses (name, teacher_id) VALUES (?, ?)", (name, teacher_id)
        )
        conn.commit()
        conn.close()

    def get_courses_for_teacher(self, teacher_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, teacher_id FROM courses WHERE teacher_id=?", (teacher_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [Course(id=r[0], name=r[1], teacher_id=r[2]) for r in rows]

    def delete_course(self, course_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM courses WHERE id=?", (course_id,))
        cursor.execute("DELETE FROM timetable WHERE course_id=?", (course_id,))
        conn.commit()
        conn.close()

    # --- TIMETABLE (UPDATED) ---
    def add_timetable_slot(self, course_id, group_id, day, start, end):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO timetable (course_id, group_id, day_of_week, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
            (course_id, group_id, day, start, end),
        )
        conn.commit()
        conn.close()

    def get_timetable_for_course(self, course_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Join with Groups to get group name
        cursor.execute(
            """
            SELECT t.id, t.course_id, t.group_id, t.day_of_week, t.start_time, t.end_time, g.name
            FROM timetable t
            JOIN student_groups g ON t.group_id = g.id
            WHERE t.course_id=? 
            ORDER BY t.day_of_week, t.start_time
        """,
            (course_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            TimetableSlot(
                id=r[0],
                course_id=r[1],
                group_id=r[2],
                day_of_week=r[3],
                start_time=r[4],
                end_time=r[5],
                group_name=r[6],
            )
            for r in rows
        ]

    def delete_timetable_slot(self, slot_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM timetable WHERE id=?", (slot_id,))
        conn.commit()
        conn.close()

    # --- TEACHER / SESSION LOGIC ---
    def get_active_session_info(self, teacher_id):
        """Returns the specific Course AND Group for right now."""
        now = datetime.now()
        current_day = now.weekday()
        current_time = now.strftime("%H:%M")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT c.id, c.name, t.group_id, g.name
            FROM timetable t
            JOIN courses c ON t.course_id = c.id
            JOIN student_groups g ON t.group_id = g.id
            WHERE c.teacher_id = ?
              AND t.day_of_week = ?
              AND ? BETWEEN t.start_time AND t.end_time
            LIMIT 1
        """
        cursor.execute(query, (teacher_id, current_day, current_time))
        row = cursor.fetchone()
        conn.close()

        if row:
            # Return dict with course info AND group info
            return {
                "course_id": row[0],
                "course_name": row[1],
                "group_id": row[2],
                "group_name": row[3],
            }
        return None

    def get_students_by_group(self, group_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, roll_number, encoding_file_path FROM students WHERE group_id=?",
            (group_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            Student(
                id=r[0],
                name=r[1],
                roll_number=r[2],
                encoding_path=r[3],
                group_id=group_id,
            )
            for r in rows
        ]

    def mark_attendance(self, student_id, course_id, group_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id FROM attendance 
            WHERE student_id=? AND course_id=? AND date(timestamp)=date('now')
        """,
            (student_id, course_id),
        )

        if not cursor.fetchone():
            cursor.execute(
                """
                INSERT INTO attendance (student_id, course_id, group_id, timestamp, status) 
                VALUES (?, ?, ?, datetime('now','localtime'), 'PRESENT')
            """,
                (student_id, course_id, group_id),
            )
            conn.commit()
            conn.close()
            return True
        conn.close()
        return False

    def get_todays_attendance(self, course_id, group_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT student_id, status FROM attendance 
            WHERE course_id=? AND group_id=? AND date(timestamp)=date('now')
        """,
            (course_id, group_id),
        )
        return {r[0]: r[1] for r in cursor.fetchall()}

    def move_student_to_group(self, student_id, new_group_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE students SET group_id=? WHERE id=?", (new_group_id, student_id)
            )
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()

    def copy_student_to_group(self, student_id, new_group_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM students WHERE id=?", (student_id,))
            row = cursor.fetchone()
            if not row:
                return False

            data = dict(row)
            del data["id"]
            data["group_id"] = new_group_id

            # --- FIX: MODIFY ROLL NUMBER TO BE UNIQUE ---
            # Append a suffix (e.g., if ID is "123", try "123_copy")
            # Or use a timestamp to ensure uniqueness
            original_roll = str(data["roll_number"])
            data["roll_number"] = f"{original_roll}_{new_group_id}"
            # --------------------------------------------

            columns = ", ".join(data.keys())
            placeholders = ", ".join("?" * len(data))
            sql = f"INSERT INTO students ({columns}) VALUES ({placeholders})"

            cursor.execute(sql, list(data.values()))
            conn.commit()
            return True

        except Exception as e:
            print(f"Copy Error: {e}")
            return False
        finally:
            conn.close()

    # ... inside DatabaseManager class ...

    def get_session_attendance(self, group_id, date_str):
        """
        Fetch attendance for a specific group on a specific date.
        date_str format: "YYYY-MM-DD"
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # We look for records matching the date portion of the timestamp
        query = """
            SELECT student_id, status 
            FROM attendance 
            WHERE group_id=? AND date(timestamp) = ?
        """

        cursor.execute(query, (group_id, date_str))
        rows = cursor.fetchall()
        conn.close()

        # Return a dictionary: {student_id: "PRESENT" (or ABSENT)}
        return {row[0]: row[1] for row in rows}

    def save_manual_attendance(self, group_id, date_str, attendance_map):
        """
        Saves or updates attendance manually.
        attendance_map: dict {student_id: "PRESENT" or "ABSENT"}
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # We treat '0' as course_id for manual edits if course context is loose
            course_id = 0

            # Timestamp for the specific date (set to noon)
            manual_ts = f"{date_str} 12:00:00"

            for student_id, status in attendance_map.items():
                # 1. Check if record exists for this date
                cursor.execute(
                    """
                    SELECT id FROM attendance 
                    WHERE student_id=? AND group_id=? AND date(timestamp)=?
                """,
                    (student_id, group_id, date_str),
                )

                row = cursor.fetchone()

                if row:
                    # Update existing record's status
                    cursor.execute(
                        "UPDATE attendance SET status=? WHERE id=?", (status, row[0])
                    )
                else:
                    # Insert new record
                    cursor.execute(
                        """
                        INSERT INTO attendance (student_id, course_id, group_id, timestamp, status)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (student_id, course_id, group_id, manual_ts, status),
                    )

            conn.commit()
            return True
        except Exception as e:
            print(f"Manual Save Error: {e}")
            return False
        finally:
            conn.close()

    def toggle_attendance_status(self, student_id, group_id):
        """
        Toggles status between PRESENT and ABSENT for TODAY.
        Used for the Live View manual override.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")

        # Find the record
        cursor.execute(
            """
            SELECT id, status FROM attendance 
            WHERE student_id=? AND group_id=? AND date(timestamp)=?
        """,
            (student_id, group_id, today),
        )

        row = cursor.fetchone()
        new_status = "PRESENT"

        if row:
            # Toggle
            current_status = row[1]
            new_status = "ABSENT" if current_status == "PRESENT" else "PRESENT"
            cursor.execute(
                "UPDATE attendance SET status=? WHERE id=?", (new_status, row[0])
            )
        else:
            # If no record exists yet, we create one as ABSENT (unusual, but safe) or PRESENT
            # Usually this method is called on a row that appears in the UI
            cursor.execute(
                """
                INSERT INTO attendance (student_id, course_id, group_id, timestamp, status)
                VALUES (?, 0, ?, datetime('now','localtime'), 'PRESENT')
            """,
                (student_id, group_id),
            )
            new_status = "PRESENT"

        conn.commit()
        conn.close()
        return new_status
