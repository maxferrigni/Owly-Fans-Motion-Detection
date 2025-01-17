# File: time_utils.py

from datetime import datetime, time, timedelta
import pytz
from utilities.configs_loader import load_sunrise_sunset_data

PACIFIC_TIME = pytz.timezone("America/Los_Angeles")

def get_darkness_times():
    """
    Calculate the start and end times for darkness based on sunrise and sunset.
    Returns:
        tuple: (darkness_start, darkness_end) as datetime.time objects.
    Raises:
        ValueError: If today's sunrise/sunset data is not found.
    """
    today = datetime.now(PACIFIC_TIME).date()
    sunrise_sunset_data = load_sunrise_sunset_data()
    row = sunrise_sunset_data[sunrise_sunset_data['Date'] == today]

    if row.empty:
        raise ValueError(f"No sunrise/sunset data available for {today}")

    sunrise_time = datetime.strptime(row.iloc[0]['Sunrise'], '%H:%M').time()
    sunset_time = datetime.strptime(row.iloc[0]['Sunset'], '%H:%M').time()

    darkness_start = (datetime.combine(datetime.today(), sunset_time) + timedelta(minutes=40)).time()
    darkness_end = (datetime.combine(datetime.today(), sunrise_time) - timedelta(minutes=40)).time()

    return darkness_start, darkness_end

def is_within_allowed_hours():
    """
    Check if the current time is within the allowed darkness hours.
    Returns:
        bool: True if the current time is within darkness hours, otherwise False.
    """
    now = datetime.now(PACIFIC_TIME).time()
    darkness_start, darkness_end = get_darkness_times()
    return darkness_start <= now or now <= darkness_end

def convert_to_pacific_time(utc_time):
    """
    Convert a UTC datetime to Pacific Time.
    Args:
        utc_time (datetime): A UTC datetime object.
    Returns:
        datetime: The equivalent Pacific Time datetime object.
    """
    return utc_time.astimezone(PACIFIC_TIME)

def current_pacific_time():
    """
    Get the current time in Pacific Time.
    Returns:
        datetime: The current Pacific Time datetime object.
    """
    return datetime.now(PACIFIC_TIME)
