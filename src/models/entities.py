from dataclasses import dataclass
from datetime import datetime

@dataclass
class Course:
    id: int
    code: str
    name: str

@dataclass
class Student:
    id: int
    name: str
    roll_number: str
    encoding_path: str

@dataclass
class AttendanceRecord:
    id: int
    student_id: int
    course_id: int
    timestamp: datetime
    status: str
    student_name: str = "" # Helper for UI Display