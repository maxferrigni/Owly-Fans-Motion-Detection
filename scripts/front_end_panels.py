# File: front_end_panels.py
# Purpose: Reusable GUI components for the Owl Monitoring System
#
# March 7, 2025 Update - Version 1.4.3
# - Completely simplified LightingInfoPanel
# - Reduced redundant time displays
# - Made time panel more compact
# - Enhanced UI responsiveness with better state management

import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
from datetime import datetime, timedelta
import threading
import time
import os
import traceback
from PIL import Image, ImageTk
from utilities.logging_utils import get_logger
from utilities.time_utils import get_lighting_info, format_time_until, get_current_lighting_condition
from utilities.constants import get_base_image_path, IMAGE_COMPARISONS_DIR

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
        
        ttk.Label(level_frame, text="Log Level:").pack(side=tk.LEFT, padx=5)
        
        self.level_var = tk.StringVar(value="ALL")
        for level in ["ALL", "INFO", "WARNING", "ERROR"]:
            ttk.Radiobutton(
                level_frame,
                text=level,
                variable=self.level_var,
                value=level,
                command=self.apply_filters
            ).pack(side=tk.LEFT, padx=5)
        
        # Search
        search_frame = ttk.Frame(filter_frame)
        search_frame.pack(fill="x", pady=2)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.apply_filters())
        
        ttk.Entry(
            search_frame,
            textvariable=self.search_var
        ).pack(side=tk.LEFT, fill="x", expand=True, padx=5)

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

