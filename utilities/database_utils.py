# File: utilities/database_utils.py
# Purpose: Centralize database operations for the Owl Monitoring System
#
# March 5, 2025 Update - Version 1.2.0
# - Added functions for report tracking in database
# - Added admin subscriber identification 
# - Streamlined error handling and removed redundant checks

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
if not all([SUPABASE_URL, SUPABASE_KEY]):
    logger.error("Supabase credentials are missing. Check the .env file.")
    raise ValueError("Supabase credentials are missing")

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
        # This selects a single row to examine its structure
        response = supabase_client.table(table_name).select("*").limit(1).execute()
        
        if hasattr(response, 'data') and len(response.data) > 0:
            # Get column names from the first row
            columns = list(response.data[0].keys())
            _column_cache[table_name] = columns
            return columns
        
        # If no data, try to get table definition
        query = f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'"
        response = supabase_client.rpc('execute_sql', {'query': query}).execute()
        
        if hasattr(response, 'data') and len(response.data) > 0:
            columns = [row.get('column_name') for row in response.data]
            _column_cache[table_name] = columns
            return columns
            
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
        
    # Get all columns for this table
    columns = get_table_columns(table_name)
    
    # Check if the requested column exists
    exists = column_name in columns
    
    # Cache the result
    _column_cache[cache_key] = exists
    
    return exists

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
        # Start with base query
        query = supabase_client.table("subscribers").select("*")
        
        # Only filter by notification_type if the column exists
        if notification_type and check_column_exists("subscribers", "notification_type"):
            query = query.eq("notification_type", notification_type)
        
        # Only filter by owl_locations if the column exists
        if owl_location and check_column_exists("subscribers", "owl_locations"):
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
        
        if hasattr(response, 'data'):
            logger.info(f"Found {len(response.data)} subscribers for {notification_type} alerts")
            return response.data
        return []
    except Exception as e:
        logger.error(f"Error getting subscribers: {e}")
        return []

def get_admin_subscribers():
    """
    Get subscribers marked as Owly Admins.
    Added in v1.2.0 for admin notification system.
    
    Returns:
        list: List of admin subscriber records
    """
    try:
        # Check if the is_admin column exists
        if not check_column_exists("subscribers", "is_admin"):
            logger.warning("is_admin column does not exist in subscribers table")
            # Fall back to a specific admin email if column doesn't exist
            return [{"email": "maxferrigni@gmail.com", "name": "Max Ferrigni"}]
        
        # Query for admin subscribers
        response = supabase_client.table("subscribers").select("*").eq("is_admin", True).execute()
        
        if hasattr(response, 'data') and response.data:
            logger.info(f"Found {len(response.data)} admin subscribers")
            return response.data
            
        # If no admins found, fall back to a specific admin
        logger.warning("No admin subscribers found, using default admin")
        return [{"email": "maxferrigni@gmail.com", "name": "Max Ferrigni"}]
        
    except Exception as e:
        logger.error(f"Error getting admin subscribers: {e}")
        # Fall back to a specific admin email on error
        return [{"email": "maxferrigni@gmail.com", "name": "Max Ferrigni"}]

def get_owl_activity_logs(start_time=None, end_time=None, limit=100, camera_name=None):
    """
    Get owl activity logs within a time range.
    
    Args:
        start_time (datetime, optional): Start time for filtering logs
        end_time (datetime, optional): End time for filtering logs
        limit (int): Maximum number of logs to retrieve
        camera_name (str, optional): Filter by specific camera
        
    Returns:
        list: List of activity log records
    """
    try:
        # Start with base query
        query = supabase_client.table("owl_activity_log").select("*")
        
        # Filter by camera if provided
        if camera_name:
            query = query.eq("camera", camera_name)
        
        # Filter by time range if provided
        if start_time:
            query = query.gte("created_at", start_time.isoformat())
            
        if end_time:
            query = query.lte("created_at", end_time.isoformat())
        
        # Order by timestamp descending and limit results
        query = query.order("created_at", desc=True).limit(limit)
        
        # Execute query
        response = query.execute()
        
        if hasattr(response, 'data'):
            return response.data
        return []
    except Exception as e:
        logger.error(f"Error getting owl activity logs: {e}")
        return []

