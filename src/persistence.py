import sqlite3
import os
import hashlib
from datetime import datetime
from src.models.entities import Student, Group, TimetableSlot


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
                teacher_id INTEGER,
                course_id INTEGER,
                group_id INTEGER,
                day_of_week INTEGER,
                start_time TEXT, 
                end_time TEXT,
                FOREIGN KEY(teacher_id) REFERENCES users(id),
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
        admin_pass = self._hash_password("admin")
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
        
        try:
            # 1. Delete the group
            cursor.execute("DELETE FROM student_groups WHERE id=?", (group_id,))
            
            # 2. Also delete related links in the teacher_groups table
            cursor.execute("DELETE FROM teacher_groups WHERE group_id=?", (group_id,))
            
            cursor.execute("""
                UPDATE sqlite_sequence 
                SET seq = COALESCE((SELECT MAX(id) FROM student_groups), 0) 
                WHERE name = 'student_groups'
            """)
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting group: {e}")
            return False
        finally:
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

    # Update this method to accept teacher_id
    def add_timetable_slot_direct(self, teacher_id, group_id, day, start, end):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # We now insert teacher_id. 
            # We can leave course_id as 0 if you don't have a specific course name.
            cursor.execute(
                """
                INSERT INTO timetable (teacher_id, group_id, day_of_week, start_time, end_time, course_id) 
                VALUES (?, ?, ?, ?, ?, 0)
            """,
                (teacher_id, group_id, day, start, end),
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding slot: {e}")
            return False
        finally:
            conn.close()

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
        now = datetime.now()
        day = now.weekday()  # 0=Mon
        current_time = now.strftime("%H:%M")

        print(f"Checking schedule for Teacher {teacher_id} at {current_time}, day {day}")

        query = """
            SELECT 
                t.id, 
                t.course_id,
                t.start_time, 
                t.end_time, 
                g.id as group_id, 
                g.name as group_name
            FROM timetable t
            JOIN student_groups g ON t.group_id = g.id
            WHERE t.teacher_id = ? 
            AND t.day_of_week = ? 
            AND ? BETWEEN t.start_time AND t.end_time
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(query, (teacher_id, day, current_time))
        row = cursor.fetchone()
        conn.close()

        if row:
            print(f"Found active session: {row['group_name']}")
            return dict(row)
        
        print("No active session found.")
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
        Returns: { student_id: {'status': 'PRESENT', 'time': 'HH:MM:SS'} }
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Query now fetches timestamp as well
        query = """
            SELECT student_id, status, timestamp 
            FROM attendance 
            WHERE group_id=? AND timestamp LIKE ?
        """
        
        # Add wildcard for the LIKE clause
        search_pattern = f"{date_str}%"
        cursor.execute(query, (group_id, search_pattern))
        rows = cursor.fetchall()
        conn.close()

        # Build a richer dictionary
        att_data = {}
        for r in rows:
            # r[2] is the timestamp string (e.g., "2023-10-25 09:30:05")
            # We just want the time part (split by space, take second part)
            time_part = ""
            if r[2] and " " in r[2]:
                time_part = r[2].split(" ")[1] 
            
            att_data[r[0]] = {
                "status": r[1],
                "time": time_part
            }
            
        return att_data
    
    def save_manual_attendance(self, group_id, date_str, att_map):
        """
        Saves attendance manually.
        att_map format: { student_id: {'status': 'PRESENT', 'time': 'HH:MM:SS'} }
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            for student_id, data in att_map.items():
                status = data['status']
                time_val = data['time']

                # Construct the full timestamp
                if time_val:
                    # If we have a specific time, combine it with the date
                    full_timestamp = f"{date_str} {time_val}"
                else:
                    # If no time (e.g. absent/manual), just use mid-day or start of day
                    # formatting it allows the 'LIKE' query to still find it later
                    full_timestamp = f"{date_str} 00:00:00"

                # UPSERT: Insert or Replace if exists
                # We assume (student_id, group_id, date(timestamp)) logic is handled 
                # OR we just check if a record exists for this day and update it.
                
                # 1. Delete existing record for this student on this day to avoid duplicates
                # (Simple way to handle updates without complex SQL logic)
                delete_query = """
                    DELETE FROM attendance 
                    WHERE student_id = ? 
                    AND group_id = ? 
                    AND timestamp LIKE ?
                """
                cursor.execute(delete_query, (student_id, group_id, f"{date_str}%"))

                # 2. Insert new record
                insert_query = """
                    INSERT INTO attendance (student_id, group_id, timestamp, status, course_id)
                    VALUES (?, ?, ?, ?, 0)
                """
                cursor.execute(insert_query, (student_id, group_id, full_timestamp, status))

            conn.commit()
            return True
        except Exception as e:
            print(f"Error saving manual attendance: {e}")
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

    # ==========================================
    # TEACHER - GROUP ASSIGNMENT (New Feature)
    # ==========================================
    def init_teacher_group_link(self):
        """Creates the linking table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teacher_groups (
                teacher_id INTEGER,
                group_id INTEGER,
                PRIMARY KEY (teacher_id, group_id)
            )
        """)
        conn.commit()
        conn.close()

    def assign_teacher_to_group(self, teacher_id, group_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR IGNORE INTO teacher_groups (teacher_id, group_id) VALUES (?, ?)", 
                           (teacher_id, group_id))
            conn.commit()
            return True
        except Exception as e:
            print(e)
            return False
        finally:
            conn.close()

    def remove_teacher_from_group(self, teacher_id, group_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM teacher_groups WHERE teacher_id=? AND group_id=?", 
                       (teacher_id, group_id))
        conn.commit()
        conn.close()

    def get_groups_for_teacher(self, teacher_id):
        """Returns only the groups assigned to this teacher."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = """
            SELECT g.id, g.name 
            FROM student_groups g
            JOIN teacher_groups tg ON g.id = tg.group_id
            WHERE tg.teacher_id = ?
        """
        cursor.execute(query, (teacher_id,))
        rows = cursor.fetchall()
        conn.close()
        # Return as simple objects or dicts
        return [dict(row) for row in rows]