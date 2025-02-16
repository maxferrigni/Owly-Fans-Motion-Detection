# File: utilities/logging_utils.py
# Purpose: Centralized logging configuration for the Owl Monitoring System

import logging
import os
from datetime import datetime
import pytz
from utilities.constants import get_base_dir

def get_logs_dir():
    """Get the logs directory path"""
    return os.path.join(get_base_dir(), "20_Local_Files", "logs")

def setup_logging(name="owl_monitor"):
    """
    Set up logging with both file and console handlers.
    
    Args:
        name (str): Logger name, defaults to "owl_monitor"
    
    Returns:
        logging.Logger: Configured logger instance
    """
    # Ensure logs directory exists
    logs_dir = get_logs_dir()
    os.makedirs(logs_dir, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Remove any existing handlers
    logger.handlers = []
    
    # Get current time in Pacific timezone for log filename
    pacific = pytz.timezone('America/Los_Angeles')
    current_time = datetime.now(pacific)
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S %Z'
    )
    console_formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S')
    
    # File handler
    log_filename = f'owl_monitor_{current_time.strftime("%Y%m%d")}.log'
    file_handler = logging.FileHandler(
        os.path.join(logs_dir, log_filename)
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Log initialization
    logger.info("Logging initialized")
    logger.info(f"Log file: {log_filename}")
    
    return logger

def get_logger(name="owl_monitor"):
    """
    Get or create a logger instance.
    
    Args:
        name (str): Logger name, defaults to "owl_monitor"
    
    Returns:
        logging.Logger: Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger = setup_logging(name)
    return logger