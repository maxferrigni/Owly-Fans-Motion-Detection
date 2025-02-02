# File: configs_loader.py
# Purpose:
# Utility script to load and validate configuration files for the Owl Monitoring System.
# Includes functions to load camera configs, email/text recipients, and sunrise/sunset data.

import json
import os
import pandas as pd

# Paths to config files
CONFIG_PATH = "../configs/config.json"
EMAIL_RECIPIENTS_PATH = "../configs/email_recipients.txt"
TEXT_RECIPIENTS_PATH = "../configs/text_recipients.txt"
SUNRISE_SUNSET_PATH = "../configs/LA_Sunrise_Sunset.txt"

def load_camera_config():
    """
    Load and validate the camera configuration from config.json.
    Returns:
        dict: Parsed configuration data.
    Raises:
        FileNotFoundError: If the config file is missing.
        json.JSONDecodeError: If the config file is invalid.
    """
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r") as file:
        return json.load(file)

def load_email_recipients():
    """
    Load the list of email recipients from email_recipients.txt.
    Returns:
        list: A list of email addresses.
    Raises:
        FileNotFoundError: If the email recipients file is missing.
    """
    if not os.path.exists(EMAIL_RECIPIENTS_PATH):
        raise FileNotFoundError(f"Email recipients file not found: {EMAIL_RECIPIENTS_PATH}")
    with open(EMAIL_RECIPIENTS_PATH, "r") as file:
        return [line.strip() for line in file if line.strip()]

def load_text_recipients():
    """
    Load the list of text recipients from text_recipients.txt.
    Returns:
        list: A list of text recipient numbers or addresses.
    Raises:
        FileNotFoundError: If the text recipients file is missing.
    """
    if not os.path.exists(TEXT_RECIPIENTS_PATH):
        raise FileNotFoundError(f"Text recipients file not found: {TEXT_RECIPIENTS_PATH}")
    with open(TEXT_RECIPIENTS_PATH, "r") as file:
        return [line.strip() for line in file if line.strip()]

def load_sunrise_sunset_data():
    """
    Load and parse the sunrise/sunset data from LA_Sunrise_Sunset.txt.
    Returns:
        pandas.DataFrame: DataFrame containing date, sunrise, and sunset times.
    Raises:
        FileNotFoundError: If the sunrise/sunset file is missing.
    """
    if not os.path.exists(SUNRISE_SUNSET_PATH):
        raise FileNotFoundError(f"Sunrise/Sunset data file not found: {SUNRISE_SUNSET_PATH}")
    
    # Read the file with tabs as delimiter and parse Date column
    df = pd.read_csv(SUNRISE_SUNSET_PATH, delimiter="\t")
    
    # Convert Date column to datetime
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Ensure Sunrise and Sunset are strings in HH:MM format
    df['Sunrise'] = df['Sunrise'].astype(str).str.pad(4, fillchar='0')
    df['Sunset'] = df['Sunset'].astype(str).str.pad(4, fillchar='0')
    
    return df