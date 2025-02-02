# File: utilities/configs_loader.py
# Purpose: Load and validate configuration files for the Owl Monitoring System

import json
import os
import pandas as pd
from utilities.logging_utils import get_logger
from utilities.constants import CONFIGS_DIR

# Initialize logger
logger = get_logger()

def load_camera_config():
    """
    Load and validate the camera configuration from config.json.
    
    Returns:
        dict: Parsed configuration data
        
    Raises:
        FileNotFoundError: If the config file is missing
        json.JSONDecodeError: If the config file is invalid JSON
    """
    config_path = os.path.join(CONFIGS_DIR, "config.json")
    
    try:
        if not os.path.exists(config_path):
            error_msg = f"Config file not found: {config_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        with open(config_path, "r") as file:
            config = json.load(file)
            
        # Validate required fields in config
        required_fields = ["roi", "threshold_percentage", "luminance_threshold", "alert_type"]
        for camera, settings in config.items():
            missing_fields = [field for field in required_fields if field not in settings]
            if missing_fields:
                error_msg = f"Missing required fields {missing_fields} for camera {camera}"
                logger.error(error_msg)
                raise ValueError(error_msg)

        logger.info("Camera configuration loaded successfully")
        return config

    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in config file: {e}"
        logger.error(error_msg)
        raise
    except Exception as e:
        logger.error(f"Error loading camera config: {e}")
        raise

def load_sunrise_sunset_data():
    """
    Load and parse the sunrise/sunset data from LA_Sunrise_Sunset.txt.
    
    Returns:
        pandas.DataFrame: DataFrame containing date, sunrise, and sunset times
        
    Raises:
        FileNotFoundError: If the sunrise/sunset file is missing
    """
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
        df['Sunrise'] = df['Sunrise'].astype(str).str.pad(4, fillchar='0')
        df['Sunset'] = df['Sunset'].astype(str).str.pad(4, fillchar='0')
        
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
    """
    Validate all configuration files exist and are readable.
    
    Returns:
        bool: True if all validations pass
    """
    try:
        # Test loading each configuration
        camera_config = load_camera_config()
        sunrise_sunset_data = load_sunrise_sunset_data()
        
        logger.info("All configuration files validated successfully")
        return True
        
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        return False

if __name__ == "__main__":
    try:
        logger.info("Testing configuration loading...")
        validate_config_files()
        logger.info("Configuration test complete")
    except Exception as e:
        logger.error(f"Configuration test failed: {e}")