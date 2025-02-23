# File: utilities/configs_loader.py
# Purpose: Load and validate configuration files for the Owl Monitoring System

import json
import os
import pandas as pd
from copy import deepcopy
from datetime import datetime
import shutil
from utilities.logging_utils import get_logger
from utilities.constants import CONFIGS_DIR

# Initialize logger
logger = get_logger()

class ConfigManager:
    def __init__(self):
        self.config_path = os.path.join(CONFIGS_DIR, "config.json")
        self.backup_dir = os.path.join(CONFIGS_DIR, "backups")
        self.original_config = None
        self.current_config = None
        
        # Ensure backup directory exists
        os.makedirs(self.backup_dir, exist_ok=True)
        
    def load_config(self):
        """Load and validate the camera configuration"""
        try:
            if not os.path.exists(self.config_path):
                error_msg = f"Config file not found: {self.config_path}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)

            with open(self.config_path, "r") as file:
                config = json.load(file)
                
            # Store original configuration
            self.original_config = deepcopy(config)
            self.current_config = deepcopy(config)
            
            # Validate configuration
            self._validate_config(config)
            
            logger.info("Camera configuration loaded successfully")
            return config

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
            "min_circularity", "min_aspect_ratio", "max_aspect_ratio",
            "min_area_ratio", "brightness_threshold"
        ]
        
        for camera, settings in config.items():
            # Check main required fields
            missing_fields = [field for field in required_fields if field not in settings]
            if missing_fields:
                raise ValueError(f"Missing required fields {missing_fields} for camera {camera}")
                
            # Check motion detection parameters
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
                
            # Validate value ranges
            self._validate_value_ranges(camera, settings)
            
    def _validate_value_ranges(self, camera, settings):
        """Validate configuration value ranges"""
        # Validate threshold percentage
        if not 0 < settings["threshold_percentage"] <= 1:
            raise ValueError(
                f"Invalid threshold_percentage for {camera}: "
                f"must be between 0 and 1"
            )
            
        # Validate luminance threshold
        if not 0 <= settings["luminance_threshold"] <= 255:
            raise ValueError(
                f"Invalid luminance_threshold for {camera}: "
                f"must be between 0 and 255"
            )
            
        # Validate motion detection parameters
        motion = settings["motion_detection"]
        if not 0 < motion["min_circularity"] <= 1:
            raise ValueError(
                f"Invalid min_circularity for {camera}: "
                f"must be between 0 and 1"
            )
            
        if not motion["min_aspect_ratio"] < motion["max_aspect_ratio"]:
            raise ValueError(
                f"Invalid aspect ratio range for {camera}: "
                f"min must be less than max"
            )
            
        if not 0 < motion["min_area_ratio"] <= 1:
            raise ValueError(
                f"Invalid min_area_ratio for {camera}: "
                f"must be between 0 and 1"
            )
            
    def create_backup(self):
        """Create a backup of the current config file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(
                self.backup_dir,
                f"config_backup_{timestamp}.json"
            )
            
            shutil.copy2(self.config_path, backup_path)
            logger.info(f"Created config backup: {backup_path}")
            
            # Clean old backups (keep last 5)
            self._cleanup_old_backups()
            
            return backup_path
            
        except Exception as e:
            logger.error(f"Error creating config backup: {e}")
            raise
            
    def _cleanup_old_backups(self):
        """Keep only the 5 most recent backups"""
        try:
            backups = sorted([
                f for f in os.listdir(self.backup_dir)
                if f.startswith("config_backup_")
            ])
            
            # Remove old backups
            while len(backups) > 5:
                old_backup = os.path.join(self.backup_dir, backups.pop(0))
                os.remove(old_backup)
                logger.debug(f"Removed old backup: {old_backup}")
                
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
            
    def update_camera_settings(self, camera, settings):
        """
        Update settings for a specific camera.
        
        Args:
            camera (str): Camera name
            settings (dict): New settings to apply
        """
        try:
            if camera not in self.current_config:
                raise ValueError(f"Unknown camera: {camera}")
                
            # Create backup before changes
            self.create_backup()
            
            # Update configuration
            self.current_config[camera].update(settings)
            
            # Validate new configuration
            self._validate_config(self.current_config)
            
            # Save changes
            self.save_config()
            
            logger.info(f"Updated settings for camera: {camera}")
            
        except Exception as e:
            logger.error(f"Error updating camera settings: {e}")
            # Restore original settings on error
            self.current_config[camera] = deepcopy(self.original_config[camera])
            raise
            
    def save_config(self):
        """Save current configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.current_config, f, indent=4)
            logger.info("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            raise
            
    def reset_camera_settings(self, camera):
        """Reset settings for a specific camera to original values"""
        try:
            if camera not in self.original_config:
                raise ValueError(f"Unknown camera: {camera}")
                
            self.current_config[camera] = deepcopy(self.original_config[camera])
            self.save_config()
            
            logger.info(f"Reset settings for camera: {camera}")
            
        except Exception as e:
            logger.error(f"Error resetting camera settings: {e}")
            raise
            
    def get_camera_settings(self, camera):
        """Get current settings for a specific camera"""
        try:
            if camera not in self.current_config:
                raise ValueError(f"Unknown camera: {camera}")
            return deepcopy(self.current_config[camera])
        except Exception as e:
            logger.error(f"Error getting camera settings: {e}")
            raise

def load_sunrise_sunset_data():
    """Load and parse the sunrise/sunset data"""
    sunrise_sunset_path = os.path.join(CONFIGS_DIR, "LA_Sunrise_Sunset.txt")

    try:
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
        # Convert HHMM to HH:MM format
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
        # Initialize config manager
        config_manager = ConfigManager()
        
        # Test loading configuration
        config_manager.load_config()
        
        # Test loading sunrise/sunset data
        sunrise_sunset_data = load_sunrise_sunset_data()
        
        logger.info("All configuration files validated successfully")
        return True
        
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        return False

if __name__ == "__main__":
    try:
        logger.info("Testing configuration management...")
        
        # Initialize manager
        config_manager = ConfigManager()
        
        # Test loading
        config = config_manager.load_config()
        logger.info("Configuration loaded successfully")
        
        # Test validation
        validate_config_files()
        logger.info("Configuration validation complete")
        
    except Exception as e:
        logger.error(f"Configuration test failed: {e}")
        raise