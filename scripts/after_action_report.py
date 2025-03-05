# File: scripts/after_action_report.py
# Purpose: Generate and send after action reports at day/night transitions
#
# Added in v1.1.0 - March 4, 2025
# - Generates summary reports of owl activity at day/night transitions
# - Includes alert counts, duration statistics, and activity summaries
# - Sends reports to all subscribers via email

import os
import datetime
import pytz
import time
import html
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import smtplib
import json

# Import utilities
from utilities.logging_utils import get_logger
from utilities.constants import ALERT_PRIORITIES, BASE_DIR
from utilities.time_utils import record_after_action_report, get_lighting_info
from utilities.database_utils import get_subscribers

# Initialize logger
logger = get_logger()

# Load environment variables
load_dotenv()

# Email credentials from environment variables
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "owlyfans01@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Google App Password

# Ensure reports directory exists
REPORTS_DIR = os.path.join(BASE_DIR, "20_Local_Files", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

def format_duration(minutes, seconds):
    """
    Format duration into a readable string.
    
    Args:
        minutes (int): Number of minutes
        seconds (int): Number of seconds
        
    Returns:
        str: Formatted duration string
    """
    if minutes == 0 and seconds == 0:
        return "None"
    elif minutes == 0:
        return f"{seconds} seconds"
    elif seconds == 0:
        return f"{minutes} minute{'s' if minutes > 1 else ''}"
    else:
        return f"{minutes} minute{'s' if minutes > 1 else ''}, {seconds} seconds"

def generate_html_report(stats, session_type="Day-to-Night Transition"):
    """
    Generate an HTML after action report from the provided statistics.
    
    Args:
        stats (dict): Alert statistics from alert_manager.get_alert_statistics()
        session_type (str): Type of session/transition being reported
        
    Returns:
        str: HTML content of the report
    """
    # Get current time in Pacific timezone
    pacific = pytz.timezone('America/Los_Angeles')
    now = datetime.datetime.now(pacific)
    
    # Format time range for the report title
    session_start = None
    if stats.get('session_start'):
        try:
            session_start = datetime.datetime.fromisoformat(stats['session_start'])
            session_start = session_start.astimezone(pacific)
        except Exception as e:
            logger.error(f"Error parsing session start time: {e}")
    
    session_end = now
    if stats.get('session_end'):
        try:
            session_end = datetime.datetime.fromisoformat(stats['session_end'])
            session_end = session_end.astimezone(pacific)
        except Exception as e:
            logger.error(f"Error parsing session end time: {e}")
    
    # Format time range
    if session_start:
        time_range = f"{session_start.strftime('%B %d, %Y %I:%M %p')} to {session_end.strftime('%I:%M %p')}"
    else:
        time_range = f"Ending at {session_end.strftime('%B %d, %Y %I:%M %p')}"
    
    # Get alert counts and durations
    alert_counts = stats.get('alert_counts', {})
    alert_durations = stats.get('alert_durations', {})
    total_alerts = stats.get('total_alerts', 0)
    
    # Create HTML content
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Owl Monitoring - After Action Report</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }}
            h1, h2, h3 {{
                color: #2c3e50;
            }}
            .header {{
                border-bottom: 2px solid #3498db;
                padding-bottom: 10px;
                margin-bottom: 20px;
            }}
            .summary-box {{
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                padding: 15px;
                margin-bottom: 20px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }}
            th, td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            th {{
                background-color: #f2f2f2;
            }}
            tr:hover {{
                background-color: #f5f5f5;
            }}
            .alert-highlight {{
                font-weight: bold;
                color: #e74c3c;
            }}
            .footer {{
                margin-top: 30px;
                border-top: 1px solid #ddd;
                padding-top: 10px;
                font-size: 0.9em;
                color: #7f8c8d;
            }}
            .chart {{
                width: 100%;
                height: 30px;
                background-color: #ecf0f1;
                margin-bottom: 5px;
                position: relative;
            }}
            .chart-bar {{
                height: 100%;
                background-color: #3498db;
                position: absolute;
                left: 0;
                top: 0;
            }}
            .chart-label {{
                position: absolute;
                right: 5px;
                top: 5px;
                font-size: 0.8em;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Owl Monitoring After Action Report</h1>
            <h3>{session_type} - {time_range}</h3>
        </div>
        
        <div class="summary-box">
            <h2>Session Summary</h2>
            <p>Total owl activity alerts during this period: <span class="alert-highlight">{total_alerts}</span></p>
            <p>Type of transition: <strong>{session_type}</strong></p>
            <p>Report generated: {now.strftime('%B %d, %Y %I:%M:%S %p')}</p>
        </div>
        
        <h2>Alert Breakdown</h2>
        <table>
            <tr>
                <th>Alert Type</th>
                <th>Count</th>
                <th>Duration</th>
                <th>Priority</th>
            </tr>
    """
    
    # Sort alert types by priority
    sorted_alerts = sorted(
        ALERT_PRIORITIES.items(), 
        key=lambda x: x[1], 
        reverse=True
    )
    
    # Add rows for each alert type
    max_count = max(alert_counts.values()) if alert_counts and alert_counts.values() else 1
    for alert_type, priority in sorted_alerts:
        count = alert_counts.get(alert_type, 0)
        duration = alert_durations.get(alert_type, {"minutes": 0, "seconds": 0})
        
        # Calculate percentage width for chart bar
        percent = (count / max_count) * 100 if max_count > 0 else 0
        
        # Format duration
        duration_text = format_duration(duration.get("minutes", 0), duration.get("seconds", 0))
        
        # Add row with chart
        html_content += f"""
            <tr>
                <td>{alert_type}</td>
                <td>
                    <div class="chart">
                        <div class="chart-bar" style="width: {percent}%;"></div>
                        <div class="chart-label">{count}</div>
                    </div>
                </td>
                <td>{duration_text}</td>
                <td>{priority}/6</td>
            </tr>
        """
    
    # Close table and add additional sections
    html_content += """
        </table>
        
        <h2>Activity Insights</h2>
    """
    
    # Add activity insights based on data
    if total_alerts == 0:
        html_content += "<p>No owl activity was detected during this period.</p>"
    else:
        # Find the most common alert type
        most_common = max(alert_counts.items(), key=lambda x: x[1]) if alert_counts else None
        
        if most_common:
            html_content += f"""
                <p>The most common owl activity was <strong>{most_common[0]}</strong> with {most_common[1]} alerts.</p>
            """
        
        # Check for multiple owl alerts
        two_owl_count = alert_counts.get("Two Owls", 0) + alert_counts.get("Two Owls In Box", 0)
        if two_owl_count > 0:
            html_content += f"""
                <p class="alert-highlight">Multiple owls were detected {two_owl_count} times during this period!</p>
            """
            
        # Calculate total activity time
        total_minutes = sum(d.get("minutes", 0) for d in alert_durations.values())
        total_seconds = sum(d.get("seconds", 0) for d in alert_durations.values())
        # Convert excess seconds to minutes
        extra_minutes, remaining_seconds = divmod(total_seconds, 60)
        total_minutes += extra_minutes
        
        html_content += f"""
            <p>Total activity time: {format_duration(total_minutes, remaining_seconds)}</p>
        """
    
    # Add footer
    html_content += """
        <div class="footer">
            <p>This report was automatically generated by the Owl Monitoring System.</p>
            <p>For more information and live camera feeds, visit <a href="http://www.owly-fans.com">Owly-Fans.com</a></p>
        </div>
    </body>
    </html>
    """
    
    return html_content

def save_report_to_file(html_content, session_type="DayNight"):
    """
    Save the report to a local HTML file.
    
    Args:
        html_content (str): HTML content of the report
        session_type (str): Type of session for filename
        
    Returns:
        str: Path to the saved file
    """
    try:
        # Generate filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        session_type_clean = session_type.replace(" ", "").replace("-", "To")
        filename = f"OwlReport_{session_type_clean}_{timestamp}.html"
        
        # Full path to save file
        file_path = os.path.join(REPORTS_DIR, filename)
        
        # Save the file
        with open(file_path, 'w') as f:
            f.write(html_content)
            
        logger.info(f"Report saved to {file_path}")
        return file_path
        
    except Exception as e:
        logger.error(f"Error saving report to file: {e}")
        return None

def send_report_to_subscribers(html_content, report_file, session_type="Day-to-Night Transition"):
    """
    Send the report via email to all subscribers.
    
    Args:
        html_content (str): HTML content of the report
        report_file (str): Path to the saved report file
        session_type (str): Type of session for email subject
        
    Returns:
        dict: Information about the email sending results
    """
    try:
        # Check if email alerts are enabled
        if os.environ.get('OWL_EMAIL_ALERTS', 'True').lower() != 'true':
            logger.info("Email alerts are disabled, skipping report distribution")
            return {"success": False, "error": "Email alerts disabled", "recipient_count": 0}
            
        # Check if after action reports are enabled
        if os.environ.get('OWL_AFTER_ACTION_REPORTS', 'True').lower() != 'true':
            logger.info("After action reports are disabled, skipping report distribution")
            return {"success": False, "error": "After action reports disabled", "recipient_count": 0}
        
        # Get all email subscribers
        subscribers = get_subscribers(notification_type="email")
        
        if not subscribers:
            logger.warning("No email subscribers found for after action report")
            return {"success": False, "error": "No subscribers", "recipient_count": 0}
            
        # Prepare email
        subject = f"Owl Monitoring - After Action Report ({session_type})"
        
        # Create email server connection
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            
            # Send to each subscriber
            sent_count = 0
            for subscriber in subscribers:
                to_email = subscriber.get('email')
                if not to_email:
                    continue
                    
                recipient_name = subscriber.get('name', '')
                
                # Create personalized message
                msg = MIMEMultipart()
                msg["From"] = EMAIL_ADDRESS
                msg["To"] = to_email
                msg["Subject"] = subject
                
                # Personalize the greeting if name is available
                greeting = f"Hello {recipient_name}," if recipient_name else "Hello,"
                
                # Personalized intro
                personalized_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                </head>
                <body>
                    <p>{greeting}</p>
                    <p>Please find attached the latest after action report for owl activity during the recent {session_type.lower()}.</p>
                    <p>This report summarizes all owl activity detected during the session.</p>
                </body>
                </html>
                """
                
                # Create alternative parts
                msg.attach(MIMEText(personalized_html, "html"))
                
                # Add the full report as the primary body
                msg.attach(MIMEText(html_content, "html"))
                
                # Send email
                server.send_message(msg)
                sent_count += 1
                logger.debug(f"Report sent to {to_email}")
                
            # Log results
            logger.info(f"After action report sent to {sent_count} subscribers")
            return {
                "success": True, 
                "recipient_count": sent_count,
                "report_file": report_file,
                "session_type": session_type
            }
                
    except Exception as e:
        logger.error(f"Error sending report to subscribers: {e}")
        return {"success": False, "error": str(e), "recipient_count": 0}

def determine_session_type():
    """
    Determine the type of session for the report.
    
    Returns:
        str: Session type description
    """
    try:
        # Get current lighting info
        lighting_info = get_lighting_info()
        current_condition = lighting_info.get('condition')
        previous_condition = lighting_info.get('previous_condition')
        
        # Determine transition type
        if previous_condition == 'transition' and current_condition == 'day':
            return "Night to Day Transition"
        elif previous_condition == 'transition' and current_condition == 'night':
            return "Day to Night Transition"
        elif previous_condition == 'day' and current_condition == 'night':
            return "Day to Night Transition"
        elif previous_condition == 'night' and current_condition == 'day':
            return "Night to Day Transition"
        else:
            # Default or manual report
            return "Monitoring Session Report"
            
    except Exception as e:
        logger.error(f"Error determining session type: {e}")
        return "Monitoring Session Report"

def generate_after_action_report(alert_stats, is_manual=False):
    """
    Generate and send an after action report.
    
    Args:
        alert_stats (dict): Statistics from alert_manager.get_alert_statistics()
        is_manual (bool): Whether this was manually triggered
        
    Returns:
        dict: Results of the operation
    """
    try:
        # Determine session type
        session_type = determine_session_type()
        if is_manual:
            session_type = "Manual Report"
            
        # Generate HTML content
        html_content = generate_html_report(alert_stats, session_type)
        
        # Save to file
        report_file = save_report_to_file(html_content, session_type)
        
        if report_file:
            # Send to subscribers
            result = send_report_to_subscribers(html_content, report_file, session_type)
            
            # Record that we generated a report
            record_after_action_report()
            
            # Return combined results
            return {
                "success": result.get("success", False),
                "report_file": report_file,
                "recipient_count": result.get("recipient_count", 0),
                "session_type": session_type,
                "total_alerts": alert_stats.get("total_alerts", 0),
                "timestamp": datetime.datetime.now().isoformat()
            }
        else:
            logger.error("Failed to save report to file")
            return {"success": False, "error": "Failed to save report"}
            
    except Exception as e:
        logger.error(f"Error generating after action report: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    # Test the functionality
    try:
        logger.info("Testing after action report generation...")
        
        # Create test alert statistics
        test_stats = {
            "alert_counts": {
                "Owl In Area": 5,
                "Owl On Box": 3,
                "Owl In Box": 2,
                "Two Owls": 1,
                "Two Owls In Box": 0,
                "Eggs Or Babies": 0
            },
            "alert_durations": {
                "Owl In Area": {"minutes": 15, "seconds": 30},
                "Owl On Box": {"minutes": 8, "seconds": 45},
                "Owl In Box": {"minutes": 5, "seconds": 10},
                "Two Owls": {"minutes": 2, "seconds": 20},
                "Two Owls In Box": {"minutes": 0, "seconds": 0},
                "Eggs Or Babies": {"minutes": 0, "seconds": 0}
            },
            "total_alerts": 11,
            "session_start": datetime.datetime.now().replace(hour=18, minute=0).isoformat(),
            "session_end": datetime.datetime.now().isoformat()
        }
        
        # Generate test report
        result = generate_after_action_report(test_stats, is_manual=True)
        
        if result.get("success"):
            logger.info(f"Test report successfully generated: {result.get('report_file')}")
            logger.info(f"Sent to {result.get('recipient_count')} subscribers")
        else:
            logger.error(f"Test report generation failed: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise