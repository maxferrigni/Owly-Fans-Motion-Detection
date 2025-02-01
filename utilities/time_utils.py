# File: time_utils.py
# Purpose:
# Utility functions for handling time-based operations, particularly
# for determining if the current time is within allowed monitoring hours.

from datetime import datetime
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
            
        # Get sunrise and sunset times
        sunrise = today_data.iloc[0]['Sunrise']
        sunset = today_data.iloc[0]['Sunset']
        
        # Add buffer times (40 minutes before sunrise, 40 minutes after sunset)
        buffer_minutes = 40
        monitoring_start = sunrise - pd.Timedelta(minutes=buffer_minutes)
        monitoring_end = sunset + pd.Timedelta(minutes=buffer_minutes)
        
        # Check if current time is within monitoring period
        return monitoring_start <= current_time.time() <= monitoring_end
        
    except Exception as e:
        print(f"Error checking allowed hours: {e}")
        return False