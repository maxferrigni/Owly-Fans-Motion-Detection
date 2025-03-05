# File: utilities/database_utils.py
# Purpose: Centralize database operations for the Owl Monitoring System
#
# March 4, 2025 Update - Version 1.1.0
# - Added support for multiple owl detection
# - Added functions to retrieve activity statistics for after action reports
# - Enhanced subscriber management for all alert types
# - Added report logging functions

import os
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
import supabase
import json
from utilities.logging_utils import get_logger

# Initialize logger
logger = get_logger()

# Load environment variables from .env file
load_dotenv()

# Retrieve Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")

# Validate credentials
if not all([SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET]):
    error_msg = "Supabase credentials are missing. Check the .env file."
    logger.error(error_msg)
    raise ValueError(error_msg)

# Initialize Supabase client
try:
    supabase_client = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {e}")
    raise

# Cache for column existence checks to avoid repeated queries
_column_cache = {}

def get_table_columns(table_name):
    """
    Get the column names for a table to check if columns exist.
    
    Args:
        table_name (str): Table name to check
        
    Returns:
        list: List of column names
    """
    # Check cache first
    if table_name in _column_cache:
        return _column_cache[table_name]
        
    try:
        # This is a simple way to get column info - might need adjustment based on Supabase API
        # This selects a single row to examine its structure
        response = supabase_client.table(table_name).select("*").limit(1).execute()
        
        if hasattr(response, 'data') and len(response.data) > 0:
            # Get column names from the first row
            columns = list(response.data[0].keys())
            # Cache the result
            _column_cache[table_name] = columns
            return columns
        else:
            # If no data, try to get table definition instead
            try:
                # This is a PostgreSQL-specific approach that might work with Supabase
                # The query gets column information from the information_schema
                query = f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'"
                response = supabase_client.rpc('execute_sql', {'query': query}).execute()
                
                if hasattr(response, 'data') and len(response.data) > 0:
                    columns = [row.get('column_name') for row in response.data]
                    # Cache the result
                    _column_cache[table_name] = columns
                    return columns
            except Exception as inner_e:
                logger.debug(f"Could not get column info from schema: {inner_e}")
            
            # If all else fails, return empty list
            _column_cache[table_name] = []
            return []
            
    except Exception as e:
        logger.error(f"Error getting column info for {table_name}: {e}")
        _column_cache[table_name] = []
        return []

def check_column_exists(table_name, column_name):
    """
    Check if a specific column exists in a table.
    
    Args:
        table_name (str): Table name to check
        column_name (str): Column name to check
        
    Returns:
        bool: True if column exists, False otherwise
    """
    # Check cache for combined key
    cache_key = f"{table_name}.{column_name}"
    if cache_key in _column_cache:
        return _column_cache[cache_key]
        
    try:
        # Get all columns for this table
        columns = get_table_columns(table_name)
        
        # Check if the requested column exists
        exists = column_name in columns
        
        # Cache the result
        _column_cache[cache_key] = exists
        
        return exists
    except Exception as e:
        logger.error(f"Error checking if column {column_name} exists in {table_name}: {e}")
        _column_cache[cache_key] = False
        return False

def get_subscribers(notification_type=None, owl_location=None):
    """
    Get subscribers based on notification type and preferences.
    
    Args:
        notification_type (str, optional): Type of notification ("email", "sms", or "email_to_text")
        owl_location (str, optional): Type of owl detection for filtering
        
    Returns:
        list: List of subscriber records
    """
    try:
        # Start with base query - always select first
        query = supabase_client.table("subscribers").select("*")
        
        # Check if the columns exist before filtering
        column_info = get_table_columns("subscribers")
        
        # Only filter by notification_type if the column exists
        if notification_type and "notification_type" in column_info:
            query = query.eq("notification_type", notification_type)
        
        # Only filter by owl_locations if the column exists
        # In v1.1.0, we now handle the new alert types (Two Owls, etc.)
        if owl_location and "owl_locations" in column_info:
            # For backward compatibility, also check old owl location types
            if owl_location in ["Two Owls", "Two Owls In Box", "Eggs Or Babies"]:
                # For new alert types, include subscribers who have the base type
                base_location = "Owl In Box" if "In Box" in owl_location else "Owl In Area"
                query = query.or_(f"owl_locations.ilike.%{owl_location}%,owl_locations.ilike.%{base_location}%")
            else:
                # Original behavior for standard alert types
                query = query.ilike("owl_locations", f"%{owl_location}%")
        
        # Execute the query
        response = query.execute()
        
        # Check if response has data and return
        if hasattr(response, 'data'):
            logger.info(f"Found {len(response.data)} subscribers for {notification_type} alerts")
            return response.data
        else:
            logger.warning("No data attribute in Supabase response")
            return []

    except Exception as e:
        logger.error(f"Error getting subscribers from Supabase: {e}")
        # Return empty list instead of None to avoid NoneType errors
        return []