def get_activity_stats(start_time=None, hours=12):
    """
    Get activity statistics for after action reports.
    
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
            
            # Check for multi-owl detections
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

def log_report_to_database(report_data):
    """
    Log report generation to database. 
    Added in v1.2.0 for report tracking.
    
    Args:
        report_data (dict): Report metadata including:
            - report_id: Unique identifier
            - report_type: "after_action", "daily", "manual"
            - is_manual: Boolean indicating manual generation
            - recipient_count: Number of email recipients
            - summary_data: JSON string of report statistics
            - start_timestamp: Start of reporting period
            - end_timestamp: End of reporting period
        
    Returns:
        dict or None: The created log entry or None if failed
    """
    try:
        # Check if reports table exists with required columns
        if not check_column_exists("reports", "report_id"):
            logger.warning("reports table doesn't exist or missing report_id column")
            return None
            
        # Ensure timestamps are in ISO format
        if 'created_at' not in report_data:
            report_data['created_at'] = datetime.now(pytz.utc).isoformat()
            
        # Insert report into database
        response = supabase_client.table("reports").insert(report_data).execute()
        
        if hasattr(response, 'data') and len(response.data) > 0:
            logger.info(f"Report {report_data.get('report_id')} logged successfully")
            return response.data[0]
        
        logger.error("Failed to log report to database")
        return None
    except Exception as e:
        logger.error(f"Error logging report to database: {e}")
        return None

def get_last_report_time():
    """
    Get the creation time of the most recent report.
    Added in v1.2.0 for report scheduling.
    
    Returns:
        str or None: ISO timestamp of the last report or None if no reports
    """
    try:
        # Check if reports table exists
        if not check_column_exists("reports", "created_at"):
            logger.warning("reports table doesn't exist or missing created_at column")
            return None
            
        # Query for the most recent report
        response = supabase_client.table("reports").select("created_at").order("created_at", desc=True).limit(1).execute()
        
        if hasattr(response, 'data') and len(response.data) > 0:
            return response.data[0]['created_at']
        return None
    except Exception as e:
        logger.error(f"Error getting last report time: {e}")
        return None

def get_recent_reports(limit=20):
    """
    Get recent reports for display in the UI.
    Added in v1.2.0 for report history view.
    
    Args:
        limit (int): Maximum number of reports to retrieve
        
    Returns:
        list: List of recent report records
    """
    try:
        # Check if reports table exists
        if not check_column_exists("reports", "created_at"):
            logger.warning("reports table doesn't exist or missing created_at column")
            return []
            
        # Query for recent reports
        response = supabase_client.table("reports").select("*").order("created_at", desc=True).limit(limit).execute()
        
        if hasattr(response, 'data'):
            return response.data
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
        if not check_column_exists("camera_settings", "camera_name"):
            logger.warning("camera_settings table does not exist or has no columns")
            return False
            
        # Check if a record exists for this camera
        response = supabase_client.table("camera_settings").select("*").eq("camera_name", camera_name).execute()
        
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
        if not check_column_exists("camera_settings", "camera_name"):
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

if __name__ == "__main__":
    # Test database functions
    try:
        logger.info("Testing database utility functions...")
        
        # Test report tracking functions
        test_report_id = f"OWLR-{datetime.now().strftime('%Y%m%d%H%M%S')}-TEST"
        
        # Create test report data
        test_report = {
            "report_id": test_report_id,
            "report_type": "manual",
            "is_manual": True,
            "recipient_count": 1,
            "summary_data": json.dumps({"total_alerts": 5, "alert_counts": {"Owl In Box": 3, "Owl On Box": 2}}),
            "start_timestamp": (datetime.now() - timedelta(hours=24)).isoformat(),
            "end_timestamp": datetime.now().isoformat()
        }
        
        # Test logging report
        report_result = log_report_to_database(test_report)
        if report_result:
            logger.info(f"Successfully logged test report: {test_report_id}")
        else:
            logger.warning("Failed to log test report")
            
        # Test retrieving last report time
        last_time = get_last_report_time()
        logger.info(f"Last report time: {last_time}")
        
        # Test retrieving recent reports
        recent_reports = get_recent_reports(5)
        logger.info(f"Found {len(recent_reports)} recent reports")
        
        # Test admin subscribers
        admins = get_admin_subscribers()
        logger.info(f"Found {len(admins)} admin subscribers")
        for admin in admins:
            logger.info(f"Admin: {admin.get('name')} ({admin.get('email')})")
        
        logger.info("Database utility tests complete")
    except Exception as e:
        logger.error(f"Database test failed: {e}")
        raise