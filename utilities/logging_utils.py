# File: utilities/logging_utils.py
# Purpose: Centralized logging configuration for the Owl Monitoring System

import logging
import os
from datetime import datetime
import pytz

def get_logs_dir():
    """Get the logs directory path"""
    # Direct path construction to avoid circular import
    base_path = "/Users/maxferrigni/Insync/maxferrigni@gmail.com/Google Drive/01 - Owl Box/60_IT/20_Motion_Detection"
    return os.path.join(base_path, "20_Local_Files", "logs")

def setup_logging(name="owl_monitor"):
    """
    Set up logging with file handler only - no console output.
    Console/GUI output is handled by the frontend LogRedirector.
    
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
    
    # Create file formatter with detailed information
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(module)s:%(funcName)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S %Z'
    )
    
    # Set up file handler
    log_filename = f'owl_monitor_{current_time.strftime("%Y%m%d")}.log'
    file_handler = logging.FileHandler(
        os.path.join(logs_dir, log_filename),
        encoding='utf-8'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)
    
    # Add only the file handler to logger
    logger.addHandler(file_handler)
    
    # Log initialization
    logger.info(f"File logging initialized: {log_filename}")
    
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

# Test the logging configuration
if __name__ == "__main__":
    logger = get_logger("test_logger")
    
    # Test different log levels
    logger.debug("This is a debug message - should not appear")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    # Test unicode handling
    logger.info("Testing unicode: 🦉 owl emoji")
    
    # Test multiline messages
    logger.info("""
    This is a multiline
    log message to test
    formatting
    """.strip())
    
    print("Logging test complete - check the log file in the logs directory")