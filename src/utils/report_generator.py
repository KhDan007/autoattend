import csv
import os
from datetime import datetime
from src.persistence import DatabaseManager


class ReportGenerator:
    def __init__(self, db_manager: DatabaseManager, output_dir="data/reports"):
        self.db = db_manager
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def export_daily_report(self):
        """Generates a CSV report for today's attendance"""
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"attendance_report_{today}.csv"
        filepath = os.path.join(self.output_dir, filename)

        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()

        # Join Students and Attendance tables to get readable names
        query = """
            SELECT s.roll_number, s.name, a.timestamp, a.status
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE date(a.timestamp) = date('now')
        """

        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return None, "No attendance records found for today."

        try:
            with open(filepath, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                # Write Header
                writer.writerow(["Roll Number", "Name", "Time", "Status"])
                # Write Data
                writer.writerows(rows)
            return filepath, f"Report saved: {filepath}"
        except Exception as e:
            return None, str(e)


# We need sqlite3 for the query inside the helper
import sqlite3
