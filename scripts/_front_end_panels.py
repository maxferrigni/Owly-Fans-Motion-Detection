# File: _front_end_panels.py
# Purpose: Reusable GUI components for the Owl Monitoring System
#
# March 6, 2025 Update - Version 1.2.1
# - Added LightingInfoPanel for sunrise/sunset countdown display
# - Moved ControlPanel from _front_end_app.py for better organization

import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
from datetime import datetime, timedelta
import threading
import time
import os
import sys

# Import utilities
from utilities.time_utils import get_lighting_info, format_time_until, get_current_lighting_condition
from utilities.constants import ensure_directories_exist, VERSION
from capture_base_images import notify_transition_period, capture_base_images

class LogWindow(tk.Toplevel):
    """Enhanced logging window with filtering and search"""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        # Configure window
        self.title("Owl Monitor Log")
        self.geometry("1000x600")
        self.resizable(True, True)
        
        # Create main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create filter frame
        self.create_filter_frame(main_frame)
        
        # Create log display
        self.create_log_display(main_frame)
        
        # Keep reference to parent
        self.parent = parent
        
        # Position window
        self.position_window()
        
        # Bind parent movement
        parent.bind("<Configure>", self.follow_main_window)
        
        # Initially hide the window - will be shown when View Logs is clicked
        self.withdraw()

    def create_filter_frame(self, parent):
        """Create log filtering controls"""
        filter_frame = ttk.LabelFrame(parent, text="Log Filters")
        filter_frame.pack(fill="x", pady=(0, 5))
        
        # Level filter
        level_frame = ttk.Frame(filter_frame)
        level_frame.pack(fill="x", pady=2)
        
        ttk.Label(level_frame, text="Log Level:").pack(side="left", padx=5)
        
        self.level_var = tk.StringVar(value="ALL")
        for level in ["ALL", "INFO", "WARNING", "ERROR"]:
            ttk.Radiobutton(
                level_frame,
                text=level,
                variable=self.level_var,
                value=level,
                command=self.apply_filters
            ).pack(side="left", padx=5)
        
        # Search
        search_frame = ttk.Frame(filter_frame)
        search_frame.pack(fill="x", pady=2)
        
        ttk.Label(search_frame, text="Search:").pack(side="left", padx=5)
        
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.apply_filters())
        
        ttk.Entry(
            search_frame,
            textvariable=self.search_var
        ).pack(side="left", fill="x", expand=True, padx=5)

    def create_log_display(self, parent):
        """Create enhanced log display"""
        self.log_display = scrolledtext.ScrolledText(
            parent,
            width=100,
            height=30,
            wrap=tk.WORD,
            font=('Consolas', 10)  # Monospaced font for better readability
        )
        self.log_display.pack(fill="both", expand=True)
        
        # Configure tags for coloring with more visible colors
        self.log_display.tag_configure("ERROR", foreground="#FF0000")  # Bright red
        self.log_display.tag_configure("WARNING", foreground="#FF8C00")  # Dark orange
        self.log_display.tag_configure("INFO", foreground="#000080")  # Navy blue
        self.log_display.tag_configure("HIGHLIGHT", background="#FFFF00")  # Yellow highlight
        self.log_display.tag_configure("filtered", elide=True)  # For hiding filtered entries
        
        # Configure the base text color and background
        self.log_display.config(bg="#F8F8F8", fg="#000000")  # Light gray background, black text

    def apply_filters(self):
        """Apply all active filters to log display"""
        # Get current filters
        level = self.level_var.get()
        search = self.search_var.get().lower()
        
        # First, show all text
        self.log_display.tag_remove("filtered", "1.0", tk.END)
        
        # Filter by level - collect ranges to hide
        if level != "ALL":
            for tag in ["ERROR", "WARNING", "INFO"]:
                if tag != level:
                    index = "1.0"
                    while True:
                        tag_range = self.log_display.tag_nextrange(tag, index, tk.END)
                        if not tag_range:
                            break
                        # Mark these lines to be hidden
                        self.log_display.tag_add("filtered", tag_range[0], tag_range[1])
                        index = tag_range[1]
        
        # Apply search highlighting
        self.log_display.tag_remove("HIGHLIGHT", "1.0", tk.END)
        if search:
            start_pos = "1.0"
            while True:
                pos = self.log_display.search(search, start_pos, tk.END, nocase=True)
                if not pos:
                    break
                end_pos = f"{pos}+{len(search)}c"
                self.log_display.tag_add("HIGHLIGHT", pos, end_pos)
                start_pos = end_pos

    def log_message(self, message, level="INFO"):
        """Add enhanced log message"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] [{level}] {message}\n"
            
            self.log_display.insert(tk.END, formatted_message, level)
            self.log_display.see(tk.END)
            self.apply_filters()
                
        except Exception as e:
            print(f"Error logging to window: {e}")

    def position_window(self):
        """Position log window next to main window"""
        main_x = self.parent.winfo_x()
        main_y = self.parent.winfo_y()
        main_width = self.parent.winfo_width()
        self.geometry(f"+{main_x + main_width + 10}+{main_y}")
        
    def follow_main_window(self, event=None):
        """Reposition log window when main window moves"""
        if event.widget == self.parent:
            self.position_window()
            
    def on_closing(self):
        """Handle window closing"""
        self.withdraw()  # Hide instead of destroy
        
    def show(self):
        """Show the log window"""
        self.deiconify()
        self.position_window()
        self.lift()  # Bring to front

class StatusPanel(ttk.LabelFrame):
    """Panel showing system status indicators"""
    def __init__(self, parent):
        super().__init__(parent, text="System Status")
        
        self.status_labels = {}
        self.create_status_indicators()
        self.create_control_buttons()

    def create_status_indicators(self):
        """Create system status indicators"""
        # Create a 3x2 grid layout for indicators (added one more for interval)
        indicators = [
            ("Motion Detection", "stopped"),
            ("Local Saving", "enabled"),
            ("Alert System", "ready"),
            ("Base Images", "not verified"),
            ("Capture Interval", "60 sec"),  # Added capture interval indicator
            ("Alert Delay", "30 min"),       # Added alert delay indicator
            ("Last Detection", "none")       # Added for completeness
        ]
        
        # Create indicator frame with grid layout
        indicator_frame = ttk.Frame(self)
        indicator_frame.pack(pady=5, padx=5, fill="x")
        
        # Calculate rows and columns
        items_per_row = 3
        rows = (len(indicators) + items_per_row - 1) // items_per_row
        
        for i, (label, initial_status) in enumerate(indicators):
            row = i // items_per_row
            col = i % items_per_row
            
            indicator_label = ttk.Label(indicator_frame, text=f"{label}:")
            indicator_label.grid(row=row, column=col*2, sticky='w', padx=5, pady=3)
            
            status_label = ttk.Label(indicator_frame, text=initial_status)
            status_label.grid(row=row, column=col*2+1, sticky='w', padx=5, pady=3)
            
            self.status_labels[label] = status_label
            
        # Configure grid to expand properly
        for i in range(items_per_row * 2):
            indicator_frame.columnconfigure(i, weight=1)

    def create_control_buttons(self):
        """Create control buttons"""
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=5, padx=5, fill="x")
        
        ttk.Button(
            button_frame,
            text="Refresh Status",
            command=self.refresh_status
        ).pack(side="right", padx=5)

    def update_status(self, indicator, status, is_error=False):
        """Update status indicator"""
        if indicator in self.status_labels:
            label = self.status_labels[indicator]
            label.config(
                text=status,
                foreground="red" if is_error else "black"
            )

    def refresh_status(self):
        """Refresh all status indicators"""
        # This would be implemented by the main app
        pass

class ControlPanel(ttk.LabelFrame):
    """
    Main control panel for system operations.
    Moved from _front_end_app.py for better organization in v1.2.1.
    """
    def __init__(self, parent, app_instance):
        """
        Initialize the control panel.
        
        Args:
            parent: The parent widget
            app_instance: The OwlApp instance for callback access
        """
        super().__init__(parent, text="System Controls")
        
        # Keep a reference to the app instance for callbacks
        self.app = app_instance
        
        # Create the panel components
        self.create_button_frame()
        self.create_alert_settings_frame()
        self.create_timing_settings_frame()
        self.create_log_frame()
        
    def create_button_frame(self):
        """Create main control buttons"""
        # Main control frame with a clear title
        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", pady=3, padx=3)  # Reduced padding

        # Grid layout for better button placement with reduced spacing
        # Update button
        update_button = ttk.Button(
            button_frame,
            text="Update System",
            command=self.app.update_system,
            style='TButton'
        )
        update_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")  # Reduced padding

        # Start button
        start_button = ttk.Button(
            button_frame,
            text="Start Motion Detection",
            command=self.app.start_script,
            style='TButton'
        )
        start_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")  # Reduced padding

        # Stop button
        self.app.stop_button = ttk.Button(
            button_frame,
            text="Stop Motion Detection",
            command=self.app.stop_script,
            state=tk.DISABLED,
            style='TButton'
        )
        self.app.stop_button.grid(row=1, column=0, padx=5, pady=5, sticky="ew")  # Reduced padding

        # Local saving option in the right column, second row
        save_frame = ttk.Frame(button_frame)
        save_frame.grid(row=1, column=1, padx=5, pady=5, sticky="ew")  # Reduced padding
        
        ttk.Checkbutton(
            save_frame,
            text="Save Images Locally",
            variable=self.app.local_saving_enabled,
            command=self.app.toggle_local_saving
        ).pack(pady=2)  # Reduced padding

        # Make columns expand evenly
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        
    def create_alert_settings_frame(self):
        """Create alert settings controls"""
        # Add Alert Settings frame
        alert_settings_frame = ttk.LabelFrame(self, text="Alert Settings")
        alert_settings_frame.pack(fill="x", pady=3, padx=3)
        
        # Create a grid for alert checkboxes
        alert_checkbox_frame = ttk.Frame(alert_settings_frame)
        alert_checkbox_frame.pack(fill="x", pady=2, padx=3)
        
        # Add Email Alerts checkbox
        ttk.Checkbutton(
            alert_checkbox_frame,
            text="Email Alerts",
            variable=self.app.email_alerts_enabled,
            command=self.app.toggle_email_alerts
        ).grid(row=0, column=0, padx=5, pady=2, sticky="w")
        
        # Add Text Alerts checkbox
        ttk.Checkbutton(
            alert_checkbox_frame,
            text="Text Alerts (SMS)",
            variable=self.app.text_alerts_enabled,
            command=self.app.toggle_text_alerts
        ).grid(row=0, column=1, padx=5, pady=2, sticky="w")
        
        # Add Email-to-Text Alerts checkbox
        ttk.Checkbutton(
            alert_checkbox_frame,
            text="Email-to-Text Alerts",
            variable=self.app.email_to_text_alerts_enabled,
            command=self.app.toggle_email_to_text_alerts
        ).grid(row=1, column=0, padx=5, pady=2, sticky="w")
        
        # Add After Action Reports checkbox
        ttk.Checkbutton(
            alert_checkbox_frame,
            text="After Action Reports",
            variable=self.app.after_action_reports_enabled,
            command=self.app.toggle_after_action_reports
        ).grid(row=1, column=1, padx=5, pady=2, sticky="w")
        
        # Make columns expand evenly
        alert_checkbox_frame.columnconfigure(0, weight=1)
        alert_checkbox_frame.columnconfigure(1, weight=1)
        
    def create_timing_settings_frame(self):
        """Create timing settings controls"""
        # Add interval settings frame
        settings_frame = ttk.LabelFrame(self, text="Timing Settings")
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
            textvariable=self.app.capture_interval,
            width=5
        )
        interval_spinner.pack(side=tk.LEFT, padx=5)
        
        # Connect the interval spinner to the update handler
        interval_spinner.bind('<FocusOut>', self.app.update_capture_interval)
        interval_spinner.bind('<Return>', self.app.update_capture_interval)
        # Also update when using the spinbox arrows
        self.app.capture_interval.trace_add("write", self.app.update_capture_interval)
        
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
            textvariable=self.app.alert_delay,
            width=5
        )
        alert_delay_spinner.pack(side=tk.LEFT, padx=5)
        
        # Connect the alert delay spinner to the update handler
        alert_delay_spinner.bind('<FocusOut>', self.app.update_alert_delay)
        alert_delay_spinner.bind('<Return>', self.app.update_alert_delay)
        # Also update when using the spinbox arrows
        self.app.alert_delay.trace_add("write", self.app.update_alert_delay)
        
        # Add status indication for the alert delay
        ttk.Label(
            alert_delay_frame,
            text="(Default: 30 minutes)"
        ).pack(side=tk.LEFT, padx=5)
        
    def create_log_frame(self):
        """Create log controls"""
        # Log viewing button in a separate section
        log_frame = ttk.Frame(self)
        log_frame.pack(fill="x", pady=2, padx=3)  # Reduced padding
        
        ttk.Button(
            log_frame,
            text="View Logs",
            command=lambda: self.app.log_window.show()
        ).pack(side=tk.LEFT, pady=2)  # Reduced padding
        
        # Manual base image capture button - Enhanced in v1.1.0
        ttk.Button(
            log_frame,
            text="Capture Base Images",
            command=self.app.manual_base_image_capture
        ).pack(side=tk.RIGHT, pady=2)  # Reduced padding
        
        # Manual report generation button - New in v1.1.0
        ttk.Button(
            log_frame,
            text="Generate Report",
            command=self.app.manual_report_generation
        ).pack(side=tk.RIGHT, padx=5, pady=2)

class LightingInfoPanel(ttk.LabelFrame):
    """
    Panel showing lighting information, sunrise/sunset times, and countdown timers.
    New in v1.2.1.
    """
    def __init__(self, parent):
        super().__init__(parent, text="Lighting Information")
        
        # Create custom progress bar style
        self.style = ttk.Style()
        self.style.configure(
            "Transition.Horizontal.TProgressbar", 
            troughcolor="#E0E0E0", 
            background="#FFA500"  # Orange for transition progress
        )
        
        # Create styles for different lighting conditions
        self.style.configure('Day.TLabel', foreground='blue', font=('Arial', 10, 'bold'))
        self.style.configure('Night.TLabel', foreground='purple', font=('Arial', 10, 'bold'))
        self.style.configure('Transition.TLabel', foreground='orange', font=('Arial', 10, 'bold'))
        self.style.configure('DuskDawn.TLabel', foreground='#FF6600', font=('Arial', 9))
        self.style.configure('CountdownTime.TLabel', foreground='green', font=('Arial', 10, 'bold'))
        
        # Initialize variables
        self.lighting_condition = tk.StringVar(value="Unknown")
        self.detailed_condition = tk.StringVar(value="Unknown")
        self.sunrise_time = tk.StringVar(value="--:--")
        self.sunset_time = tk.StringVar(value="--:--")
        self.true_day_time = tk.StringVar(value="--:--")
        self.true_night_time = tk.StringVar(value="--:--")
        self.to_sunrise = tk.StringVar(value="--:--")
        self.to_sunset = tk.StringVar(value="--:--")
        self.to_true_day = tk.StringVar(value="--:--")
        self.to_true_night = tk.StringVar(value="--:--")
        self.transition_percentage = tk.DoubleVar(value=0)
        self.is_transition = False
        
        # Create panel components
        self.create_lighting_display()
        self.create_sun_times_display()
        self.create_countdown_display()
        self.create_transition_progress()
        
        # Start update thread
        self.update_thread = None
        self.running = True
        self.start_update_thread()
        
    def create_lighting_display(self):
        """Create the current lighting condition display"""
        lighting_frame = ttk.Frame(self)
        lighting_frame.pack(fill="x", padx=5, pady=5)
        
        # Current lighting condition
        ttk.Label(lighting_frame, text="Current Condition:").grid(row=0, column=0, sticky="w", padx=5)
        self.condition_label = ttk.Label(
            lighting_frame,
            textvariable=self.lighting_condition,
            style="Day.TLabel"  # Default style, will be updated
        )
        self.condition_label.grid(row=0, column=1, sticky="w", padx=5)
        
        # Detailed condition (dawn/dusk/etc)
        self.detailed_label = ttk.Label(
            lighting_frame,
            textvariable=self.detailed_condition,
            style="DuskDawn.TLabel"
        )
        self.detailed_label.grid(row=0, column=2, sticky="w", padx=5)
        
        # Configure grid
        lighting_frame.columnconfigure(0, weight=0)
        lighting_frame.columnconfigure(1, weight=0)
        lighting_frame.columnconfigure(2, weight=1)
        
    def create_sun_times_display(self):
        """Create the sunrise/sunset times display"""
        times_frame = ttk.Frame(self)
        times_frame.pack(fill="x", padx=5, pady=5)
        
        # Create a 2x4 grid for the times
        ttk.Label(times_frame, text="Sunrise:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Label(times_frame, textvariable=self.sunrise_time).grid(row=0, column=1, sticky="w", padx=5)
        
        ttk.Label(times_frame, text="Sunset:").grid(row=0, column=2, sticky="w", padx=5)
        ttk.Label(times_frame, textvariable=self.sunset_time).grid(row=0, column=3, sticky="w", padx=5)
        
        ttk.Label(times_frame, text="True Day:").grid(row=1, column=0, sticky="w", padx=5)
        ttk.Label(times_frame, textvariable=self.true_day_time).grid(row=1, column=1, sticky="w", padx=5)
        
        ttk.Label(times_frame, text="True Night:").grid(row=1, column=2, sticky="w", padx=5)
        ttk.Label(times_frame, textvariable=self.true_night_time).grid(row=1, column=3, sticky="w", padx=5)
        
        # Configure grid
        for i in range(4):
            times_frame.columnconfigure(i, weight=1)
            
    def create_countdown_display(self):
        """Create the countdown/countup display"""
        countdown_frame = ttk.Frame(self)
        countdown_frame.pack(fill="x", padx=5, pady=5)
        
        # Create a 2x4 grid for the countdowns
        ttk.Label(countdown_frame, text="Until Sunrise:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Label(
            countdown_frame, 
            textvariable=self.to_sunrise,
            style="CountdownTime.TLabel"
        ).grid(row=0, column=1, sticky="w", padx=5)
        
        ttk.Label(countdown_frame, text="Until Sunset:").grid(row=0, column=2, sticky="w", padx=5)
        ttk.Label(
            countdown_frame, 
            textvariable=self.to_sunset,
            style="CountdownTime.TLabel"
        ).grid(row=0, column=3, sticky="w", padx=5)
        
        ttk.Label(countdown_frame, text="Until True Day:").grid(row=1, column=0, sticky="w", padx=5)
        ttk.Label(
            countdown_frame, 
            textvariable=self.to_true_day,
            style="CountdownTime.TLabel"
        ).grid(row=1, column=1, sticky="w", padx=5)
        
        ttk.Label(countdown_frame, text="Until True Night:").grid(row=1, column=2, sticky="w", padx=5)
        ttk.Label(
            countdown_frame, 
            textvariable=self.to_true_night,
            style="CountdownTime.TLabel"
        ).grid(row=1, column=3, sticky="w", padx=5)
        
        # Configure grid
        for i in range(4):
            countdown_frame.columnconfigure(i, weight=1)
            
    def create_transition_progress(self):
        """Create the transition progress display"""
        self.transition_frame = ttk.Frame(self)
        self.transition_frame.pack(fill="x", padx=5, pady=5)
        
        # Transition progress bar label
        self.progress_label = ttk.Label(
            self.transition_frame, 
            text="Transition Progress:"
        )
        self.progress_label.pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(
            self.transition_frame,
            variable=self.transition_percentage,
            style="Transition.Horizontal.TProgressbar",
            length=200,
            mode='determinate'
        )
        self.progress_bar.pack(side=tk.LEFT, fill="x", expand=True, padx=5)
        
        # Percentage label
        self.percentage_label = ttk.Label(
            self.transition_frame,
            text="0%"
        )
        self.percentage_label.pack(side=tk.LEFT, padx=5)
        
        # Initially hide the transition progress
        self.transition_frame.pack_forget()
        
    def update_lighting_info(self):
        """Update all lighting information"""
        try:
            # Get current lighting information
            lighting_info = get_lighting_info()
            
            # Update condition variables
            condition = lighting_info.get('condition', 'unknown')
            detailed = lighting_info.get('detailed_condition', 'unknown')
            
            self.lighting_condition.set(condition.upper())
            
            # Update condition label style
            if condition == 'day':
                self.condition_label.configure(style='Day.TLabel')
            elif condition == 'night':
                self.condition_label.configure(style='Night.TLabel')
            else:
                self.condition_label.configure(style='Transition.TLabel')
            
            # Update detailed condition if in transition
            if condition == 'transition':
                self.detailed_condition.set(f"({detailed.upper()})")
                self.detailed_label.pack()
            else:
                self.detailed_condition.set("")
                
            # Update times
            if lighting_info.get('next_sunrise'):
                self.sunrise_time.set(lighting_info.get('next_sunrise'))
            if lighting_info.get('next_sunset'):
                self.sunset_time.set(lighting_info.get('next_sunset'))
            if lighting_info.get('next_true_day'):
                self.true_day_time.set(lighting_info.get('next_true_day'))
            if lighting_info.get('next_true_night'):
                self.true_night_time.set(lighting_info.get('next_true_night'))
                
            # Update countdowns
            countdown = lighting_info.get('countdown', {})
            
            if countdown.get('to_sunrise') is not None:
                self.to_sunrise.set(format_time_until(countdown.get('to_sunrise')))
            if countdown.get('to_sunset') is not None:
                self.to_sunset.set(format_time_until(countdown.get('to_sunset')))
            if countdown.get('to_true_day') is not None:
                self.to_true_day.set(format_time_until(countdown.get('to_true_day')))
            if countdown.get('to_true_night') is not None:
                self.to_true_night.set(format_time_until(countdown.get('to_true_night')))
                
            # Update transition progress
            is_transition = lighting_info.get('is_transition', False)
            if is_transition:
                progress = lighting_info.get('transition_percentage', 0)
                self.transition_percentage.set(progress)
                self.percentage_label.config(text=f"{progress:.1f}%")
                
                # Show transition progress
                if not self.is_transition:
                    self.transition_frame.pack(fill="x", padx=5, pady=5)
                    self.is_transition = True
            else:
                # Hide transition progress
                if self.is_transition:
                    self.transition_frame.pack_forget()
                    self.is_transition = False
                    
        except Exception as e:
            print(f"Error updating lighting info: {e}")
            
    def start_update_thread(self):
        """Start the background thread to update lighting information"""
        def update_loop():
            while self.running:
                try:
                    # Update lighting info
                    self.update_lighting_info()
                    
                    # Sleep for 5 seconds
                    for _ in range(50):  # 5 seconds in 100ms increments
                        if not self.running:
                            break
                        time.sleep(0.1)
                        
                except Exception as e:
                    print(f"Error in update thread: {e}")
                    time.sleep(5)  # Wait 5 seconds on error
        
        self.update_thread = threading.Thread(target=update_loop, daemon=True)
        self.update_thread.start()
        
    def stop_update_thread(self):
        """Stop the update thread when panel is destroyed"""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=1)
            
    def destroy(self):
        """Clean up resources when panel is destroyed"""
        self.stop_update_thread()
        super().destroy()