def get_owl_activity_logs(start_time=None, end_time=None, limit=100, camera_name=None):
    """
    Get owl activity logs within a time range.
    Enhanced in v1.1.0 to support after action reports.
    
    Args:
        start_time (datetime, optional): Start time for filtering logs
        end_time (datetime, optional): End time for filtering logs
        limit (int): Maximum number of logs to retrieve
        camera_name (str, optional): Filter by specific camera
        
    Returns:
        list: List of activity log records
    """
    try:
        # Start with base query - always select first
        query = supabase_client.table("owl_activity_log").select("*")
        
        # Filter by camera if provided
        if camera_name:
            query = query.eq("camera", camera_name)
        
        # Filter by time range if provided
        if start_time:
            # Convert to ISO format for Supabase
            start_time_iso = start_time.isoformat()
            query = query.gte("created_at", start_time_iso)
            
        if end_time:
            # Convert to ISO format for Supabase
            end_time_iso = end_time.isoformat()
            query = query.lte("created_at", end_time_iso)
        
        # Order by timestamp descending and limit results
        query = query.order("created_at", desc=True).limit(limit)
        
        # Execute query
        response = query.execute()
        
        # Check if response has data
        if hasattr(response, 'data'):
            return response.data
        else:
            logger.warning("No data attribute in Supabase response")
            return []
            
    except Exception as e:
        logger.error(f"Error getting owl activity logs: {e}")
        return []

def get_activity_stats(start_time=None, hours=12):
    """
    Get activity statistics for after action reports.
    New in v1.1.0 to support after action reporting.
    
    Args:
        start_time (datetime, optional): Start time for statistics, defaults to hours ago
        hours (int): Number of hours to look back if start_time not provided
        
    Returns:
        dict: Statistics about owl activity during the period
    """
    try:
        # If no start time provided, calculate based on hours
        if not start_time:
            end_time = datetime.now(pytz.utc)
            start_time = end_time - timedelta(hours=hours)
        else:
            end_time = datetime.now(pytz.utc)
            
        # Get logs for the period
        logs = get_owl_activity_logs(start_time, end_time, limit=1000)
        
        # Initialize counters
        stats = {
            "Owl In Area": 0,
            "Owl On Box": 0,
            "Owl In Box": 0,
            "Two Owls": 0,
            "Two Owls In Box": 0,
            "Eggs Or Babies": 0,
            "total_detections": 0,
            "period_start": start_time.isoformat(),
            "period_end": end_time.isoformat(),
            "duration_hours": (end_time - start_time).total_seconds() / 3600
        }
        
        # Process logs to count detections
        for log in logs:
            if log.get("owl_in_area") == 1:
                stats["Owl In Area"] += 1
                stats["total_detections"] += 1
                
            if log.get("owl_on_box") == 1:
                stats["Owl On Box"] += 1
                stats["total_detections"] += 1
                
            if log.get("owl_in_box") == 1:
                stats["Owl In Box"] += 1
                stats["total_detections"] += 1
            
            # Check for multi-owl detections (added in v1.1.0)
            if check_column_exists("owl_activity_log", "two_owls") and log.get("two_owls") == 1:
                stats["Two Owls"] += 1
                stats["total_detections"] += 1
                
            if check_column_exists("owl_activity_log", "two_owls_in_box") and log.get("two_owls_in_box") == 1:
                stats["Two Owls In Box"] += 1
                stats["total_detections"] += 1
                
            if check_column_exists("owl_activity_log", "eggs_or_babies") and log.get("eggs_or_babies") == 1:
                stats["Eggs Or Babies"] += 1
                stats["total_detections"] += 1
                
        return stats
        
    except Exception as e:
        logger.error(f"Error getting activity statistics: {e}")
        return {
            "error": str(e),
            "total_detections": 0,
            "period_start": start_time.isoformat() if start_time else None,
            "period_end": datetime.now(pytz.utc).isoformat()
        }

