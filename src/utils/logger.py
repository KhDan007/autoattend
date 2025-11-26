"""
Logger for AutoAttend Application
Provides logging functionality for debugging and monitoring
"""
import logging
import os
from datetime import datetime
from enum import Enum


class LogLevel(Enum):
    """Log level enumeration"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class Logger:
    """Application logger with file and console output"""
    
    def __init__(self, log_file: str = None, log_level: LogLevel = LogLevel.INFO):
        """Initialize logger"""
        self.log_level = log_level
        
        if log_file is None:
            os.makedirs("logs", exist_ok=True)
            log_file = f"logs/autoattend_{datetime.now().strftime('%Y%m%d')}.log"
        
        self.log_file = log_file
        
        self.logger = logging.getLogger("AutoAttend")
        self.logger.setLevel(log_level.value)
        self.logger.handlers.clear()
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level.value)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level.value)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def log_info(self, message: str):
        """Log info message"""
        self.logger.info(message)
    
    def log_error(self, message: str):
        """Log error message"""
        self.logger.error(message)
    
    def log_warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)
    
    def log_debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)
    
    def log_critical(self, message: str):
        """Log critical message"""
        self.logger.critical(message)