class ControlPanel(ttk.Frame):
    """Panel for controlling the application - Enhanced with error handling for v1.4.3"""
    def __init__(self, parent, local_saving_enabled, capture_interval, alert_delay,
                 email_alerts_enabled, update_system_func, start_script_func,
                 stop_script_func, toggle_local_saving_func, update_capture_interval_func,
                 update_alert_delay_func, toggle_email_alerts_func, log_window, 
                 clear_saved_images_func=None):
        super().__init__(parent)
        
        self.local_saving_enabled = local_saving_enabled
        self.capture_interval = capture_interval
        self.alert_delay = alert_delay
        self.email_alerts_enabled = email_alerts_enabled
        
        # Store callback functions
        self.update_system_func = update_system_func
        self.start_script_func = start_script_func
        self.stop_script_func = stop_script_func
        self.toggle_local_saving_func = toggle_local_saving_func
        self.update_capture_interval_func = update_capture_interval_func
        self.update_alert_delay_func = update_alert_delay_func
        self.toggle_email_alerts_func = toggle_email_alerts_func
        self.clear_saved_images_func = clear_saved_images_func
        self.log_window = log_window
        
        # For logging
        self.logger = get_logger()
        
        # Create UI components
        self.create_control_interface()
        
    def create_control_interface(self):
        """Create simplified control interface components"""
        # Main controls frame
        main_controls = ttk.LabelFrame(self, text="Motion Detection Controls")
        main_controls.pack(padx=5, pady=5, fill="x")
        
        # Script control buttons
        button_frame = ttk.Frame(main_controls)
        button_frame.pack(pady=5, fill="x")
        
        self.start_button = ttk.Button(
            button_frame,
            text="Start Detection",
            command=self.start_script_handler
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(
            button_frame,
            text="Stop Detection",
            command=self.stop_script_handler,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.update_button = ttk.Button(
            button_frame,
            text="Update System",
            command=self.update_system_handler
        )
        self.update_button.pack(side=tk.LEFT, padx=5)
        
        # Maintenance button
        self.clear_images_button = ttk.Button(
            button_frame,
            text="Clear Saved Images",
            command=self.clear_saved_images_handler
        )
        self.clear_images_button.pack(side=tk.LEFT, padx=5)
        
        # View logs button
        self.view_logs_button = ttk.Button(
            button_frame,
            text="View Logs",
            command=self.show_logs_handler
        )
        self.view_logs_button.pack(side=tk.RIGHT, padx=5)
        
        # Combined Settings section (merged settings and alert settings)
        settings_frame = ttk.LabelFrame(self, text="Settings")
        settings_frame.pack(padx=5, pady=5, fill="x")
        
        # Create settings controls
        setting_controls = ttk.Frame(settings_frame)
        setting_controls.pack(pady=5, fill="x")
        
        # Local saving checkbox
        local_saving_cb = ttk.Checkbutton(
            setting_controls,
            text="Enable Local Image Saving",
            variable=self.local_saving_enabled,
            command=self.toggle_local_saving_handler
        )
        local_saving_cb.grid(row=0, column=0, sticky="w", padx=5, pady=2)
        
        # Capture interval
        interval_frame = ttk.Frame(setting_controls)
        interval_frame.grid(row=1, column=0, sticky="w", padx=5, pady=2)
        
        ttk.Label(interval_frame, text="Capture Interval (sec):").pack(side=tk.LEFT)
        
        interval_spinner = ttk.Spinbox(
            interval_frame,
            from_=10,
            to=300,
            width=5,
            textvariable=self.capture_interval,
            command=self.update_capture_interval_handler
        )
        interval_spinner.pack(side=tk.LEFT, padx=5)
        
        # Alert delay
        delay_frame = ttk.Frame(setting_controls)
        delay_frame.grid(row=2, column=0, sticky="w", padx=5, pady=2)
        
        ttk.Label(delay_frame, text="Alert Delay (min):").pack(side=tk.LEFT)
        
        delay_spinner = ttk.Spinbox(
            delay_frame,
            from_=5,
            to=120,
            width=5,
            textvariable=self.alert_delay,
            command=self.update_alert_delay_handler
        )
        delay_spinner.pack(side=tk.LEFT, padx=5)
        
        # Email alerts checkbox (only remaining alert type)
        email_cb = ttk.Checkbutton(
            setting_controls,
            text="Enable Email Alerts",
            variable=self.email_alerts_enabled,
            command=self.toggle_email_alerts_handler
        )
        email_cb.grid(row=3, column=0, sticky="w", padx=5, pady=2)
    
    # Adding error handling to all button handlers
    def start_script_handler(self):
        """Start script with error handling"""
        try:
            self.logger.info("Start detection button clicked")
            self.start_script_func()
        except Exception as e:
            error_message = f"Error starting detection: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)
    
    def stop_script_handler(self):
        """Stop script with error handling"""
        try:
            self.logger.info("Stop detection button clicked")
            self.stop_script_func()
        except Exception as e:
            error_message = f"Error stopping detection: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)
    
    def update_system_handler(self):
        """Update system with error handling"""
        try:
            self.logger.info("Update system button clicked")
            self.update_system_func()
        except Exception as e:
            error_message = f"Error updating system: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)

    def clear_saved_images_handler(self):
        """Clear saved images with error handling"""
        try:
            self.logger.info("Clear saved images button clicked")
            if self.clear_saved_images_func:
                self.clear_saved_images_func()
            else:
                messagebox.showinfo("Not Available", "Clear saved images function is not available")
        except Exception as e:
            error_message = f"Error clearing saved images: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)

    def show_logs_handler(self):
        """Show logs with error handling"""
        try:
            self.logger.info("View logs button clicked")
            if hasattr(self.log_window, 'show'):
                self.log_window.show()
            else:
                messagebox.showinfo("Not Available", "Log window is not available")
        except Exception as e:
            error_message = f"Error showing logs: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)
    
    def toggle_local_saving_handler(self):
        """Toggle local saving with error handling"""
        try:
            self.toggle_local_saving_func()
        except Exception as e:
            error_message = f"Error toggling local saving: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)
            # Reset checkbox to previous state
            self.local_saving_enabled.set(not self.local_saving_enabled.get())
    
    def update_capture_interval_handler(self):
        """Update capture interval with error handling"""
        try:
            self.update_capture_interval_func()
        except Exception as e:
            error_message = f"Error updating capture interval: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)
    
    def update_alert_delay_handler(self):
        """Update alert delay with error handling"""
        try:
            self.update_alert_delay_func()
        except Exception as e:
            error_message = f"Error updating alert delay: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)
    
    def toggle_email_alerts_handler(self):
        """Toggle email alerts with error handling"""
        try:
            self.toggle_email_alerts_func()
        except Exception as e:
            error_message = f"Error toggling email alerts: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)
            # Reset checkbox to previous state
            self.email_alerts_enabled.set(not self.email_alerts_enabled.get())
    
    def update_run_state(self, is_running):
        """Update UI based on whether the script is running"""
        try:
            if is_running:
                self.start_button.config(state=tk.DISABLED)
                self.stop_button.config(state=tk.NORMAL)
            else:
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
        except Exception as e:
            self.logger.error(f"Error updating run state: {e}")

class LightingInfoPanel(ttk.LabelFrame):
    """
    Simplified panel showing only essential lighting information.
    Completely redesigned for v1.4.3 to be more compact and efficient.
    """
    def __init__(self, parent):
        super().__init__(parent, text="Lighting Information")
        
        # Initialize logger
        self.logger = get_logger()
        
        # Create styles for lighting conditions
        self.style = ttk.Style()
        self.style.configure('Day.TLabel', foreground='blue', font=('Arial', 9, 'bold'))
        self.style.configure('Night.TLabel', foreground='purple', font=('Arial', 9, 'bold'))
        self.style.configure('Transition.TLabel', foreground='orange', font=('Arial', 9, 'bold'))
        self.style.configure('TimeValue.TLabel', foreground='black', font=('Arial', 9))
        
        # Initialize variables for the essential information only
        self.lighting_condition = tk.StringVar(value="Unknown")
        self.sunrise_time = tk.StringVar(value="--:--")
        self.sunset_time = tk.StringVar(value="--:--")
        self.true_day_time = tk.StringVar(value="--:--")
        self.true_night_time = tk.StringVar(value="--:--")
        
        # Track running state
        self.running = True
        
        # Create simplified single-row layout
        self.create_compact_layout()
        
        # Start update thread
        self.start_update_thread()
    
    def create_compact_layout(self):
        """Create a simplified single-row layout with only essential information"""
        try:
            # Create main container frame with very small padding
            main_frame = ttk.Frame(self)
            main_frame.pack(fill="x", padx=2, pady=2)
            
            # Create a single row with 5 equally-spaced columns
            
            # 1. Current condition display
            condition_frame = ttk.Frame(main_frame)
            condition_frame.pack(side="left", padx=5)
            
            ttk.Label(condition_frame, text="Condition:").pack(side="left")
            self.condition_label = ttk.Label(
                condition_frame,
                textvariable=self.lighting_condition,
                style="Day.TLabel"  # Default style
            )
            self.condition_label.pack(side="left", padx=2)
            
            # Add a separator
            ttk.Separator(main_frame, orient="vertical").pack(side="left", fill="y", padx=5)
            
            # 2. Sunrise info
            sunrise_frame = ttk.Frame(main_frame)
            sunrise_frame.pack(side="left", padx=5)
            
            ttk.Label(sunrise_frame, text="Sunrise:").pack(side="left")
            ttk.Label(
                sunrise_frame,
                textvariable=self.sunrise_time,
                style="TimeValue.TLabel"
            ).pack(side="left", padx=2)
            
            # 3. True day info
            true_day_frame = ttk.Frame(main_frame)
            true_day_frame.pack(side="left", padx=5)
            
            ttk.Label(true_day_frame, text="True Day:").pack(side="left")
            ttk.Label(
                true_day_frame,
                textvariable=self.true_day_time,
                style="TimeValue.TLabel"
            ).pack(side="left", padx=2)
            
            # Add a separator
            ttk.Separator(main_frame, orient="vertical").pack(side="left", fill="y", padx=5)
            
            # 4. Sunset info
            sunset_frame = ttk.Frame(main_frame)
            sunset_frame.pack(side="left", padx=5)
            
            ttk.Label(sunset_frame, text="Sunset:").pack(side="left")
            ttk.Label(
                sunset_frame,
                textvariable=self.sunset_time,
                style="TimeValue.TLabel"
            ).pack(side="left", padx=2)
            
            # 5. True night info
            true_night_frame = ttk.Frame(main_frame)
            true_night_frame.pack(side="left", padx=5)
            
            ttk.Label(true_night_frame, text="True Night:").pack(side="left")
            ttk.Label(
                true_night_frame,
                textvariable=self.true_night_time,
                style="TimeValue.TLabel"
            ).pack(side="left", padx=2)
            
        except Exception as e:
            self.logger.error(f"Error creating lighting info layout: {e}")
            self.logger.error(traceback.format_exc())
    
    def update_lighting_info(self):
        """Update lighting information with essential data only"""
        try:
            # Get lighting information
            lighting_info = get_lighting_info()
            
            # Update condition
            condition = lighting_info.get('condition', 'unknown')
            self.lighting_condition.set(condition.upper())
            
            # Update condition style
            if condition == 'day':
                self.condition_label.configure(style='Day.TLabel')
            elif condition == 'night':
                self.condition_label.configure(style='Night.TLabel')
            else:
                self.condition_label.configure(style='Transition.TLabel')
            
            # Update times
            if lighting_info.get('next_sunrise'):
                self.sunrise_time.set(lighting_info.get('next_sunrise'))
            if lighting_info.get('next_sunset'):
                self.sunset_time.set(lighting_info.get('next_sunset'))
            if lighting_info.get('next_true_day'):
                self.true_day_time.set(lighting_info.get('next_true_day'))
            if lighting_info.get('next_true_night'):
                self.true_night_time.set(lighting_info.get('next_true_night'))
                
        except Exception as e:
            self.logger.error(f"Error updating lighting info: {e}")
            self.logger.error(traceback.format_exc())
    
    def start_update_thread(self):
        """Start background thread for updates"""
        def update_loop():
            while self.running:
                try:
                    # Update lighting info
                    self.update_lighting_info()
                    
                    # Sleep for 10 seconds (less frequent updates to save resources)
                    for _ in range(100):  # 10 seconds in 100ms increments
                        if not self.running:
                            break
                        time.sleep(0.1)
                        
                except Exception as e:
                    self.logger.error(f"Error in lighting update thread: {e}")
                    time.sleep(5)  # Wait 5 seconds on error
        
        self.update_thread = threading.Thread(target=update_loop, daemon=True)
        self.update_thread.start()
    
    def stop_update_thread(self):
        """Stop the update thread"""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=1)
    
    def destroy(self):
        """Clean up resources when destroyed"""
        self.stop_update_thread()
        super().destroy()

# Test the layouts
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Panel Test")
    
    # Test lighting info panel
    lighting_panel = LightingInfoPanel(root)
    lighting_panel.pack(fill="x", pady=10)
    
    # Add dummy labels to show layout
    ttk.Label(root, text="Main Content Would Go Here").pack(pady=50)
    
    root.mainloop()