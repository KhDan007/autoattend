from dataclasses import dataclass
from typing import Optional

@dataclass
class Group:
    id: int
    name: str  # e.g., "CS-SL-26-1"

@dataclass
class Student:
    id: int
    name: str
    roll_number: str
    encoding_path: Optional[str]
    group_id: int
    group_name: str = "" # Helper for display

@dataclass
class Course:
    id: int
    name: str
    teacher_id: int

@dataclass
class TimetableSlot:
    id: int
    course_id: int
    group_id: int
    day_of_week: int
    start_time: str
    end_time: str
    group_name: str = ""  # Helper
    course_name: str = "" # Helper