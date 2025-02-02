# File: time_utils.py
# Purpose:
# Utility functions for handling time-based operations, particularly
# for determining if the current time is within allowed monitoring hours.

from datetime import datetime, timedelta
import pytz
import pandas as pd
from utilities.configs_loader import load_sunrise_sunset_data

def is_within_allowed_hours():
    """
    Check if current time is within allowed monitoring hours.
    Returns:
        bool: True if current time is within monitoring period, False otherwise.
    """
    try:
        # Get current time in LA timezone
        pacific = pytz.timezone('America/Los_Angeles')
        current_time = datetime.now(pacific)
        
        # Load sunrise/sunset data
        sun_data = load_sunrise_sunset_data()
        
        # Get today's data
        today_data = sun_data[sun_data['Date'].dt.date == current_time.date()]
        
        if today_data.empty:
            print("No sunrise/sunset data found for today")
            return False
            
        # Convert sunrise/sunset strings to datetime.time objects
        sunrise = datetime.strptime(today_data.iloc[0]['Sunrise'], '%H:%M').time()
        sunset = datetime.strptime(today_data.iloc[0]['Sunset'], '%H:%M').time()
        
        # Add buffer times (40 minutes before sunrise, 40 minutes after sunset)
        sunrise_dt = datetime.combine(current_time.date(), sunrise)
        sunset_dt = datetime.combine(current_time.date(), sunset)
        
        monitoring_start = (sunrise_dt - timedelta(minutes=40)).time()
        monitoring_end = (sunset_dt + timedelta(minutes=40)).time()
        
        current = current_time.time()
        
        # Log the times for debugging
        print(f"Current time: {current}")
        print(f"Monitoring period: {monitoring_start} to {monitoring_end}")
        print(f"Sunrise: {sunrise}, Sunset: {sunset}")
        
        # Between sunset and monitoring_end OR between monitoring_start and sunrise
        is_active = (sunset <= current <= monitoring_end) or (monitoring_start <= current <= sunrise)
        print(f"Is within monitoring hours: {is_active}")
        return is_active
        
    except Exception as e:
        print(f"Error checking allowed hours: {e}")
        return False