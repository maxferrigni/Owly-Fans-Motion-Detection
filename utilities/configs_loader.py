# File: utilities/configs_loader.py
# Purpose: Load and validate configuration files for the Owl Monitoring System

import json
import os
import pandas as pd
from datetime import datetime
import threading
from utilities.logging_utils import get_logger
from utilities.constants import CONFIGS_DIR

# Initialize logger
logger = get_logger()

# Lock for thread-safe config updates
config_lock = threading.Lock()

class ConfigurationManager:
    def __init__(self):
        self.config_path = os.path.join(CONFIGS_DIR, "config.json")
        self.backup_path = os.path.join(CONFIGS_DIR, "config.backup.json")
        self.config = {}
        self.original_values = {}
        self.load_config()

    def load_config(self):
        """Load and validate the camera configuration"""
        try:
            if not os.path.exists(self.config_path):
                error_msg = f"Config file not found: {self.config_path}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)

            with config_lock:
                with open(self.config_path, "r") as file:
                    self.config = json.load(file)
                    
                # Store original values
                self.original_values = json.loads(json.dumps(self.config))
                    
                # Validate required fields
                self._validate_config(self.config)
                
            logger.info("Camera configuration loaded successfully")
            return self.config

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in config file: {e}"
            logger.error(error_msg)
            raise
        except Exception as e:
            logger.error(f"Error loading camera config: {e}")
            raise

    def _validate_config(self, config):
        """Validate configuration structure and values"""
        required_fields = ["roi", "threshold_percentage", "luminance_threshold", "alert_type"]
        required_motion_fields = [
            "min_circularity", "min_aspect_ratio", 
            "max_aspect_ratio", "min_area_ratio",
            "brightness_threshold"
        ]
        
        for camera, settings in config.items():
            # Check main fields
            missing_fields = [field for field in required_fields if field not in settings]
            if missing_fields:
                raise ValueError(f"Missing required fields {missing_fields} for camera {camera}")
                
            # Check motion detection fields
            if "motion_detection" not in settings:
                raise ValueError(f"Missing motion_detection settings for camera {camera}")
                
            motion_settings = settings["motion_detection"]
            missing_motion_fields = [
                field for field in required_motion_fields 
                if field not in motion_settings
            ]
            if missing_motion_fields:
                raise ValueError(
                    f"Missing motion detection fields {missing_motion_fields} "
                    f"for camera {camera}"
                )

    def create_backup(self):
        """Create a backup of current configuration"""
        try:
            with config_lock:
                with open(self.backup_path, 'w') as f:
                    json.dump(self.config, f, indent=4)
            logger.info("Configuration backup created")
        except Exception as e:
            logger.error(f"Error creating config backup: {e}")
            raise

    def restore_backup(self):
        """Restore configuration from backup"""
        try:
            if not os.path.exists(self.backup_path):
                raise FileNotFoundError("No backup file found")
                
            with config_lock:
                with open(self.backup_path, 'r') as f:
                    self.config = json.load(f)
                self.save_config()
            logger.info("Configuration restored from backup")
        except Exception as e:
            logger.error(f"Error restoring config backup: {e}")
            raise

    def update_camera_setting(self, camera, param_path, value):
        """
        Update a specific camera parameter.
        
        Args:
            camera (str): Camera name
            param_path (str): Parameter path (e.g., "threshold_percentage" or "motion_detection.min_circularity")
            value: New value
        """
        try:
            with config_lock:
                # Create backup before modification
                self.create_backup()
                
                # Handle nested parameters
                if '.' in param_path:
                    category, param = param_path.split('.')
                    if category not in self.config[camera]:
                        self.config[camera][category] = {}
                    self.config[camera][category][param] = value
                else:
                    self.config[camera][param_path] = value
                
                # Validate new configuration
                self._validate_config(self.config)
                
                # Save changes
                self.save_config()
                
            logger.info(f"Updated {param_path} for {camera}: {value}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating camera setting: {e}")
            self.restore_backup()
            raise

    def reset_camera_settings(self, camera):
        """Reset camera settings to original values"""
        try:
            if camera not in self.original_values:
                raise ValueError(f"No original values found for camera: {camera}")
                
            with config_lock:
                self.create_backup()
                self.config[camera] = json.loads(
                    json.dumps(self.original_values[camera])
                )
                self.save_config()
                
            logger.info(f"Reset settings for camera: {camera}")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting camera settings: {e}")
            raise

    def save_config(self):
        """Save current configuration to file"""
        try:
            with config_lock:
                with open(self.config_path, 'w') as f:
                    json.dump(self.config, f, indent=4)
            logger.info("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            raise

    def get_camera_settings(self, camera):
        """Get all settings for a specific camera"""
        try:
            if camera not in self.config:
                raise ValueError(f"Camera not found: {camera}")
            return json.loads(json.dumps(self.config[camera]))
        except Exception as e:
            logger.error(f"Error getting camera settings: {e}")
            raise

    def validate_and_update_settings(self, camera, settings):
        """Validate and update multiple settings for a camera"""
        try:
            # Create a copy of config for validation
            test_config = json.loads(json.dumps(self.config))
            test_config[camera].update(settings)
            
            # Validate new configuration
            self._validate_config(test_config)
            
            # If validation passes, update actual config
            with config_lock:
                self.create_backup()
                self.config[camera].update(settings)
                self.save_config()
                
            logger.info(f"Updated multiple settings for camera: {camera}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating multiple settings: {e}")
            self.restore_backup()
            raise

def load_sunrise_sunset_data():
    """Load and parse the sunrise/sunset data"""
    try:
        sunrise_sunset_path = os.path.join(CONFIGS_DIR, "LA_Sunrise_Sunset.txt")

        if not os.path.exists(sunrise_sunset_path):
            error_msg = f"Sunrise/Sunset data file not found: {sunrise_sunset_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        # Read the file with tabs as delimiter
        df = pd.read_csv(sunrise_sunset_path, delimiter="\t")
        
        # Validate required columns
        required_columns = ['Date', 'Sunrise', 'Sunset']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            error_msg = f"Missing required columns in sunrise/sunset data: {missing_columns}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Convert Date column to datetime
        df['Date'] = pd.to_datetime(df['Date'])
        
        # Ensure Sunrise and Sunset are strings in HH:MM format
        df['Sunrise'] = df['Sunrise'].astype(str).str.pad(4, fillchar='0').apply(
            lambda x: f"{x[:2]}:{x[2:]}"
        )
        df['Sunset'] = df['Sunset'].astype(str).str.pad(4, fillchar='0').apply(
            lambda x: f"{x[:2]}:{x[2:]}"
        )
        
        logger.info("Sunrise/Sunset data loaded successfully")
        logger.debug(f"Loaded {len(df)} days of sunrise/sunset data")
        
        return df

    except pd.errors.EmptyDataError:
        error_msg = "Sunrise/Sunset file is empty"
        logger.error(error_msg)
        raise
    except Exception as e:
        logger.error(f"Error loading sunrise/sunset data: {e}")
        raise

def validate_config_files():
    """Validate all configuration files exist and are readable"""
    try:
        # Create configuration manager
        config_manager = ConfigurationManager()
        
        # Load and validate camera config
        config_manager.load_config()
        
        # Load and validate sunrise/sunset data
        sunrise_sunset_data = load_sunrise_sunset_data()
        
        logger.info("All configuration files validated successfully")
        return True
        
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        return False

# Create global configuration manager instance
config_manager = ConfigurationManager()

if __name__ == "__main__":
    try:
        logger.info("Testing configuration loading...")
        validate_config_files()
        logger.info("Configuration test complete")
    except Exception as e:
        logger.error(f"Configuration test failed: {e}")