def log_after_action_report(report_data):
    """
    Log after action report generation to Supabase.
    New in v1.1.0 to track report generation.
    
    Args:
        report_data (dict): Report data including statistics
        
    Returns:
        dict or None: The created log entry or None if failed
    """
    try:
        # Check if the reports table exists
        if not check_column_exists("reports", "created_at"):
            logger.warning("Reports table doesn't exist or is missing required columns")
            
            # Try to create the table if it doesn't exist
            try:
                # This is a simplistic approach - in a real system, you'd manage migrations properly
                create_table_query = """
                CREATE TABLE IF NOT EXISTS reports (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    report_type TEXT,
                    recipient_count INTEGER,
                    start_time TIMESTAMPTZ,
                    end_time TIMESTAMPTZ,
                    total_detections INTEGER,
                    statistics JSONB,
                    report_url TEXT
                );
                """
                supabase_client.rpc('execute_sql', {'query': create_table_query}).execute()
                logger.info("Created reports table")
            except Exception as e:
                logger.error(f"Failed to create reports table: {e}")
                return None
                
        # Prepare log entry
        now = datetime.now(pytz.utc)
        log_entry = {
            "created_at": now.isoformat(),
            "report_type": report_data.get("report_type", "after_action"),
            "recipient_count": report_data.get("recipient_count", 0),
            "start_time": report_data.get("period_start"),
            "end_time": report_data.get("period_end"),
            "total_detections": report_data.get("total_detections", 0),
            "statistics": json.dumps(report_data.get("statistics", {})),
            "report_url": report_data.get("report_url")
        }
        
        # Insert into Supabase
        response = supabase_client.table("reports").insert(log_entry).execute()
        
        if hasattr(response, 'data') and response.data and len(response.data) > 0:
            logger.info(f"After action report logged successfully")
            return response.data[0]
        else:
            logger.error("Failed to log after action report")
            return None
            
    except Exception as e:
        logger.error(f"Error logging after action report: {e}")
        return None

def get_recent_reports(limit=10):
    """
    Get recent after action reports.
    New in v1.1.0 to support the reports interface.
    
    Args:
        limit (int): Maximum number of reports to retrieve
        
    Returns:
        list: List of report records
    """
    try:
        # Check if reports table exists
        if not check_column_exists("reports", "created_at"):
            logger.warning("Reports table doesn't exist or is missing required columns")
            return []
            
        # Query reports
        response = supabase_client.table("reports").select("*").order("created_at", desc=True).limit(limit).execute()
        
        if hasattr(response, 'data'):
            return response.data
        else:
            logger.warning("No data attribute in Supabase response")
            return []
            
    except Exception as e:
        logger.error(f"Error getting recent reports: {e}")
        return []

