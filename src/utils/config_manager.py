"""
Configuration Manager for AutoAttend Application
Handles loading and saving application settings
"""
import json
import os
from typing import Any, Dict


class ConfigurationManager:
    """Manages application configuration settings"""
    
    def __init__(self, config_file: str = "config.json"):
        """
        Initialize configuration manager
        
        Args:
            config_file: Path to configuration file
        """
        self.config_file = config_file
        self.settings = self._load_default_config()
        self.load_config()
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default configuration settings"""
        return {
            "camera": {
                "resolution": [640, 480],
                "fps": 30,
                "device_id": 0
            },
            "recognition": {
                "tolerance": 0.6,
                "model": "hog",
                "num_jitters": 1
            },
            "database": {
                "path": "data/autoattend.db"
            },
            "ui": {
                "window_title": "AutoAttend - Face Recognition Attendance System",
                "theme": "default"
            },
            "session": {
                "auto_save_interval": 300,
                "late_threshold": 600
            },
            "reports": {
                "output_dir": "reports",
                "default_format": "csv"
            }
        }
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    self.settings.update(loaded_config)
            except Exception as e:
                print(f"Error loading config: {e}. Using defaults.")
        else:
            self.save_config(self.settings)
        
        return self.settings
    
    def save_config(self, settings: Dict[str, Any]) -> bool:
        """Save configuration to file"""
        try:
            self.settings = settings
            with open(self.config_file, 'w') as f:
                json.dump(settings, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a specific setting value"""
        keys = key.split('.')
        value = self.settings
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
