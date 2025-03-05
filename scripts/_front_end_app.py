# File: _front_end_app.py
# Purpose: Main application window for the Owl Monitoring System
#
# March 4, 2025 Update - Version 1.1.0
# - Added transition period indicators for lighting conditions
# - Enhanced status display for base image captures
# - Added support for after action reports
# - Improved UI feedback for lighting conditions

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import sys
from datetime import datetime, timedelta

# Add parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Import utilities and modules
from utilities.constants import SCRIPTS_DIR, ensure_directories_exist, VERSION, BASE_DIR
from utilities.logging_utils import get_logger
from utilities.alert_manager import AlertManager
from utilities.time_utils import (
    get_current_lighting_condition, 
    is_transition_period, 
    get_lighting_info, 
    should_generate_after_action_report
)
from motion_detection_settings import MotionDetectionSettings
from test_interface import TestInterface
from capture_base_images import notify_transition_period

# Import after action report generator - New in v1.1.0
from after_action_report import generate_after_action_report

# Import GUI panels
from _front_end_panels import LogWindow, StatusPanel

class OwlApp:
    def __init__(self, root):
        # Initialize window
        self.root = root
        self.root.title("Owl Monitoring App")
        self.root.geometry("900x600+-1920+0")  # Reduced height to 600
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
        
        # Added in v1.1.0 - After action report variables
        self.after_action_reports_enabled = tk.BooleanVar(value=True)
        
        # Lighting condition tracker - Added in v1.1.0
        self.current_lighting_condition = get_current_lighting_condition()
        self.last_lighting_check = datetime.now()
        self.in_transition = is_transition_period()
        
        self.main_script_path = os.path.join(SCRIPTS_DIR, "main.py")

        # Set style for more immediate button rendering
        self.style = ttk.Style()
        self.style.configure('TButton', font=('Arial', 10))
        self.style.configure('TFrame', padding=2)  # Reduced padding
        self.style.configure('TLabelframe', padding=3)  # Reduced padding
        
        # Add custom styles for lighting indicators - v1.1.0
        self.style.configure('Day.TLabel', foreground='blue', font=('Arial', 10, 'bold'))
        self.style.configure('Night.TLabel', foreground='purple', font=('Arial', 10, 'bold'))
        self.style.configure('Transition.TLabel', foreground='orange', font=('Arial', 10, 'bold'))

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
        
        # Add lighting condition indicator - New in v1.1.0
        self.lighting_frame = ttk.Frame(self.root)
        self.lighting_frame.pack(side="top", pady=3)
        
        ttk.Label(
            self.lighting_frame,
            text="Lighting: "
        ).pack(side=tk.LEFT)
        
        self.lighting_indicator = ttk.Label(
            self.lighting_frame,
            text=self.current_lighting_condition.upper(),
            style=f"{self.current_lighting_condition.capitalize()}.TLabel"
        )
        self.lighting_indicator.pack(side=tk.LEFT)
        
        # Add transition warning if needed
        if self.in_transition:
            ttk.Label(
                self.lighting_frame,
                text=" (Base images paused during transition)",
                font=("Arial", 8, "italic"),
                foreground="orange"
            ).pack(side=tk.LEFT)

        # Create main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill="both", expand=True, padx=3, pady=3)  # Reduced padding

        # Create main notebook for tab-based layout
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill="both", expand=True)

        # Create tabs
        self.control_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.test_tab = ttk.Frame(self.notebook)
        self.report_tab = ttk.Frame(self.notebook)  # New in v1.1.0

        # Add tabs to notebook
        self.notebook.add(self.control_tab, text="Control")
        self.notebook.add(self.settings_tab, text="Settings")
        self.notebook.add(self.test_tab, text="Test")
        self.notebook.add(self.report_tab, text="Reports")  # New in v1.1.0

        # Initialize components
        self.initialize_components()

        # Initialize redirector
        sys.stdout = self.LogRedirector(self)
        sys.stderr = self.LogRedirector(self)

        # Verify directories
        self.verify_directories()
        self.log_message("GUI initialized and ready", "INFO")
        
        # Start periodic lighting condition check - New in v1.1.0
        self.root.after(10000, self.check_lighting_condition)  # Check every 10 seconds

    def initialize_components(self):
        """Initialize all GUI components"""
        # Initialize log window
        self.log_window = LogWindow(self.root)
        
        # Create control panel
        self.create_control_panel()
        
        # Create status panel
        self.status_panel = StatusPanel(self.control_tab)
        self.status_panel.pack(fill="x", pady=3)  # Reduced padding
        
        # Create motion detection settings in settings tab (more compact)
        settings_scroll = ttk.Frame(self.settings_tab)
        settings_scroll.pack(fill="both", expand=True)
        self.settings = MotionDetectionSettings(settings_scroll, self.logger)
        
        # Create test interface in test tab (more compact)
        test_scroll = ttk.Frame(self.test_tab)
        test_scroll.pack(fill="both", expand=True)
        self.test_interface = TestInterface(test_scroll, self.logger, self.alert_manager)
        
        # Create reports interface - New in v1.1.0
        self.create_reports_interface()

    def create_control_panel(self):
        """Create main control panel"""
        # Main control frame with a clear title
        control_frame = ttk.LabelFrame(self.control_tab, text="System Controls")
        control_frame.pack(fill="x", pady=3, padx=3)  # Reduced padding

        # Grid layout for better button placement with reduced spacing
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill="x", pady=3, padx=3)  # Reduced padding
        
        # Update button
        update_button = ttk.Button(
            button_frame,
            text="Update System",
            command=self.update_system,
            style='TButton'
        )
        update_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")  # Reduced padding

        # Start button
        start_button = ttk.Button(
            button_frame,
            text="Start Motion Detection",
            command=self.start_script,
            style='TButton'
        )
        start_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")  # Reduced padding

        # Stop button
        self.stop_button = ttk.Button(
            button_frame,
            text="Stop Motion Detection",
            command=self.stop_script,
            state=tk.DISABLED,
            style='TButton'
        )
        self.stop_button.grid(row=1, column=0, padx=5, pady=5, sticky="ew")  # Reduced padding

        # Local saving option in the right column, second row
        save_frame = ttk.Frame(button_frame)
        save_frame.grid(row=1, column=1, padx=5, pady=5, sticky="ew")  # Reduced padding
        
        ttk.Checkbutton(
            save_frame,
            text="Save Images Locally",
            variable=self.local_saving_enabled,
            command=self.toggle_local_saving
        ).pack(pady=2)  # Reduced padding

        # Make columns expand evenly
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        # Add Alert Settings frame
        alert_settings_frame = ttk.LabelFrame(control_frame, text="Alert Settings")
        alert_settings_frame.pack(fill="x", pady=3, padx=3)
        
        # Create a grid for alert checkboxes
        alert_checkbox_frame = ttk.Frame(alert_settings_frame)
        alert_checkbox_frame.pack(fill="x", pady=2, padx=3)
        
        # Add Email Alerts checkbox
        ttk.Checkbutton(
            alert_checkbox_frame,
            text="Email Alerts",
            variable=self.email_alerts_enabled,
            command=self.toggle_email_alerts
        ).grid(row=0, column=0, padx=5, pady=2, sticky="w")
        
        # Add Text Alerts checkbox
        ttk.Checkbutton(
            alert_checkbox_frame,
            text="Text Alerts (SMS)",
            variable=self.text_alerts_enabled,
            command=self.toggle_text_alerts
        ).grid(row=0, column=1, padx=5, pady=2, sticky="w")
        
        # Add Email-to-Text Alerts checkbox
        ttk.Checkbutton(
            alert_checkbox_frame,
            text="Email-to-Text Alerts",
            variable=self.email_to_text_alerts_enabled,
            command=self.toggle_email_to_text_alerts
        ).grid(row=1, column=0, padx=5, pady=2, sticky="w")
        
        # Add After Action Reports checkbox - New in v1.1.0
        ttk.Checkbutton(
            alert_checkbox_frame,
            text="After Action Reports",
            variable=self.after_action_reports_enabled,
            command=self.toggle_after_action_reports
        ).grid(row=1, column=1, padx=5, pady=2, sticky="w")
        
        # Make columns expand evenly
        alert_checkbox_frame.columnconfigure(0, weight=1)
        alert_checkbox_frame.columnconfigure(1, weight=1)

        # Add interval settings frame
        settings_frame = ttk.LabelFrame(control_frame, text="Timing Settings")
        settings_frame.pack(fill="x", pady=3, padx=3)
        
        # Add capture interval setting
        interval_frame = ttk.Frame(settings_frame)
        interval_frame.pack(fill="x", pady=2, padx=3)
        
        ttk.Label(
            interval_frame,
            text="Capture Interval (seconds):"
        ).pack(side=tk.LEFT, padx=5)
        
        interval_spinner = ttk.Spinbox(
            interval_frame,
            from_=10,
            to=300,
            increment=10,
            textvariable=self.capture_interval,
            width=5
        )
        interval_spinner.pack(side=tk.LEFT, padx=5)
        
        # Connect the interval spinner to the update handler
        interval_spinner.bind('<FocusOut>', self.update_capture_interval)
        interval_spinner.bind('<Return>', self.update_capture_interval)
        # Also update when using the spinbox arrows
        self.capture_interval.trace_add("write", self.update_capture_interval)
        
        # Add status indication for the interval
        ttk.Label(
            interval_frame,
            text="(Default: 60 seconds)"
        ).pack(side=tk.LEFT, padx=5)
        
        # Add alert delay setting
        alert_delay_frame = ttk.Frame(settings_frame)
        alert_delay_frame.pack(fill="x", pady=2, padx=3)
        
        ttk.Label(
            alert_delay_frame,
            text="Alert Delay (minutes):"
        ).pack(side=tk.LEFT, padx=5)
        
        alert_delay_spinner = ttk.Spinbox(
            alert_delay_frame,
            from_=5,
            to=120,
            increment=5,
            textvariable=self.alert_delay,
            width=5
        )
        alert_delay_spinner.pack(side=tk.LEFT, padx=5)
        
        # Connect the alert delay spinner to the update handler
        alert_delay_spinner.bind('<FocusOut>', self.update_alert_delay)
        alert_delay_spinner.bind('<Return>', self.update_alert_delay)
        # Also update when using the spinbox arrows
        self.alert_delay.trace_add("write", self.update_alert_delay)
        
        # Add status indication for the alert delay
        ttk.Label(
            alert_delay_frame,
            text="(Default: 30 minutes)"
        ).pack(side=tk.LEFT, padx=5)

        # Log viewing button in a separate section
        log_frame = ttk.Frame(control_frame)
        log_frame.pack(fill="x", pady=2, padx=3)  # Reduced padding
        
        ttk.Button(
            log_frame,
            text="View Logs",
            command=lambda: self.log_window.show()
        ).pack(side=tk.LEFT, pady=2)  # Reduced padding
        
        # Manual base image capture button - Enhanced in v1.1.0
        ttk.Button(
            log_frame,
            text="Capture Base Images",
            command=self.manual_base_image_capture
        ).pack(side=tk.RIGHT, pady=2)  # Reduced padding
        
        # Manual report generation button - New in v1.1.0
        ttk.Button(
            log_frame,
            text="Generate Report",
            command=self.manual_report_generation
        ).pack(side=tk.RIGHT, padx=5, pady=2)

    def create_reports_interface(self):
        """Create reports interface tab - New in v1.1.0"""
        reports_frame = ttk.LabelFrame(self.report_tab, text="After Action Reports")
        reports_frame.pack(fill="both", expand=True, pady=5, padx=5)
        
        # Add explanation text
        info_text = """
        After Action Reports are automatically generated when transitioning 
        between day and night lighting conditions. Reports summarize all owl 
        activity from the preceding session.
        
        Reports include:
        • Alert counts by type
        • Detection durations
        • Activity summaries
        
        Reports are sent to all subscribers.
        """
        
        ttk.Label(
            reports_frame,
            text=info_text,
            wraplength=500,
            justify=tk.LEFT
        ).pack(pady=10, padx=10, anchor=tk.W)
        
        # Add buttons frame
        buttons_frame = ttk.Frame(reports_frame)
        buttons_frame.pack(fill="x", pady=5)
        
        # Generate report button
        ttk.Button(
            buttons_frame,
            text="Generate Report Now",
            command=self.manual_report_generation
        ).pack(side=tk.LEFT, padx=5)
        
        # View last report button
        ttk.Button(
            buttons_frame,
            text="View Last Report",
            command=self.view_last_report
        ).pack(side=tk.LEFT, padx=5)
        
        # Add report history frame
        history_frame = ttk.LabelFrame(reports_frame, text="Report History")
        history_frame.pack(fill="both", expand=True, pady=5)
        
        # Create treeview for report history
        columns = ('date', 'time', 'alerts', 'session_type')
        self.reports_tree = ttk.Treeview(history_frame, columns=columns, show='headings')
        
        # Define headings
        self.reports_tree.heading('date', text='Date')
        self.reports_tree.heading('time', text='Time')
        self.reports_tree.heading('alerts', text='Alerts')
        self.reports_tree.heading('session_type', text='Session Type')
        
        # Define columns
        self.reports_tree.column('date', width=100)
        self.reports_tree.column('time', width=100)
        self.reports_tree.column('alerts', width=100)
        self.reports_tree.column('session_type', width=150)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.reports_tree.yview)
        self.reports_tree.configure(yscroll=scrollbar.set)
        
        # Pack the treeview and scrollbar
        self.reports_tree.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill="y")
        
        # Double-click to view report
        self.reports_tree.bind("<Double-1>", self.on_report_double_click)
    
    def check_lighting_condition(self):
        """
        Periodically check for lighting condition changes.
        New in v1.1.0 to handle transition periods and after action reports.
        """
        try:
            # Get current lighting condition
            current_condition = get_current_lighting_condition()
            in_transition = is_transition_period()
            
            # Check for condition change
            if current_condition != self.current_lighting_condition or in_transition != self.in_transition:
                self.log_message(f"Lighting condition changed: {self.current_lighting_condition} -> {current_condition}")
                
                # Update indicator
                self.lighting_indicator.config(
                    text=current_condition.upper(),
                    style=f"{current_condition.capitalize()}.TLabel"
                )
                
                # Update status panel
                self.status_panel.update_status(
                    "Lighting",
                    current_condition
                )
                
                # Show notification if entering or leaving transition period
                if in_transition and not self.in_transition:
                    # Entered transition period
                    notify_transition_period(self.root)
                    
                    # Clear transition warning label if it exists
                    for widget in self.lighting_frame.winfo_children():
                        if isinstance(widget, ttk.Label) and widget not in [self.lighting_indicator]:
                            if "transition" in widget.cget("text").lower():
                                widget.destroy()
                    
                    # Add transition warning
                    ttk.Label(
                        self.lighting_frame,
                        text=" (Base images paused during transition)",
                        font=("Arial", 8, "italic"),
                        foreground="orange"
                    ).pack(side=tk.LEFT)
                    
                elif not in_transition and self.in_transition:
                    # Exited transition period
                    # Clear transition warning label if it exists
                    for widget in self.lighting_frame.winfo_children():
                        if isinstance(widget, ttk.Label) and widget not in [self.lighting_indicator]:
                            if "transition" in widget.cget("text").lower():
                                widget.destroy()
                
                # Check if we should generate an after action report
                if self.after_action_reports_enabled.get() and should_generate_after_action_report():
                    self.log_message("Generating after action report due to major lighting transition")
                    self.generate_after_action_report()
                
                # Update stored values
                self.current_lighting_condition = current_condition
                self.in_transition = in_transition
            
            # Schedule next check
            self.root.after(10000, self.check_lighting_condition)  # Check every 10 seconds
            
        except Exception as e:
            self.log_message(f"Error checking lighting condition: {e}", "ERROR")
            # Still schedule next check even if error occurs
            self.root.after(10000, self.check_lighting_condition)

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
        """Handle after action reports toggle - New in v1.1.0"""
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
        Enhanced in v1.1.0 to handle transition periods.
        """
        # Import here to avoid circular import
        from capture_base_images import capture_base_images
        
        # Check for transition period
        if is_transition_period():
            messagebox.showinfo(
                "Base Image Capture", 
                "Cannot capture base images during lighting transition period.\n"
                "Please wait for true day or true night conditions."
            )
            return
        
        try:
            # Get current lighting condition
            lighting_condition = get_current_lighting_condition()
            
            # Force capture even if timing conditions aren't met
            results = capture_base_images(lighting_condition, force_capture=True, show_ui_message=True)
            
            if results:
                # Show success message
                success_count = sum(1 for r in results if r['status'] == 'success')
                messagebox.showinfo(
                    "Base Image Capture",
                    f"Successfully captured {success_count} base images for {lighting_condition} condition."
                )
            else:
                messagebox.showinfo(
                    "Base Image Capture",
                    "No base images were captured. This could be due to transition period or camera configuration issues."
                )
                
        except Exception as e:
            self.log_message(f"Error during manual base image capture: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to capture base images: {e}")
    
    def manual_report_generation(self):
        """Handle manual report generation button press - New in v1.1.0"""
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
    
    def generate_after_action_report(self):
        """Generate and send after action report - New in v1.1.0"""
        try:
            # Get alert statistics from alert manager
            alert_stats = self.alert_manager.get_alert_statistics()
            
            # Generate and send the report
            report_result = generate_after_action_report(alert_stats, is_manual=True)
            
            if report_result and report_result.get('success'):
                self.log_message("After action report generated and sent successfully")
                
                # Reset alert statistics
                self.alert_manager.reset_alert_stats()
                
                # Add to report history
                self.add_report_to_history(report_result)
                
                # Show success message
                messagebox.showinfo(
                    "Report Generated",
                    f"After action report generated and sent to {report_result.get('recipient_count', 0)} subscribers."
                )
            else:
                error_msg = report_result.get('error', 'Unknown error') if report_result else 'Failed to generate report'
                self.log_message(f"Error generating report: {error_msg}", "ERROR")
                messagebox.showerror("Error", f"Failed to generate report: {error_msg}")
                
        except Exception as e:
            self.log_message(f"Error generating report: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to generate report: {e}")
    
    def add_report_to_history(self, report_data):
        """Add a new report to the history treeview - New in v1.1.0"""
        try:
            # Format data for treeview
            date_str = datetime.now().strftime('%Y-%m-%d')
            time_str = datetime.now().strftime('%H:%M:%S')
            alerts = str(report_data.get('total_alerts', 0))
            session_type = report_data.get('session_type', 'Manual')
            
            # Insert at the top of the treeview
            self.reports_tree.insert('', 0, values=(date_str, time_str, alerts, session_type))
            
        except Exception as e:
            self.log_message(f"Error adding report to history: {e}", "ERROR")
    
    def view_last_report(self):
        """View the latest after action report - New in v1.1.0"""
        try:
            # Try to open the last report file
            import os
            reports_dir = os.path.join(BASE_DIR, "20_Local_Files", "reports")
            
            if not os.path.exists(reports_dir):
                messagebox.showinfo("No Reports", "No reports have been generated yet.")
                return
                
            # List all report files and sort by modification time
            report_files = [os.path.join(reports_dir, f) for f in os.listdir(reports_dir) if f.endswith('.html')]
            
            if not report_files:
                messagebox.showinfo("No Reports", "No report files found.")
                return
                
            # Get the most recent file
            latest_report = max(report_files, key=os.path.getmtime)
            
            # Try to open with default browser
            import webbrowser
            webbrowser.open(f"file://{latest_report}")
            
        except Exception as e:
            self.log_message(f"Error viewing report: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to view report: {e}")
    
    def on_report_double_click(self, event):
        """Handle double-click on report in treeview - New in v1.1.0"""
        try:
            # Get selected item
            selected_item = self.reports_tree.focus()
            if not selected_item:
                return
                
            # Get values
            values = self.reports_tree.item(selected_item, 'values')
            if not values:
                return
                
            # Attempt to find the report based on date and time
            date_str, time_str = values[0], values[1]
            formatted_datetime = f"{date_str}_{time_str.replace(':', '')}"
            
            # Look for file with matching timestamp
            import os
            reports_dir = os.path.join(BASE_DIR, "20_Local_Files", "reports")
            
            if not os.path.exists(reports_dir):
                messagebox.showinfo("No Reports", "Reports directory not found.")
                return
                
            # Try to find a matching report
            matching_files = [f for f in os.listdir(reports_dir) 
                             if f.endswith('.html') and formatted_datetime in f]
            
            if matching_files:
                # Open the first matching file
                import webbrowser
                report_path = os.path.join(reports_dir, matching_files[0])
                webbrowser.open(f"file://{report_path}")
            else:
                messagebox.showinfo("Report Not Found", "Could not find the report file.")
                
        except Exception as e:
            self.log_message(f"Error opening report: {e}", "ERROR")

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
            
            # Add reports directory in v1.1.0
            reports_dir = os.path.join(BASE_DIR, "20_Local_Files", "reports")
            os.makedirs(reports_dir, exist_ok=True)
            
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
                
                # After action reports - New in v1.1.0
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
                self.stop_button.config(state=tk.NORMAL)
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
                self.stop_button.config(state=tk.DISABLED)
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