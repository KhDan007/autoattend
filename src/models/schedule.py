"""
Schedule Model for Course Timing
"""
from datetime import time, timedelta, datetime
from typing import Optional


class Schedule:
    """Represents a class schedule with timing information"""
    
    def __init__(
        self,
        day_of_week: str,
        start_time: time,
        end_time: time,
        schedule_id: Optional[str] = None
    ):
        """Initialize schedule"""
        self.schedule_id = schedule_id
        self.day_of_week = day_of_week
        self.start_time = start_time
        self.end_time = end_time
    
    def is_class_time(self, check_time: Optional[datetime] = None) -> bool:
        """Check if given time is within class hours"""
        if check_time is None:
            check_time = datetime.now()
        
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if days[check_time.weekday()] != self.day_of_week:
            return False
        
        current_time = check_time.time()
        return self.start_time <= current_time <= self.end_time
    
    def get_duration(self) -> timedelta:
        """Calculate class duration"""
        today = datetime.today()
        start_dt = datetime.combine(today, self.start_time)
        end_dt = datetime.combine(today, self.end_time)
        
        return end_dt - start_dt
    
    def __str__(self):
        return f"{self.day_of_week} {self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"
