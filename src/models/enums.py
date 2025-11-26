"""
Enumerations for AutoAttend Application
"""
from enum import Enum


class AttendanceStatus(Enum):
    """Attendance status enumeration"""
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"
    
    def __str__(self):
        return self.value
