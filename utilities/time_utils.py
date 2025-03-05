# File: utilities/time_utils.py
# Purpose: Determine optimal lighting conditions for base image capture and motion detection
#
# March 5, 2025 Update - Version 1.2.0
# - Enhanced should_generate_after_action_report() with time-based fallback
# - Added database integration for report tracking
# - Reduced excessive error checking

from datetime import datetime, timedelta, date
import pytz
import pandas as pd
import os
import json
import time
from utilities.configs_loader import load_sunrise_sunset_data
from utilities.logging_utils import get_logger

# Import database utility for report time tracking
from utilities.database_utils import get_last_report_time

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
    'previous_condition': None,  # Added in v1.1.0 to track transitions
    'cache_duration': timedelta(minutes=5)  # Cache lighting condition for 5 minutes
}

# Add a new cache for base image capture timing
_base_image_timing_cache = {
    'last_capture_time': {},  # Dictionary by lighting condition
    'stable_period_start': {},  # When the current lighting condition started
    'min_capture_interval': timedelta(hours=3),  # Minimum time between captures for same condition
    'min_stable_period': timedelta(minutes=20),  # Minimum time in same lighting condition before capturing
    'last_transition_time': None  # New in v1.1.0 - Track when last transition occurred
}

# Track detailed lighting conditions for after action reports - Added in v1.1.0
_detailed_lighting_info = {
    'last_day_period': None,
    'last_night_period': None,
    'last_transition_start': None,
    'last_transition_end': None,
    'last_after_action_report': None
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

def _get_detailed_lighting_condition():
    """
    Get more detailed lighting condition for internal use.
    Used to determine true day/night vs transition periods.
    Added in v1.1.0.
    
    Returns:
        str: Detailed lighting condition
            'true_day' - Full daylight, well after sunrise
            'true_night' - Full darkness, well after sunset
            'dawn' - Transition period around sunrise
            'dusk' - Transition period around sunset
    """
    try:
        current_time = datetime.now(pytz.timezone('America/Los_Angeles'))
        
        # Get sun data for today
        sun_data = _get_cached_sun_data()
        today_data = sun_data[sun_data['Date'].dt.date == current_time.date()]
        
        if today_data.empty:
            logger.warning("No sunrise/sunset data found for today")
            return 'unknown'
            
        # Convert times to datetime.time objects
        sunrise = datetime.strptime(today_data.iloc[0]['Sunrise'], '%H:%M').time()
        sunset = datetime.strptime(today_data.iloc[0]['Sunset'], '%H:%M').time()
        
        # Calculate transition periods with wider margins for v1.1.0
        sunrise_dt = datetime.combine(current_time.date(), sunrise)
        sunset_dt = datetime.combine(current_time.date(), sunset)
        
        # Define true day/night with wider margins (90 minutes instead of 30)
        dawn_start = (sunrise_dt - timedelta(minutes=90)).time()
        dawn_end = (sunrise_dt + timedelta(minutes=90)).time()
        
        dusk_start = (sunset_dt - timedelta(minutes=90)).time()
        dusk_end = (sunset_dt + timedelta(minutes=90)).time()
        
        current = current_time.time()
        
        # Determine detailed condition
        if dawn_start <= current < dawn_end:
            return 'dawn'
        elif dusk_start <= current < dusk_end:
            return 'dusk'
        elif dawn_end <= current < dusk_start:
            return 'true_day'
        else:
            return 'true_night'
            
    except Exception as e:
        logger.error(f"Error determining detailed lighting condition: {e}")
        return 'unknown'

def get_current_lighting_condition():
    """
    Determine current lighting condition based on time of day.
    In v1.1.0, simplified to just 'day', 'night', or 'transition'.
    Uses caching to prevent frequent recalculations.
    
    Returns:
        str: Current lighting condition
            'day' - Full daylight (true_day)
            'night' - Full darkness (true_night)
            'transition' - Dawn or dusk periods
    """
    current_time = datetime.now(pytz.timezone('America/Los_Angeles'))
    
    # Check if cached condition is still valid
    if (_lighting_condition_cache['timestamp'] and 
        _lighting_condition_cache['condition'] and
        current_time - _lighting_condition_cache['timestamp'] < _lighting_condition_cache['cache_duration']):
        
        logger.debug("Using cached lighting condition")
        return _lighting_condition_cache['condition']
        
    # Get detailed condition
    detailed_condition = _get_detailed_lighting_condition()
    
    # Map detailed condition to simplified condition for v1.1.0
    condition_mapping = {
        'true_day': 'day',
        'true_night': 'night',
        'dawn': 'transition',
        'dusk': 'transition',
        'unknown': 'transition'  # Default to transition if unknown
    }
    
    # Get simplified condition
    condition = condition_mapping.get(detailed_condition, 'transition')
    
    # Check if lighting condition has changed
    previous_condition = _lighting_condition_cache.get('condition')
    if previous_condition != condition:
        # Store previous condition for transition tracking
        _lighting_condition_cache['previous_condition'] = previous_condition
        
        # Record the start time of this new lighting condition
        _base_image_timing_cache['stable_period_start'][condition] = current_time
        
        # If transitioning between day and night or vice versa, record for after action report
        if previous_condition in ['day', 'night'] and condition in ['day', 'night'] and previous_condition != condition:
            _detailed_lighting_info['last_transition_end'] = current_time
            logger.info(f"Major lighting transition detected: {previous_condition} to {condition}")
        elif previous_condition and condition == 'transition':
            _detailed_lighting_info['last_transition_start'] = current_time
            logger.info(f"Entering transition period from {previous_condition}")
        
        # Record day/night period starts
        if condition == 'day':
            _detailed_lighting_info['last_day_period'] = current_time
        elif condition == 'night':
            _detailed_lighting_info['last_night_period'] = current_time
            
        # Record transition time for base image capture logic
        _base_image_timing_cache['last_transition_time'] = current_time
        
        logger.info(f"Lighting condition changed from {previous_condition} to {condition}")
    
    # Update cache
    _lighting_condition_cache['timestamp'] = current_time
    _lighting_condition_cache['condition'] = condition
    
    logger.debug(f"New lighting condition calculated: {condition} (detailed: {detailed_condition})")
    return condition

def get_lighting_info():
    """
    Get all lighting-related information in a single call.
    
    Returns:
        dict: Dictionary containing current lighting information
    """
    condition = get_current_lighting_condition()
    detailed_condition = _get_detailed_lighting_condition()
    sun_data = _get_cached_sun_data()
    
    # Enhanced lighting info for v1.1.0
    return {
        'condition': condition,
        'detailed_condition': detailed_condition,
        'sun_data': sun_data,
        'cache_time': _lighting_condition_cache['timestamp'],
        'previous_condition': _lighting_condition_cache.get('previous_condition'),
        'is_transition': condition == 'transition',
        'last_transition_time': _base_image_timing_cache.get('last_transition_time')
    }

def is_lighting_condition_stable():
    """
    Determine if the current lighting condition has been stable for
    enough time to warrant a base image capture.
    
    Returns:
        bool: True if lighting condition is stable
    """
    current_time = datetime.now(pytz.timezone('America/Los_Angeles'))
    condition = get_current_lighting_condition()
    
    # In v1.1.0, only day and night are considered stable
    if condition == 'transition':
        logger.debug("Currently in transition period, not stable for base image capture")
        return False
    
    # If we don't have a record of when this condition started, it's not stable yet
    if condition not in _base_image_timing_cache['stable_period_start']:
        return False
        
    # Check if we've been in this lighting condition long enough
    stable_start = _base_image_timing_cache['stable_period_start'][condition]
    stable_duration = current_time - stable_start
    
    return stable_duration >= _base_image_timing_cache['min_stable_period']

def should_capture_base_image():
    """
    Determine if it's an optimal time to capture new base images.
    In v1.1.0, only allows capture during true day/night, not transitions.
    
    Returns:
        bool: True if optimal time for base image capture
    """
    current_time = datetime.now(pytz.timezone('America/Los_Angeles'))
    condition = get_current_lighting_condition()
    
    # If lighting condition is transition or unknown, don't capture
    if condition == 'transition':
        logger.debug("In transition period, skipping base image capture")
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
    detailed_condition = _get_detailed_lighting_condition()
    
    # Updated multipliers for v1.1.0 with more granular adjustments
    multipliers = {
        'day': 1.0,
        'night': 2.0,
        'transition': 1.5
    }
    
    # Fine-tune based on detailed condition
    detailed_adjustments = {
        'dawn': 1.4,
        'dusk': 1.6,
        'true_day': 1.0,
        'true_night': 2.0,
        'unknown': 1.5
    }
    
    # Use the standard multiplier as base, adjust with detailed if available
    multiplier = multipliers.get(condition, 1.0)
    if detailed_condition in detailed_adjustments:
        detailed_multiplier = detailed_adjustments[detailed_condition]
        # Use the average for better gradation
        multiplier = (multiplier + detailed_multiplier) / 2
    
    logger.debug(f"Luminance threshold multiplier for {condition} ({detailed_condition}): {multiplier}")
    return multiplier

def is_transition_period():
    """
    Check if we're currently in a lighting transition period.
    Added in v1.1.0 to better handle transition periods.
    
    Returns:
        bool: True if currently in transition period
    """
    condition = get_current_lighting_condition()
    return condition == 'transition'

def should_generate_after_action_report():
    """
    Determine if it's time to generate an after action report.
    Updated in v1.2.0 to include time-based fallback.
    
    Reports should be generated when:
    1. Completed a transition from day to night or night to day
    2. Haven't generated a report recently (time-based fallback)
    
    Returns:
        bool: True if a report should be generated
    """
    # Get current condition
    current_time = datetime.now(pytz.timezone('America/Los_Angeles'))
    condition = get_current_lighting_condition()
    previous_condition = _lighting_condition_cache.get('previous_condition')
    
    # Only consider major transitions (day to night or night to day)
    # Skip if we're in a transition period
    if condition == 'transition':
        logger.debug("Currently in transition period, not generating report")
        return False
        
    # Check if we just completed a transition
    if (previous_condition == 'transition' and 
        condition in ['day', 'night'] and
        _detailed_lighting_info['last_transition_end']):
        
        logger.info(f"Transition complete from transition to {condition}, should generate report")
        return True
    
    # [NEW in v1.2.0] Time-based fallback: Check when the last report was generated
    last_report_time = get_last_report_time()
    
    # If no report has ever been generated, definitely generate one
    if not last_report_time:
        logger.info("No previous report found, should generate report")
        return True
    
    # If we have a last report time, check if it's been more than 24 hours
    try:
        # Parse datetime if it's a string
        if isinstance(last_report_time, str):
            try:
                last_report_time = datetime.fromisoformat(last_report_time.replace('Z', '+00:00'))
            except ValueError:
                # If parsing fails, use a fallback time that will trigger report
                last_report_time = current_time - timedelta(hours=25)
        
        # Ensure last_report_time has timezone info for comparison
        if last_report_time.tzinfo is None:
            last_report_time = pytz.UTC.localize(last_report_time)
            
        # Convert to Pacific time for comparison
        last_report_pacific = last_report_time.astimezone(pytz.timezone('America/Los_Angeles'))
        
        # Check if it's been more than 24 hours since the last report
        if (current_time - last_report_pacific) > timedelta(hours=24):
            logger.info("More than 24 hours since last report, should generate report")
            return True
            
    except Exception as e:
        # On error, generate a report to be safe
        logger.error(f"Error checking last report time: {e}")
        return True
    
    # No need to generate a report
    return False

def record_after_action_report():
    """
    Record that an after action report was generated.
    Added in v1.1.0 to support after action reports.
    """
    current_time = datetime.now(pytz.timezone('America/Los_Angeles'))
    _detailed_lighting_info['last_after_action_report'] = current_time
    logger.info(f"Recorded after action report generation at {current_time}")

def get_session_duration():
    """
    Calculate the duration of the current lighting session.
    Added in v1.1.0 to support after action reports.
    
    Returns:
        timedelta: Duration of current session
    """
    current_time = datetime.now(pytz.timezone('America/Los_Angeles'))
    condition = get_current_lighting_condition()
    
    # Use the appropriate period start time
    if condition == 'day':
        start_time = _detailed_lighting_info.get('last_day_period')
    elif condition == 'night':
        start_time = _detailed_lighting_info.get('last_night_period')
    else:
        # For transitions, use the previous major period
        if _lighting_condition_cache.get('previous_condition') == 'day':
            start_time = _detailed_lighting_info.get('last_day_period')
        else:
            start_time = _detailed_lighting_info.get('last_night_period')
    
    # If no start time recorded, default to 12 hours
    if not start_time:
        return timedelta(hours=12)
        
    return current_time - start_time

if __name__ == "__main__":
    # Test the timing functions
    logger.info("Testing lighting condition detection...")
    lighting_info = get_lighting_info()
    print(f"Current lighting info: {lighting_info}")
    print(f"Current detailed condition: {_get_detailed_lighting_condition()}")
    print(f"Is transition period: {is_transition_period()}")
    print(f"Is lighting condition stable: {is_lighting_condition_stable()}")
    print(f"Should capture base image: {should_capture_base_image()}")
    print(f"Luminance threshold multiplier: {get_luminance_threshold_multiplier()}")
    print(f"Should generate after action report: {should_generate_after_action_report()}")
    print(f"Session duration: {get_session_duration()}")