def save_custom_threshold(camera_name, threshold_value):
    """
    Save a custom confidence threshold for a specific camera.
    
    Args:
        camera_name (str): Name of the camera
        threshold_value (float): The confidence threshold value
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if camera_settings table exists
        column_info = get_table_columns("camera_settings")
        if not column_info:
            logger.warning("camera_settings table does not exist or has no columns")
            return False
            
        # Check if a record exists for this camera
        query = supabase_client.table("camera_settings").select("*").eq("camera_name", camera_name)
        response = query.execute()
        
        if hasattr(response, 'data') and len(response.data) > 0:
            # Update existing record
            update_data = {
                "owl_confidence_threshold": threshold_value,
                "last_updated": "now()"
            }
            
            supabase_client.table("camera_settings").update(update_data).eq("camera_name", camera_name).execute()
            logger.info(f"Updated confidence threshold for {camera_name} to {threshold_value}%")
        else:
            # Insert new record
            insert_data = {
                "camera_name": camera_name,
                "owl_confidence_threshold": threshold_value,
                "created_at": "now()",
                "last_updated": "now()"
            }
            
            supabase_client.table("camera_settings").insert(insert_data).execute()
            logger.info(f"Created new confidence threshold for {camera_name}: {threshold_value}%")
            
        return True
        
    except Exception as e:
        logger.error(f"Error saving custom threshold for {camera_name}: {e}")
        return False

def get_custom_thresholds():
    """
    Get all custom confidence thresholds stored in the database.
    
    Returns:
        dict: Camera name to threshold value mapping
    """
    try:
        # Check if camera_settings table exists
        column_info = get_table_columns("camera_settings")
        if not column_info:
            logger.warning("camera_settings table doesn't exist or has no columns")
            return {}
            
        # Query camera settings table
        response = supabase_client.table("camera_settings").select("*").execute()
        
        # Process results
        thresholds = {}
        if hasattr(response, 'data'):
            for row in response.data:
                if "camera_name" in row and "owl_confidence_threshold" in row:
                    thresholds[row["camera_name"]] = row["owl_confidence_threshold"]
                    
        return thresholds
        
    except Exception as e:
        logger.error(f"Error getting custom thresholds: {e}")
        return {}

def get_multiple_owl_settings():
    """
    Get settings for multiple owl detection.
    New in v1.1.0 to support multiple owl detection.
    
    Returns:
        dict: Settings for multiple owl detection
    """
    try:
        # Check if settings table exists and has multiple_owl_settings column
        if not check_column_exists("settings", "multiple_owl_settings"):
            logger.warning("multiple_owl_settings not found in settings table")
            # Return default settings
            return {
                "enabled": True,
                "confidence_boost": 10.0,  # Boost confidence score for multiple owls
                "minimum_confidence": 50.0  # Minimum base confidence to consider multiple owls
            }
            
        # Query settings
        response = supabase_client.table("settings").select("multiple_owl_settings").limit(1).execute()
        
        if hasattr(response, 'data') and len(response.data) > 0 and "multiple_owl_settings" in response.data[0]:
            settings_json = response.data[0]["multiple_owl_settings"]
            
            # Parse JSON if it's a string
            if isinstance(settings_json, str):
                try:
                    settings = json.loads(settings_json)
                    return settings
                except json.JSONDecodeError:
                    logger.error("Invalid JSON in multiple_owl_settings")
            elif isinstance(settings_json, dict):
                return settings_json
                
        # Return default settings if no valid settings found
        return {
            "enabled": True,
            "confidence_boost": 10.0,
            "minimum_confidence": 50.0
        }
            
    except Exception as e:
        logger.error(f"Error getting multiple owl settings: {e}")
        # Return default settings on error
        return {
            "enabled": True,
            "confidence_boost": 10.0,
            "minimum_confidence": 50.0
        }

if __name__ == "__main__":
    # Test database functions
    try:
        logger.info("Testing database utility functions...")
        
        # Test get_subscribers with new alert types
        email_subscribers = get_subscribers(notification_type="email", owl_location="Two Owls In Box")
        logger.info(f"Found {len(email_subscribers) if email_subscribers else 0} email subscribers for Two Owls In Box")
        
        # Test activity stats
        hours_ago = 24
        stats = get_activity_stats(hours=hours_ago)
        logger.info(f"Found {stats.get('total_detections', 0)} detections in the last {hours_ago} hours")
        logger.info(f"Owl In Box detections: {stats.get('Owl In Box', 0)}")
        logger.info(f"Owl On Box detections: {stats.get('Owl On Box', 0)}")
        logger.info(f"Owl In Area detections: {stats.get('Owl In Area', 0)}")
        
        # Test recent reports
        reports = get_recent_reports(5)
        logger.info(f"Found {len(reports)} recent reports")
        
        # Test multiple owl settings
        owl_settings = get_multiple_owl_settings()
        logger.info(f"Multiple owl detection enabled: {owl_settings.get('enabled', False)}")
        
        logger.info("Database utility tests complete")
    except Exception as e:
        logger.error(f"Database test failed: {e}")
        raise