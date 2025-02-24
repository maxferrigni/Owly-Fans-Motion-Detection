# File: utilities/time_utils.py
# Purpose: Determine optimal lighting conditions for base image capture and motion detection

from datetime import datetime, timedelta, date
import pytz
import pandas as pd
import os
import json
import time
from utilities.configs_loader import load_sunrise_sunset_data
from utilities.logging_utils import get_logger

# Initialize logger
logger = get_logger()

# Cache for sunrise/sunset data and lighting conditions
_sun_data_cache = {
    'date': None,
    'data': None
}

_lighting_condition_cache = {
    'timestamp': None,
    'condition': None,
    'cache_duration': timedelta(minutes=5)  # Cache lighting condition for 5 minutes
}

# Add a new cache for base image capture timing
_base_image_timing_cache = {
    'last_capture_time': {},  # Dictionary by lighting condition
    'stable_period_start': {},  # When the current lighting condition started
    'min_capture_interval': timedelta(hours=3),  # Minimum time between captures for same condition
    'min_stable_period': timedelta(minutes=20)  # Minimum time in same lighting condition before capturing
}

def _get_cached_sun_data():
    """
    Get cached sunrise/sunset data, reloading if needed.
    
    Returns:
        pandas.DataFrame: Sunrise/sunset data for current date
    """
    current_date = date.today()
    
    # If cache is empty or from a different date, reload
    if (_sun_data_cache['date'] != current_date or 
        _sun_data_cache['data'] is None):
        
        logger.debug("Loading sunrise/sunset data from file")
        _sun_data_cache['data'] = load_sunrise_sunset_data()
        _sun_data_cache['date'] = current_date
    
    return _sun_data_cache['data']

def get_current_lighting_condition():
    """
    Determine current lighting condition based on time of day.
    Uses caching to prevent frequent recalculations.
    
    Returns:
        str: Current lighting condition
            'night' - Full darkness
            'astronomical_twilight' - Sun is 12-18 degrees below horizon
            'civil_twilight' - Sun is 0-6 degrees below horizon
            'day' - Full daylight
    """
    try:
        current_time = datetime.now(pytz.timezone('America/Los_Angeles'))
        
        # Check if cached condition is still valid
        if (_lighting_condition_cache['timestamp'] and 
            _lighting_condition_cache['condition'] and
            current_time - _lighting_condition_cache['timestamp'] < _lighting_condition_cache['cache_duration']):
            
            logger.debug("Using cached lighting condition")
            return _lighting_condition_cache['condition']
            
        # Get sun data for today
        sun_data = _get_cached_sun_data()
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
            
        # Check if lighting condition has changed
        previous_condition = _lighting_condition_cache.get('condition')
        if previous_condition != condition:
            # Record the start time of this new lighting condition
            _base_image_timing_cache['stable_period_start'][condition] = current_time
            logger.info(f"Lighting condition changed from {previous_condition} to {condition}")
        
        # Update cache
        _lighting_condition_cache['timestamp'] = current_time
        _lighting_condition_cache['condition'] = condition
        
        logger.debug(f"New lighting condition calculated: {condition}")
        return condition
        
    except Exception as e:
        logger.error(f"Error determining lighting condition: {e}")
        return 'unknown'

def get_lighting_info():
    """
    Get all lighting-related information in a single call.
    
    Returns:
        dict: Dictionary containing current lighting information
    """
    try:
        condition = get_current_lighting_condition()
        sun_data = _get_cached_sun_data()
        
        return {
            'condition': condition,
            'sun_data': sun_data,
            'cache_time': _lighting_condition_cache['timestamp']
        }
    except Exception as e:
        logger.error(f"Error getting lighting info: {e}")
        return None

def is_lighting_condition_stable():
    """
    Determine if the current lighting condition has been stable for
    enough time to warrant a base image capture.
    
    Returns:
        bool: True if lighting condition is stable
    """
    try:
        current_time = datetime.now(pytz.timezone('America/Los_Angeles'))
        condition = get_current_lighting_condition()
        
        # If we don't have a record of when this condition started, it's not stable yet
        if condition not in _base_image_timing_cache['stable_period_start']:
            return False
            
        # Check if we've been in this lighting condition long enough
        stable_start = _base_image_timing_cache['stable_period_start'][condition]
        stable_duration = current_time - stable_start
        
        return stable_duration >= _base_image_timing_cache['min_stable_period']
        
    except Exception as e:
        logger.error(f"Error checking lighting stability: {e}")
        return False

def should_capture_base_image():
    """
    Determine if it's an optimal time to capture new base images.
    
    Returns:
        bool: True if optimal time for base image capture
    """
    try:
        current_time = datetime.now(pytz.timezone('America/Los_Angeles'))
        condition = get_current_lighting_condition()
        
        # If lighting condition is unknown, don't capture
        if condition == 'unknown':
            return False
            
        # Only capture during stable lighting conditions
        if not is_lighting_condition_stable():
            logger.debug(f"Lighting condition {condition} not stable yet, skipping base image capture")
            return False
        
        # Check if we've recently captured for this lighting condition
        if condition in _base_image_timing_cache['last_capture_time']:
            last_capture = _base_image_timing_cache['last_capture_time'][condition]
            time_since_last = current_time - last_capture
            
            if time_since_last < _base_image_timing_cache['min_capture_interval']:
                logger.debug(f"Too soon since last {condition} base image capture ({time_since_last}), skipping")
                return False
        
        # If we get here, it's a good time to capture
        logger.info(f"Optimal time for base image capture during stable {condition} conditions")
        _base_image_timing_cache['last_capture_time'][condition] = current_time
        return True
        
    except Exception as e:
        logger.error(f"Error checking base image capture timing: {e}")
        return False

def record_base_image_capture(lighting_condition):
    """
    Record that a base image capture occurred for the given lighting condition.
    This helps prevent too-frequent captures.
    
    Args:
        lighting_condition (str): The lighting condition when capture occurred
    """
    current_time = datetime.now(pytz.timezone('America/Los_Angeles'))
    _base_image_timing_cache['last_capture_time'][lighting_condition] = current_time
    logger.debug(f"Recorded base image capture for {lighting_condition} at {current_time}")

def get_luminance_threshold_multiplier():
    """
    Get multiplier for luminance threshold based on current lighting condition.
    
    Returns:
        float: Multiplier for base luminance threshold
    """
    condition = get_current_lighting_condition()
    
    multipliers = {
        'day': 1.0,
        'civil_twilight': 1.2,
        'astronomical_twilight': 1.5,
        'night': 2.0,
        'unknown': 1.0
    }
    
    multiplier = multipliers.get(condition, 1.0)
    logger.debug(f"Luminance threshold multiplier for {condition}: {multiplier}")
    return multiplier

if __name__ == "__main__":
    # Test the timing functions
    logger.info("Testing lighting condition detection...")
    lighting_info = get_lighting_info()
    print(f"Current lighting info: {lighting_info}")
    print(f"Is lighting condition stable: {is_lighting_condition_stable()}")
    print(f"Should capture base image: {should_capture_base_image()}")
    print(f"Luminance threshold multiplier: {get_luminance_threshold_multiplier()}")