# File: _front_end_app.py
# Purpose: Main application window for the Owl Monitoring System
#
# March 6, 2025 Update - Version 1.2.1
# - Reduced transition window to 30 minutes
# - Added lighting info panel with sunrise/sunset countdowns
# - Improved base image capture during transitions
# - Major refactoring to make code more modular

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import sys
import json
from datetime import datetime, timedelta
import pytz

# Add parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Import utilities and modules
from utilities.constants import SCRIPTS_DIR, ensure_directories_exist, VERSION, BASE_DIR
from utilities.logging_utils import get_logger
from utilities.alert_manager import AlertManager
from utilities.time_utils import get_current_lighting_condition

# Import GUI panels - now including all panel components
from _front_end_panels import (
    LogWindow, 
    StatusPanel, 
    LightingInfoPanel,
    ControlPanel,
    ReportsPanel
)

# Import remaining components
from motion_detection_settings import MotionDetectionSettings
from test_interface import TestInterface
from capture_base_images import notify_transition_period

# Import after action report generator
from after_action_report import generate_after_action_report

class OwlApp:
    def __init__(self, root):
        # Initialize window
        self.root = root
        self.root.title("Owl Monitoring App")
        self.root.geometry("900x600+-1920+0")
        self.root.update_idletasks()
        self.root.resizable(True, True)

        # Initialize variables
        self.script_process = None
        self.local_saving_enabled = tk.BooleanVar(value=True)
        self.capture_interval = tk.IntVar(value=60)  # Default to 60 seconds
        self.alert_delay = tk.IntVar(value=30)      # Default to 30 minutes
        
        # Add alert toggle variables
        self.email_alerts_enabled = tk.BooleanVar(value=True)
        self.text_alerts_enabled = tk.BooleanVar(value=True)
        self.email_to_text_alerts_enabled = tk.BooleanVar(value=True)
        self.after_action_reports_enabled = tk.BooleanVar(value=True)
        
        # Initialize lighting condition
        self.current_lighting_condition = get_current_lighting_condition()
        self.in_transition = self.current_lighting_condition == 'transition'
        
        self.main_script_path = os.path.join(SCRIPTS_DIR, "main.py")

        # Set style for more immediate button rendering
        self.style = ttk.Style()
        self.style.configure('TButton', font=('Arial', 10))
        self.style.configure('TFrame', padding=2)
        self.style.configure('TLabelframe', padding=3)
        
        # Add custom styles for lighting indicators
        self.style.configure('Day.TLabel', foreground='blue', font=('Arial', 10, 'bold'))
        self.style.configure('Night.TLabel', foreground='purple', font=('Arial', 10, 'bold'))
        self.style.configure('Transition.TLabel', foreground='orange', font=('Arial', 10, 'bold'))
        
        # Add accent style for Force Report button
        self.style.configure('Accent.TButton', font=('Arial', 10, 'bold'), foreground='red')

        # Initialize managers
        self.alert_manager = AlertManager()
        self.logger = get_logger()

        # Add environment and version labels
        self.env_label = ttk.Label(
            self.root,
            text="DEV ENVIRONMENT" if "Dev" in BASE_DIR else "PRODUCTION",
            font=("Arial", 12, "bold"),
            foreground="red" if "Dev" in BASE_DIR else "green"
        )
        self.env_label.pack(side="top", pady=5)

        # Add version label
        self.version_label = ttk.Label(
            self.root,
            text=f"Version: {VERSION}",
            font=("Arial", 8)
        )
        self.version_label.pack(side="top", pady=2)
        
        # Add lighting information panel - New in v1.2.1
        self.lighting_info_panel = LightingInfoPanel(self.root)
        self.lighting_info_panel.pack(side="top", pady=3, fill="x")

        # Create main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill="both", expand=True, padx=3, pady=3)

        # Create main notebook for tab-based layout
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill="both", expand=True)

        # Create tabs
        self.control_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.test_tab = ttk.Frame(self.notebook)
        self.report_tab = ttk.Frame(self.notebook)

        # Add tabs to notebook
        self.notebook.add(self.control_tab, text="Control")
        self.notebook.add(self.settings_tab, text="Settings")
        self.notebook.add(self.test_tab, text="Test")
        self.notebook.add(self.report_tab, text="Reports")

        # Initialize components
        self.initialize_components()

        # Initialize redirector
        sys.stdout = self.LogRedirector(self)
        sys.stderr = self.LogRedirector(self)

        # Verify directories
        self.verify_directories()
        self.log_message("GUI initialized and ready", "INFO")

    def initialize_components(self):
        """Initialize all GUI components"""
        # Initialize log window
        self.log_window = LogWindow(self.root)
        
        # Create control panel - Now uses the panel class
        self.control_panel = ControlPanel(
            self.control_tab,
            self.local_saving_enabled,
            self.capture_interval,
            self.alert_delay,
            self.email_alerts_enabled,
            self.text_alerts_enabled,
            self.email_to_text_alerts_enabled,
            self.after_action_reports_enabled,
            self.update_system,
            self.start_script,
            self.stop_script,
            self.toggle_local_saving,
            self.update_capture_interval,
            self.update_alert_delay,
            self.toggle_email_alerts,
            self.toggle_text_alerts,
            self.toggle_email_to_text_alerts,
            self.toggle_after_action_reports,
            self.manual_base_image_capture,
            self.manual_report_generation,
            self.log_window
        )
        self.control_panel.pack(fill="both", expand=True)
        
        # Create status panel
        self.status_panel = StatusPanel(self.control_tab)
        self.status_panel.pack(fill="x", pady=3)
        
        # Create motion detection settings in settings tab
        settings_scroll = ttk.Frame(self.settings_tab)
        settings_scroll.pack(fill="both", expand=True)
        self.settings = MotionDetectionSettings(settings_scroll, self.logger)
        
        # Create test interface in test tab
        test_scroll = ttk.Frame(self.test_tab)
        test_scroll.pack(fill="both", expand=True)
        self.test_interface = TestInterface(test_scroll, self.logger, self.alert_manager)
        
        # Create reports interface - Using the panel class
        self.reports_panel = ReportsPanel(
            self.report_tab,
            self.manual_report_generation,
            self.force_report_generation,
            self.load_report_history,
            self.show_report_details
        )
        self.reports_panel.pack(fill="both", expand=True)

    def log_message(self, message, level="INFO"):
        """Log message to log window"""
        try:
            self.log_window.log_message(message, level)
        except Exception as e:
            print(f"Error logging message: {e}")

    def verify_directories(self):
        """Verify all required directories exist"""
        try:
            self.log_message("Verifying directory structure...")
            ensure_directories_exist()
            self.log_message("Directory verification complete")
        except Exception as e:
            self.log_message(f"Error verifying directories: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to verify directories: {e}")

    def toggle_local_saving(self):
        """Handle local saving toggle"""
        is_enabled = self.local_saving_enabled.get()
        self.log_message(f"Local image saving {'enabled' if is_enabled else 'disabled'}")
        
        # Set environment variable for child processes
        os.environ['OWL_LOCAL_SAVING'] = str(is_enabled)

        if is_enabled:
            try:
                ensure_directories_exist()
            except Exception as e:
                self.log_message(f"Error creating local directories: {e}", "ERROR")
                messagebox.showerror("Error", f"Failed to create local directories: {e}")
                self.local_saving_enabled.set(False)
        
        # Update status panel
        self.status_panel.update_status(
            "Local Saving",
            "enabled" if is_enabled else "disabled"
        )

    def toggle_email_alerts(self):
        """Handle email alerts toggle"""
        is_enabled = self.email_alerts_enabled.get()
        self.log_message(f"Email alerts {'enabled' if is_enabled else 'disabled'}")
        
        # Set environment variable for child processes
        os.environ['OWL_EMAIL_ALERTS'] = str(is_enabled)
        
        # Update status panel
        self.status_panel.update_status(
            "Email Alerts",
            "enabled" if is_enabled else "disabled"
        )

    def toggle_text_alerts(self):
        """Handle text alerts toggle"""
        is_enabled = self.text_alerts_enabled.get()
        self.log_message(f"Text alerts {'enabled' if is_enabled else 'disabled'}")
        
        # Set environment variable for child processes
        os.environ['OWL_TEXT_ALERTS'] = str(is_enabled)
        
        # Update status panel
        self.status_panel.update_status(
            "Text Alerts",
            "enabled" if is_enabled else "disabled"
        )

    def toggle_email_to_text_alerts(self):
        """Handle email-to-text alerts toggle"""
        is_enabled = self.email_to_text_alerts_enabled.get()
        self.log_message(f"Email-to-text alerts {'enabled' if is_enabled else 'disabled'}")
        
        # Set environment variable for child processes
        os.environ['OWL_EMAIL_TO_TEXT_ALERTS'] = str(is_enabled)
        
        # Update status panel
        self.status_panel.update_status(
            "Email-to-Text",
            "enabled" if is_enabled else "disabled"
        )
    
    def toggle_after_action_reports(self):
        """Handle after action reports toggle"""
        is_enabled = self.after_action_reports_enabled.get()
        self.log_message(f"After action reports {'enabled' if is_enabled else 'disabled'}")
        
        # Set environment variable for child processes
        os.environ['OWL_AFTER_ACTION_REPORTS'] = str(is_enabled)
        
        # Update status panel
        self.status_panel.update_status(
            "After Action Reports",
            "enabled" if is_enabled else "disabled"
        )
    
    def manual_base_image_capture(self):
        """
        Handle manual base image capture button press.
        Updated in v1.2.1 to support transition periods with proper messaging.
        """
        # Import here to avoid circular import
        from capture_base_images import capture_base_images
        
        try:
            # Get current lighting condition
            lighting_condition = get_current_lighting_condition()
            is_transition = lighting_condition == 'transition'
            
            # In v1.2.1, we can capture images during transition periods,
            # so there's no need to block capture
            
            # Force capture even if timing conditions aren't met
            results = capture_base_images(lighting_condition, force_capture=True, show_ui_message=True)
            
            if results:
                # Show success message
                success_count = sum(1 for r in results if r['status'] == 'success')
                transition_count = sum(1 for r in results if r['status'] == 'success' and r.get('is_transition', False))
                
                if is_transition:
                    messagebox.showinfo(
                        "Base Image Capture",
                        f"Successfully captured {success_count} base images during transition period."
                    )
                else:
                    messagebox.showinfo(
                        "Base Image Capture",
                        f"Successfully captured {success_count} base images for {lighting_condition} condition."
                    )
            else:
                messagebox.showinfo(
                    "Base Image Capture",
                    "No base images were captured. Please check the logs for details."
                )
                
        except Exception as e:
            self.log_message(f"Error during manual base image capture: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to capture base images: {e}")
    
    def manual_report_generation(self):
        """Handle manual report generation button press"""
        try:
            # Ask for confirmation
            if messagebox.askyesno(
                "Generate Report",
                "Generate an after action report for the current session?\n"
                "This will be sent to all subscribers."
            ):
                self.generate_after_action_report()
                
        except Exception as e:
            self.log_message(f"Error generating report: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to generate report: {e}")
    
    def force_report_generation(self):
        """
        Force generation of an after action report regardless of conditions.
        This bypasses all timing checks and always generates a report.
        """
        try:
            # Show a more detailed confirmation
            if messagebox.askyesno(
                "Force Report Generation",
                "This will FORCE an after action report to be generated and sent\n"
                "regardless of timing conditions.\n\n"
                "Are you sure you want to continue?",
                icon='warning'
            ):
                # Get alert statistics
                alert_stats = self.alert_manager.get_alert_statistics()
                
                # Call with is_manual=True to indicate this is a forced report
                report_result = generate_after_action_report(alert_stats, is_manual=True)
                
                if report_result and report_result.get('success'):
                    self.log_message(f"Report forced successfully: {report_result.get('report_id')}")
                    
                    # Reset alert statistics
                    self.alert_manager.reset_alert_stats()
                    
                    # Reload report history
                    self.load_report_history()
                    
                    # Show success message
                    messagebox.showinfo(
                        "Report Generated",
                        f"Report {report_result.get('report_id')} was generated and sent to "
                        f"{report_result.get('recipient_count', 0)} subscribers."
                    )
                else:
                    error_msg = report_result.get('error', 'Unknown error') if report_result else 'Failed to generate report'
                    self.log_message(f"Error forcing report: {error_msg}", "ERROR")
                    messagebox.showerror("Error", f"Failed to generate report: {error_msg}")
                
        except Exception as e:
            self.log_message(f"Error forcing report: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to generate report: {e}")
    
    def generate_after_action_report(self):
        """Generate and send after action report"""
        try:
            # Get alert statistics from alert manager
            alert_stats = self.alert_manager.get_alert_statistics()
            
            # Generate and send the report
            report_result = generate_after_action_report(alert_stats, is_manual=True)
            
            if report_result and report_result.get('success'):
                self.log_message(f"After action report generated and sent successfully: {report_result.get('report_id')}")
                
                # Reset alert statistics
                self.alert_manager.reset_alert_stats()
                
                # Reload report history
                self.load_report_history()
                
                # Show success message
                messagebox.showinfo(
                    "Report Generated",
                    f"After action report {report_result.get('report_id')} generated and sent to "
                    f"{report_result.get('recipient_count', 0)} subscribers."
                )
            else:
                error_msg = report_result.get('error', 'Unknown error') if report_result else 'Failed to generate report'
                self.log_message(f"Error generating report: {error_msg}", "ERROR")
                messagebox.showerror("Error", f"Failed to generate report: {error_msg}")
                
        except Exception as e:
            self.log_message(f"Error generating report: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to generate report: {e}")
    
    def show_report_details(self, event=None):
        """Show details for a selected report"""
        try:
            # Get selected item from reports panel
            selected_item = self.reports_panel.reports_tree.focus()
            if not selected_item:
                return
                
            # Get report ID
            values = self.reports_panel.reports_tree.item(selected_item, 'values')
            if not values or values[0] == 'No reports':
                return
                
            report_id = values[0]
            
            # Create details window
            details_window = tk.Toplevel(self.root)
            details_window.title(f"Report Details: {report_id}")
            details_window.geometry("500x400")
            details_window.transient(self.root)
            
            # Add details frame
            details_frame = ttk.Frame(details_window, padding=10)
            details_frame.pack(fill="both", expand=True)
            
            # Show report ID and basic info
            ttk.Label(
                details_frame,
                text=f"Report ID: {report_id}",
                font=("Arial", 12, "bold")
            ).pack(anchor="w", pady=(0, 10))
            
            ttk.Label(
                details_frame,
                text=f"Date: {values[1]}",
                font=("Arial", 10)
            ).pack(anchor="w", pady=2)
            
            ttk.Label(
                details_frame,
                text=f"Type: {values[2]}",
                font=("Arial", 10)
            ).pack(anchor="w", pady=2)
            
            ttk.Label(
                details_frame,
                text=f"Recipients: {values[3]}",
                font=("Arial", 10)
            ).pack(anchor="w", pady=2)
            
            ttk.Label(
                details_frame,
                text=f"Total Alerts: {values[4]}",
                font=("Arial", 10)
            ).pack(anchor="w", pady=2)
            
            # Add note about email
            ttk.Separator(details_frame).pack(fill="x", pady=10)
            
            ttk.Label(
                details_frame,
                text="Note: The full report was sent via email to all subscribers.\n"
                "Check your email for the complete report with detailed statistics.",
                font=("Arial", 10, "italic"),
                wraplength=450
            ).pack(anchor="w", pady=10)
            
            # Add close button
            ttk.Button(
                details_frame,
                text="Close",
                command=details_window.destroy
            ).pack(side="bottom", pady=10)
            
        except Exception as e:
            self.log_message(f"Error showing report details: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to show report details: {e}")

    def update_capture_interval(self, *args):
        """Handle changes to the capture interval"""
        try:
            interval = self.capture_interval.get()
            
            # Validate interval is within reasonable range
            if interval < 10:
                self.capture_interval.set(10)
                interval = 10
                self.log_message("Minimum capture interval is 10 seconds", "WARNING")
            elif interval > 300:
                self.capture_interval.set(300)
                interval = 300
                self.log_message("Maximum capture interval is 300 seconds", "WARNING")
                
            # Update environment variable for child processes
            os.environ['OWL_CAPTURE_INTERVAL'] = str(interval)
            
            # Update status panel
            self.status_panel.update_status(
                "Capture Interval",
                f"{interval} sec"
            )
            
            self.log_message(f"Capture interval updated to {interval} seconds")
            
        except Exception as e:
            self.log_message(f"Error updating capture interval: {e}", "ERROR")
            # Reset to default on error
            self.capture_interval.set(60)
            
    def update_alert_delay(self, *args):
        """Handle changes to the alert delay"""
        try:
            delay = self.alert_delay.get()
            
            # Validate delay is within reasonable range
            if delay < 5:
                self.alert_delay.set(5)
                delay = 5
                self.log_message("Minimum alert delay is 5 minutes", "WARNING")
            elif delay > 120:
                self.alert_delay.set(120)
                delay = 120
                self.log_message("Maximum alert delay is 120 minutes", "WARNING")
                
            # Update alert manager
            self.alert_manager.set_alert_delay(delay)
            
            # Update status panel
            self.status_panel.update_status(
                "Alert Delay",
                f"{delay} min"
            )
            
            self.log_message(f"Alert delay updated to {delay} minutes")
            
        except Exception as e:
            self.log_message(f"Error updating alert delay: {e}", "ERROR")
            # Reset to default on error
            self.alert_delay.set(30)

    def load_report_history(self):
        """Load report history data and update the reports panel"""
        self.reports_panel.load_report_history()

    class LogRedirector:
        """Redirects stdout/stderr to log window"""
        def __init__(self, app):
            self.app = app

        def write(self, message):
            if message.strip():
                if "error" in message.lower():
                    self.app.log_message(message.strip(), "ERROR")
                elif "warning" in message.lower():
                    self.app.log_message(message.strip(), "WARNING")
                else:
                    self.app.log_message(message.strip(), "INFO")

        def flush(self):
            pass

    def update_system(self):
        """Update the system from git repository"""
        if self.script_process:
            messagebox.showwarning(
                "Warning",
                "Please stop motion detection before updating."
            )
            return

        try:
            self.log_message("Resetting local repository and pulling latest updates...")
            original_dir = os.getcwd()
            os.chdir(os.path.dirname(SCRIPTS_DIR))

            try:
                result_reset = subprocess.run(
                    ["git", "reset", "--hard"],
                    capture_output=True,
                    text=True
                )
                self.log_message(result_reset.stdout)

                result_clean = subprocess.run(
                    ["git", "clean", "-fd"],
                    capture_output=True,
                    text=True
                )
                self.log_message(result_clean.stdout)

                result_pull = subprocess.run(
                    ["git", "pull"],
                    capture_output=True,
                    text=True
                )

                if result_pull.returncode == 0:
                    self.log_message("Git pull successful. Restarting application...")
                    self.restart_application()
                else:
                    self.log_message(f"Git pull failed: {result_pull.stderr}", "ERROR")
                    messagebox.showerror("Update Failed", "Git pull failed. Check logs for details.")
            finally:
                os.chdir(original_dir)
        except Exception as e:
            self.log_message(f"Error during update: {e}", "ERROR")
            messagebox.showerror("Update Error", f"An error occurred: {e}")

    def restart_application(self):
        """Restart the entire application"""
        self.root.destroy()
        python_executable = sys.executable
        script_path = os.path.join(SCRIPTS_DIR, "_front_end.py")
        os.execv(python_executable, [python_executable, script_path])

    def start_script(self):
        """Start the motion detection script"""
        if not self.script_process:
            self.log_message("Starting motion detection script...")
            try:
                # Pass configuration through environment variables
                env = os.environ.copy()
                env['OWL_LOCAL_SAVING'] = str(self.local_saving_enabled.get())
                # Use the capture interval from the UI control
                env['OWL_CAPTURE_INTERVAL'] = str(self.capture_interval.get())
                
                # Add the alert setting environment variables
                env['OWL_EMAIL_ALERTS'] = str(self.email_alerts_enabled.get())
                env['OWL_TEXT_ALERTS'] = str(self.text_alerts_enabled.get())
                env['OWL_EMAIL_TO_TEXT_ALERTS'] = str(self.email_to_text_alerts_enabled.get())
                env['OWL_AFTER_ACTION_REPORTS'] = str(self.after_action_reports_enabled.get())
                
                # Set alert delay
                self.alert_manager.set_alert_delay(self.alert_delay.get())
                
                cmd = [sys.executable, self.main_script_path]
                self.script_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env
                )

                # Update UI state
                self.control_panel.update_run_state(True)
                self.status_panel.update_status("Motion Detection", "running")
                
                # Start log monitoring
                threading.Thread(target=self.refresh_logs, daemon=True).start()

            except Exception as e:
                self.log_message(f"Error starting script: {e}", "ERROR")

    def stop_script(self):
        """Stop the motion detection script"""
        if self.script_process:
            self.log_message("Stopping motion detection script...")
            try:
                self.script_process.terminate()
                self.script_process.wait(timeout=5)
                self.script_process = None
                self.control_panel.update_run_state(False)
                self.status_panel.update_status("Motion Detection", "stopped")
            except Exception as e:
                self.log_message(f"Error stopping script: {e}", "ERROR")

    def refresh_logs(self):
        """Refresh log display with script output"""
        try:
            while self.script_process and self.script_process.stdout:
                line = self.script_process.stdout.readline()
                if line.strip():
                    self.log_message(line.strip())
        except Exception as e:
            self.log_message(f"Error reading logs: {e}", "ERROR")