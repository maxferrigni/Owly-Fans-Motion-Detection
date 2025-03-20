# File: utilities/time_utils.py
# Purpose: Determine optimal lighting conditions for base image capture and motion detection
#
# March 28, 2025 Update - Version 1.4.6
# - Improved lighting condition determination for day/night settings
# - Enhanced transition period detection
# - Simplified cached data tracking
# - Added clear documentation of lighting state boundaries

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
    'previous_condition': None,
    'cache_duration': timedelta(minutes=5)  # Cache lighting condition for 5 minutes
}

# Add a new cache for base image capture timing
_base_image_timing_cache = {
    'last_capture_time': {},  # Dictionary by lighting condition
    'stable_period_start': {},  # When the current lighting condition started
    'min_capture_interval': timedelta(hours=3),  # Minimum time between captures for same condition
    'min_stable_period': timedelta(minutes=20),  # Minimum time in same lighting condition before capturing
    'last_transition_time': None
}

# Track detailed lighting conditions for after action reports
_detailed_lighting_info = {
    'last_day_period': None,
    'last_night_period': None,
    'last_transition_start': None,
    'last_transition_end': None,
    'last_after_action_report': None
}

# Track sunrise/sunset times for countdown display
_time_tracking = {
    'next_sunrise': None,
    'next_sunset': None,
    'next_true_day': None,  # Next time true day begins
    'next_true_night': None,  # Next time true night begins
    'last_updated': None     # When these values were last calculated
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
        
        # Calculate transition periods with 30-minute window
        sunrise_dt = datetime.combine(current_time.date(), sunrise)
        sunset_dt = datetime.combine(current_time.date(), sunset)
        
        # Ensure these datetime objects are timezone aware by localizing them
        pacific_tz = pytz.timezone('America/Los_Angeles')
        sunrise_dt = pacific_tz.localize(sunrise_dt)
        sunset_dt = pacific_tz.localize(sunset_dt)
        
        # Define true day/night with 30-minute margins
        dawn_start = (sunrise_dt - timedelta(minutes=30)).time()
        dawn_end = (sunrise_dt + timedelta(minutes=30)).time()
        
        dusk_start = (sunset_dt - timedelta(minutes=30)).time()
        dusk_end = (sunset_dt + timedelta(minutes=30)).time()
        
        # Update next transition times for countdown display
        _update_time_tracking(current_time, sunrise_dt, sunset_dt)
        
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

def _update_time_tracking(current_time, sunrise_dt, sunset_dt):
    """
    Update the time tracking for sunrise/sunset countdowns.
    
    Args:
        current_time (datetime): Current time (timezone-aware)
        sunrise_dt (datetime): Today's sunrise time
        sunset_dt (datetime): Today's sunset time
    """
    # Only update once per hour to avoid unnecessary calculations
    if (_time_tracking['last_updated'] and 
        (current_time - _time_tracking['last_updated'] < timedelta(hours=1))):
        return
        
    try:
        # Ensure the datetime objects have timezone information
        pacific_tz = pytz.timezone('America/Los_Angeles')
        
        # Make sunrise_dt timezone-aware if it isn't already
        if sunrise_dt.tzinfo is None:
            sunrise_dt = pacific_tz.localize(sunrise_dt)
            
        # Make sunset_dt timezone-aware if it isn't already
        if sunset_dt.tzinfo is None:
            sunset_dt = pacific_tz.localize(sunset_dt)
            
        # Calculate next sunrise
        if current_time.time() < sunrise_dt.time():
            # Sunrise is later today
            _time_tracking['next_sunrise'] = sunrise_dt
        else:
            # Sunrise is tomorrow - get tomorrow's date
            tomorrow = current_time.date() + timedelta(days=1)
            
            # Get sun data for tomorrow
            sun_data = _get_cached_sun_data()
            tomorrow_data = sun_data[sun_data['Date'].dt.date == tomorrow]
            
            if not tomorrow_data.empty:
                tomorrow_sunrise = datetime.strptime(tomorrow_data.iloc[0]['Sunrise'], '%H:%M').time()
                tomorrow_sunrise_dt = datetime.combine(tomorrow, tomorrow_sunrise)
                # Make timezone-aware
                _time_tracking['next_sunrise'] = pacific_tz.localize(tomorrow_sunrise_dt)
            else:
                # If no data for tomorrow, estimate based on today
                _time_tracking['next_sunrise'] = sunrise_dt + timedelta(days=1)
                
        # Calculate next sunset
        if current_time.time() < sunset_dt.time():
            # Sunset is later today
            _time_tracking['next_sunset'] = sunset_dt
        else:
            # Sunset is tomorrow - get tomorrow's date
            tomorrow = current_time.date() + timedelta(days=1)
            
            # Get sun data for tomorrow
            sun_data = _get_cached_sun_data()
            tomorrow_data = sun_data[sun_data['Date'].dt.date == tomorrow]
            
            if not tomorrow_data.empty:
                tomorrow_sunset = datetime.strptime(tomorrow_data.iloc[0]['Sunset'], '%H:%M').time()
                tomorrow_sunset_dt = datetime.combine(tomorrow, tomorrow_sunset)
                # Make timezone-aware
                _time_tracking['next_sunset'] = pacific_tz.localize(tomorrow_sunset_dt)
            else:
                # If no data for tomorrow, estimate based on today
                _time_tracking['next_sunset'] = sunset_dt + timedelta(days=1)
                
        # Calculate next true day (30 minutes after sunrise)
        _time_tracking['next_true_day'] = _time_tracking['next_sunrise'] + timedelta(minutes=30)
        
        # Calculate next true night (30 minutes after sunset)
        _time_tracking['next_true_night'] = _time_tracking['next_sunset'] + timedelta(minutes=30)
        
        _time_tracking['last_updated'] = current_time
        
    except Exception as e:
        logger.error(f"Error updating time tracking: {e}")

def get_current_lighting_condition():
    """
    Determine current lighting condition based on time of day.
    Simplified to just 'day', 'night', or 'transition'.
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
    
    # Map detailed condition to simplified condition
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
    
    logger.debug(f"Current lighting condition: {condition} (detailed: {detailed_condition})")
    return condition

def get_lighting_info():
    """
    Get all lighting-related information in a single call.
    Enhanced to include countdown information.
    
    Returns:
        dict: Dictionary containing current lighting information
    """
    condition = get_current_lighting_condition()
    detailed_condition = _get_detailed_lighting_condition()
    sun_data = _get_cached_sun_data()
    
    # Get current time for countdown calculations
    current_time = datetime.now(pytz.timezone('America/Los_Angeles'))
    
    # Get transition completion percentage
    transition_percentage = 0
    if condition == 'transition':
        if detailed_condition == 'dawn':
            # Calculate how far through dawn we are
            if _time_tracking['next_sunrise'] and _time_tracking['next_true_day']:
                # Make sure both datetimes are timezone-aware before subtracting
                next_sunrise = _time_tracking['next_sunrise']
                next_true_day = _time_tracking['next_true_day']
                
                # Ensure timezone awareness
                if next_sunrise.tzinfo is None:
                    pacific_tz = pytz.timezone('America/Los_Angeles')
                    next_sunrise = pacific_tz.localize(next_sunrise)
                
                if next_true_day.tzinfo is None:
                    pacific_tz = pytz.timezone('America/Los_Angeles')
                    next_true_day = pacific_tz.localize(next_true_day)
                
                # Calculate dawn 30 min before sunrise
                dawn_start = next_sunrise - timedelta(minutes=30)
                
                # Now calculate time deltas safely
                total_dawn_period = (next_true_day - dawn_start)
                time_into_dawn = (current_time - dawn_start)
                
                if total_dawn_period.total_seconds() > 0:
                    transition_percentage = (time_into_dawn.total_seconds() / 
                                            total_dawn_period.total_seconds()) * 100
        elif detailed_condition == 'dusk':
            # Calculate how far through dusk we are
            if _time_tracking['next_sunset'] and _time_tracking['next_true_night']:
                # Make sure both datetimes are timezone-aware before subtracting
                next_sunset = _time_tracking['next_sunset']
                next_true_night = _time_tracking['next_true_night']
                
                # Ensure timezone awareness
                if next_sunset.tzinfo is None:
                    pacific_tz = pytz.timezone('America/Los_Angeles')
                    next_sunset = pacific_tz.localize(next_sunset)
                
                if next_true_night.tzinfo is None:
                    pacific_tz = pytz.timezone('America/Los_Angeles')
                    next_true_night = pacific_tz.localize(next_true_night)
                
                # Calculate dusk 30 min before sunset
                dusk_start = next_sunset - timedelta(minutes=30)
                
                # Now calculate time deltas safely
                total_dusk_period = (next_true_night - dusk_start)
                time_into_dusk = (current_time - dusk_start)
                
                if total_dusk_period.total_seconds() > 0:
                    transition_percentage = (time_into_dusk.total_seconds() / 
                                            total_dusk_period.total_seconds()) * 100

    # Ensure transition percentage is clamped between 0-100
    transition_percentage = max(0, min(100, transition_percentage))
    
    # Calculate countdown times
    countdown_info = {
        'to_sunrise': None,
        'to_sunset': None,
        'to_true_day': None,
        'to_true_night': None
    }
    
    # Make sure all datetime objects have timezone info before calculation
    if _time_tracking['next_sunrise']:
        next_sunrise = _time_tracking['next_sunrise']
        if next_sunrise.tzinfo is None:
            pacific_tz = pytz.timezone('America/Los_Angeles')
            next_sunrise = pacific_tz.localize(next_sunrise)
        countdown_info['to_sunrise'] = (next_sunrise - current_time).total_seconds()
        
    if _time_tracking['next_sunset']:
        next_sunset = _time_tracking['next_sunset']
        if next_sunset.tzinfo is None:
            pacific_tz = pytz.timezone('America/Los_Angeles')
            next_sunset = pacific_tz.localize(next_sunset)
        countdown_info['to_sunset'] = (next_sunset - current_time).total_seconds()
        
    if _time_tracking['next_true_day']:
        next_true_day = _time_tracking['next_true_day']
        if next_true_day.tzinfo is None:
            pacific_tz = pytz.timezone('America/Los_Angeles')
            next_true_day = pacific_tz.localize(next_true_day)
        countdown_info['to_true_day'] = (next_true_day - current_time).total_seconds()
        
    if _time_tracking['next_true_night']:
        next_true_night = _time_tracking['next_true_night']
        if next_true_night.tzinfo is None:
            pacific_tz = pytz.timezone('America/Los_Angeles')
            next_true_night = pacific_tz.localize(next_true_night)
        countdown_info['to_true_night'] = (next_true_night - current_time).total_seconds()
    
    # Format times as strings for display, handling None values
    next_sunrise_str = None
    if _time_tracking['next_sunrise']:
        next_sunrise_str = _time_tracking['next_sunrise'].strftime('%H:%M:%S')
        
    next_sunset_str = None
    if _time_tracking['next_sunset']:
        next_sunset_str = _time_tracking['next_sunset'].strftime('%H:%M:%S')
        
    next_true_day_str = None
    if _time_tracking['next_true_day']:
        next_true_day_str = _time_tracking['next_true_day'].strftime('%H:%M:%S')
        
    next_true_night_str = None
    if _time_tracking['next_true_night']:
        next_true_night_str = _time_tracking['next_true_night'].strftime('%H:%M:%S')
    
    # Enhanced lighting info
    return {
        'condition': condition,
        'detailed_condition': detailed_condition,
        'sun_data': sun_data,
        'cache_time': _lighting_condition_cache['timestamp'],
        'previous_condition': _lighting_condition_cache.get('previous_condition'),
        'is_transition': condition == 'transition',
        'last_transition_time': _base_image_timing_cache.get('last_transition_time'),
        'transition_percentage': round(transition_percentage, 1),
        'countdown': countdown_info,
        'next_sunrise': next_sunrise_str,
        'next_sunset': next_sunset_str,
        'next_true_day': next_true_day_str,
        'next_true_night': next_true_night_str
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
    
    Returns:
        tuple: (bool, str) - (should_capture, lighting_condition)
    """
    current_time = datetime.now(pytz.timezone('America/Los_Angeles'))
    condition = get_current_lighting_condition()
    
    # Prefer capturing in pure day/night conditions, avoid transitions
    if condition == 'transition':
        logger.debug("Transition period, not ideal for base image capture")
        return False, condition
    
    # Only capture during stable lighting conditions
    if not is_lighting_condition_stable():
        logger.debug(f"Lighting condition {condition} not stable yet, skipping base image capture")
        return False, condition
    
    # Check if we've recently captured for this lighting condition
    if condition in _base_image_timing_cache['last_capture_time']:
        last_capture = _base_image_timing_cache['last_capture_time'][condition]
        time_since_last = current_time - last_capture
        
        if time_since_last < _base_image_timing_cache['min_capture_interval']:
            logger.debug(f"Too soon since last {condition} base image capture ({time_since_last}), skipping")
            return False, condition
    
    # If we get here, it's a good time to capture
    logger.info(f"Optimal time for base image capture during {condition} conditions")
    _base_image_timing_cache['last_capture_time'][condition] = current_time
    return True, condition

def is_pure_lighting_condition():
    """
    Determine if the current time represents a "pure" lighting condition for
    reliable base image capture.
    
    Returns:
        bool: True if it's a pure day or night condition, False during transitions
    """
    condition = get_current_lighting_condition()
    detailed = _get_detailed_lighting_condition()
    
    # Only true_day or true_night are considered pure
    return detailed in ['true_day', 'true_night']

def record_base_image_capture(lighting_condition):
    """
    Record that a base image capture occurred for the given lighting condition.
    
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
    
    # Updated multipliers for better day/night separation
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
    
    Returns:
        bool: True if currently in transition period
    """
    condition = get_current_lighting_condition()
    return condition == 'transition'

def format_time_until(seconds):
    """
    Format a time difference in seconds into a human-readable string.
    
    Args:
        seconds (float): Number of seconds
        
    Returns:
        str: Formatted time string (e.g., "2h 30m" or "15m 20s")
    """
    if seconds is None:
        return "Unknown"
        
    # Handle negative values (time since)
    is_negative = seconds < 0
    seconds = abs(seconds)
    
    # Calculate hours, minutes, seconds
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    # Format based on time magnitude
    if hours > 0:
        result = f"{hours}h {minutes}m"
    elif minutes > 0:
        result = f"{minutes}m {secs}s"
    else:
        result = f"{secs}s"
        
    # Add minus sign for negative values
    if is_negative:
        result = f"{result} ago"
        
    return result

def should_generate_after_action_report():
    """
    Determine if it's time to generate an after action report.
    
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
    
    # Time-based fallback: Check when the last report was generated
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
    """Record that an after action report was generated."""
    current_time = datetime.now(pytz.timezone('America/Los_Angeles'))
    _detailed_lighting_info['last_after_action_report'] = current_time
    logger.info(f"Recorded after action report generation at {current_time}")

if __name__ == "__main__":
    # Test the timing functions
    logger.info("Testing lighting condition detection with day/night settings...")
    lighting_info = get_lighting_info()
    
    print(f"Current lighting info:")
    print(f"- Condition: {lighting_info['condition']}")
    print(f"- Detailed condition: {lighting_info['detailed_condition']}")
    print(f"- Is transition period: {lighting_info['is_transition']}")
    print(f"- Transition percentage: {lighting_info['transition_percentage']}%")
    print(f"- Is lighting condition stable: {is_lighting_condition_stable()}")
    print(f"- Is pure lighting condition: {is_pure_lighting_condition()}")
    
    print("\nTime information:")
    print(f"- Next sunrise: {lighting_info['next_sunrise']}")
    print(f"- Next sunset: {lighting_info['next_sunset']}")
    print(f"- Next true day: {lighting_info['next_true_day']}")
    print(f"- Next true night: {lighting_info['next_true_night']}")
    
    if lighting_info['countdown']['to_sunrise']:
        print(f"- Time until sunrise: {format_time_until(lighting_info['countdown']['to_sunrise'])}")
    if lighting_info['countdown']['to_sunset']:
        print(f"- Time until sunset: {format_time_until(lighting_info['countdown']['to_sunset'])}")
    if lighting_info['countdown']['to_true_day']:
        print(f"- Time until true day: {format_time_until(lighting_info['countdown']['to_true_day'])}")
    if lighting_info['countdown']['to_true_night']:
        print(f"- Time until true night: {format_time_until(lighting_info['countdown']['to_true_night'])}")
    
    print("\nDetection decisions:")
    print(f"- Should capture base image: {should_capture_base_image()}")
    print(f"- Luminance threshold multiplier: {get_luminance_threshold_multiplier()}")
    print(f"- Should generate after action report: {should_generate_after_action_report()}")
    
    print("\nTest complete - ready for integration with day/night detection settings")