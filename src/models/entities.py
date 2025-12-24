from dataclasses import dataclass

@dataclass
class Student:
    id: int
    name: str
    roll_number: str
    encoding_path: str

@dataclass
class Course:
    id: int
    name: str
    teacher_id: int

@dataclass
class TimetableSlot:
    id: int
    course_id: int
    day_of_week: int # 0=Monday, 6=Sunday
    start_time: str  # Format "HH:MM"
    end_time: str    # Format "HH:MM"