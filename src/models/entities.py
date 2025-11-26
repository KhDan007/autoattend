from dataclasses import dataclass
from datetime import datetime

@dataclass
class Student:
    id: int
    name: str
    roll_number: str
    encoding_path: str

@dataclass
class AttendanceRecord:
    student_id: int
    course_id: str
    timestamp: datetime
    status: str