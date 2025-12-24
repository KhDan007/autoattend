from dataclasses import dataclass
from datetime import datetime

@dataclass
class Student:
    id: int
    name: str
    roll_number: str
    encoding_path: str

@dataclass
class Course:
    id: int
    code: str
    name: str
    teacher_id: int  # New: Links course to a specific teacher

@dataclass
class TimetableSlot:
    id: int
    course_id: int
    day_of_week: int # 0=Monday, 6=Sunday
    start_time: str  # Format "HH:MM" (24hr)
    end_time: str    # Format "HH:MM" (24hr)