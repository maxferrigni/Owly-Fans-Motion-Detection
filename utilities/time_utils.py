# File: time_utils.py
# Purpose: Determine optimal lighting conditions for base image capture and motion detection
# These times are critical for:
# 1. Capturing accurate base images with proper lighting conditions
# 2. Adjusting luminance thresholds based on time of day
# 3. Understanding natural light changes that could affect motion detection

from datetime import datetime, timedelta
import pytz
import pandas as pd
from utilities.configs_loader import load_sunrise_sunset_data
from utilities.logging_utils import get_logger

# Initialize logger
logger = get_logger()

def get_current_lighting_condition():
    """
    Determine current lighting condition based on time of day.
    
    Returns:
        str: Current lighting condition
            'night' - Full darkness
            'astronomical_twilight' - Sun is 12-18 degrees below horizon
            'civil_twilight' - Sun is 0-6 degrees below horizon
            'day' - Full daylight
    """
    try:
        pacific = pytz.timezone('America/Los_Angeles')
        current_time = datetime.now(pacific)
        
        # Load sunrise/sunset data
        sun_data = load_sunrise_sunset_data()
        today_data = sun_data[sun_data['Date'].dt.date == current_time.date()]
        
        if today_data.empty:
            logger.warning("No sunrise/sunset data found for today")
            return 'unknown'
            
        # Convert times to datetime.time objects
        sunrise = datetime.strptime(today_data.iloc[0]['Sunrise'], '%H:%M').time()
        sunset = datetime.strptime(today_data.iloc[0]['Sunset'], '%H:%M').time()
        
        # Calculate twilight periods (approximately)
        sunrise_dt = datetime.combine(current_time.date(), sunrise)
        sunset_dt = datetime.combine(current_time.date(), sunset)
        
        civil_twilight_start = (sunrise_dt - timedelta(minutes=30)).time()
        astronomical_twilight_start = (sunrise_dt - timedelta(minutes=70)).time()
        
        civil_twilight_end = (sunset_dt + timedelta(minutes=30)).time()
        astronomical_twilight_end = (sunset_dt + timedelta(minutes=70)).time()
        
        current = current_time.time()
        
        # Determine current condition
        if sunrise <= current <= sunset:
            condition = 'day'
        elif (civil_twilight_start <= current < sunrise) or (sunset < current <= civil_twilight_end):
            condition = 'civil_twilight'
        elif (astronomical_twilight_start <= current < civil_twilight_start) or (civil_twilight_end < current <= astronomical_twilight_end):
            condition = 'astronomical_twilight'
        else:
            condition = 'night'
            
        logger.debug(f"Current lighting condition: {condition}")
        return condition
        
    except Exception as e:
        logger.error(f"Error determining lighting condition: {e}")
        return 'unknown'

def should_capture_base_image():
    """
    Determine if it's an optimal time to capture new base images.
    Base images should be captured during stable lighting conditions:
    - Middle of the night (most stable darkness)
    - Middle of the day (most stable daylight)
    
    Returns:
        bool: True if optimal time for base image capture
    """
    try:
        condition = get_current_lighting_condition()
        
        if condition == 'unknown':
            return False
            
        pacific = pytz.timezone('America/Los_Angeles')
        current_time = datetime.now(pacific)
        
        # Load sunrise/sunset data
        sun_data = load_sunrise_sunset_data()
        today_data = sun_data[sun_data['Date'].dt.date == current_time.date()]
        
        if today_data.empty:
            return False
            
        sunrise = datetime.strptime(today_data.iloc[0]['Sunrise'], '%H:%M').time()
        sunset = datetime.strptime(today_data.iloc[0]['Sunset'], '%H:%M').time()
        
        # Calculate optimal times
        sunrise_dt = datetime.combine(current_time.date(), sunrise)
        sunset_dt = datetime.combine(current_time.date(), sunset)
        
        mid_day = (sunrise_dt + (sunset_dt - sunrise_dt) / 2).time()
        mid_night = ((datetime.combine(current_time.date(), sunset) + 
                     timedelta(hours=6)).time())
        
        current = current_time.time()
        
        # Check if within optimal windows (±30 minutes from mid-points)
        day_window_start = (datetime.combine(current_time.date(), mid_day) - 
                          timedelta(minutes=30)).time()
        day_window_end = (datetime.combine(current_time.date(), mid_day) + 
                        timedelta(minutes=30)).time()
        
        night_window_start = (datetime.combine(current_time.date(), mid_night) - 
                           timedelta(minutes=30)).time()
        night_window_end = (datetime.combine(current_time.date(), mid_night) + 
                         timedelta(minutes=30)).time()
        
        is_optimal = (
            (day_window_start <= current <= day_window_end) or
            (night_window_start <= current <= night_window_end)
        )
        
        if is_optimal:
            logger.info(f"Optimal time for base image capture during {condition}")
        
        return is_optimal
        
    except Exception as e:
        logger.error(f"Error checking base image capture timing: {e}")
        return False

def get_luminance_threshold_multiplier():
    """
    Get multiplier for luminance threshold based on current lighting condition.
    Different lighting conditions require different sensitivity levels.
    
    Returns:
        float: Multiplier for base luminance threshold
    """
    condition = get_current_lighting_condition()
    
    multipliers = {
        'day': 1.0,           # Normal sensitivity
        'civil_twilight': 1.2, # Slightly higher sensitivity
        'astronomical_twilight': 1.5, # Higher sensitivity
        'night': 2.0,         # Highest sensitivity
        'unknown': 1.0        # Default to normal sensitivity
    }
    
    multiplier = multipliers.get(condition, 1.0)
    logger.debug(f"Luminance threshold multiplier for {condition}: {multiplier}")
    return multiplier

if __name__ == "__main__":
    # Test the timing functions
    logger.info("Testing lighting condition detection...")
    print(f"Current lighting condition: {get_current_lighting_condition()}")
    print(f"Should capture base image: {should_capture_base_image()}")
    print(f"Luminance threshold multiplier: {get_luminance_threshold_multiplier()}")