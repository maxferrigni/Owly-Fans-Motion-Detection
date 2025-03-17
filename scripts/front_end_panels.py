# File: scripts/front_end_panels.py
# Purpose: Reusable GUI components for the Owl Monitoring System
#
# March 17, 2025 Update - Version 1.4.1
# - Refactored panel components - moved specific tab panels to their own files
# - Retained only shared components (LogWindow and LightingInfoPanel)
# - ControlPanel moved to front_end_components/control_tab.py
# - ImageViewerPanel moved to front_end_components/images_tab.py
# - SysMonitorPanel moved to front_end_components/monitor_tab.py

import tkinter as tk
from tkinter import scrolledtext, ttk
from datetime import datetime, timedelta
import threading
import time
import os
from utilities.logging_utils import get_logger
from utilities.time_utils import get_lighting_info, format_time_until, get_current_lighting_condition

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

class LightingInfoPanel(ttk.LabelFrame):
    """
    Panel showing lighting information, sunrise/sunset times, and countdown timers.
    Made more compact in v1.3.2 for better space utilization.
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
        self.style.configure('Day.TLabel', foreground='blue', font=('Arial', 9, 'bold'))
        self.style.configure('Night.TLabel', foreground='purple', font=('Arial', 9, 'bold'))
        self.style.configure('Transition.TLabel', foreground='orange', font=('Arial', 9, 'bold'))
        self.style.configure('DuskDawn.TLabel', foreground='#FF6600', font=('Arial', 8))
        self.style.configure('CountdownTime.TLabel', foreground='green', font=('Arial', 9, 'bold'))
        self.style.configure('InfoLabel.TLabel', font=('Arial', 8))
        
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
        
        # Create compact layout
        self.create_compact_layout()
        
        # Start update thread
        self.update_thread = None
        self.running = True
        self.start_update_thread()
        
    def create_compact_layout(self):
        """Create more compact layout for lighting information"""
        # Main grid with 3 columns
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="x", padx=3, pady=3)
        
        # Current condition (Row 0)
        ttk.Label(main_frame, text="Current:").grid(row=0, column=0, sticky="w", padx=2)
        self.condition_label = ttk.Label(
            main_frame,
            textvariable=self.lighting_condition,
            style="Day.TLabel"
        )
        self.condition_label.grid(row=0, column=1, sticky="w", padx=2)
        self.detailed_label = ttk.Label(
            main_frame,
            textvariable=self.detailed_condition,
            style="DuskDawn.TLabel"
        )
        self.detailed_label.grid(row=0, column=2, sticky="w", padx=2)
        
        # Sun times with countdowns (Row 1-2) - More compact grid layout
        times_frame = ttk.Frame(main_frame)
        times_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=1)
        
        # Grid layout for times
        # Column 0-1: Sunrise info, Column 2-3: Sunset info
        # Column 4-5: True Day info, Column 6-7: True Night info
        
        # Labels - Row 0
        ttk.Label(times_frame, text="Sunrise:", style="InfoLabel.TLabel").grid(row=0, column=0, sticky="w", padx=2)
        ttk.Label(times_frame, text="Sunset:", style="InfoLabel.TLabel").grid(row=0, column=2, sticky="w", padx=2)
        ttk.Label(times_frame, text="True Day:", style="InfoLabel.TLabel").grid(row=0, column=4, sticky="w", padx=2)
        ttk.Label(times_frame, text="True Night:", style="InfoLabel.TLabel").grid(row=0, column=6, sticky="w", padx=2)
        
        # Time values - Row 0
        ttk.Label(times_frame, textvariable=self.sunrise_time, style="InfoLabel.TLabel").grid(row=0, column=1, sticky="w", padx=2)
        ttk.Label(times_frame, textvariable=self.sunset_time, style="InfoLabel.TLabel").grid(row=0, column=3, sticky="w", padx=2)
        ttk.Label(times_frame, textvariable=self.true_day_time, style="InfoLabel.TLabel").grid(row=0, column=5, sticky="w", padx=2)
        ttk.Label(times_frame, textvariable=self.true_night_time, style="InfoLabel.TLabel").grid(row=0, column=7, sticky="w", padx=2)
        
        # Countdown labels - Row 1
        ttk.Label(times_frame, text="Until:", style="InfoLabel.TLabel").grid(row=1, column=0, sticky="w", padx=2)
        ttk.Label(times_frame, textvariable=self.to_sunrise, style="CountdownTime.TLabel").grid(row=1, column=1, sticky="w", padx=2)
        
        ttk.Label(times_frame, text="Until:", style="InfoLabel.TLabel").grid(row=1, column=2, sticky="w", padx=2)
        ttk.Label(times_frame, textvariable=self.to_sunset, style="CountdownTime.TLabel").grid(row=1, column=3, sticky="w", padx=2)
        
        ttk.Label(times_frame, text="Until:", style="InfoLabel.TLabel").grid(row=1, column=4, sticky="w", padx=2)
        ttk.Label(times_frame, textvariable=self.to_true_day, style="CountdownTime.TLabel").grid(row=1, column=5, sticky="w", padx=2)
        
        ttk.Label(times_frame, text="Until:", style="InfoLabel.TLabel").grid(row=1, column=6, sticky="w", padx=2)
        ttk.Label(times_frame, textvariable=self.to_true_night, style="CountdownTime.TLabel").grid(row=1, column=7, sticky="w", padx=2)
        
        # Configure columns to expand proportionally
        for i in range(8):
            times_frame.columnconfigure(i, weight=1)
        
        # Transition progress (hidden initially)
        self.transition_frame = ttk.Frame(main_frame)
        self.transition_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=1)
        
        self.progress_label = ttk.Label(
            self.transition_frame, 
            text="Transition:",
            style="InfoLabel.TLabel"
        )
        self.progress_label.pack(side=tk.LEFT, padx=2)
        
        self.progress_bar = ttk.Progressbar(
            self.transition_frame,
            variable=self.transition_percentage,
            style="Transition.Horizontal.TProgressbar",
            length=150,
            mode='determinate'
        )
        self.progress_bar.pack(side=tk.LEFT, fill="x", expand=True, padx=2)
        
        self.percentage_label = ttk.Label(
            self.transition_frame,
            text="0%",
            style="InfoLabel.TLabel"
        )
        self.percentage_label.pack(side=tk.LEFT, padx=2)
        
        # Initially hide the transition progress
        self.transition_frame.grid_remove()
        
        # Configure grid
        main_frame.columnconfigure(2, weight=1)
        
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
                self.detailed_label.grid()
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
                    self.transition_frame.grid()
                    self.is_transition = True
            else:
                # Hide transition progress
                if self.is_transition:
                    self.transition_frame.grid_remove()
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

# Note: The following classes have been moved to separate files:
# - ControlPanel -> front_end_components/control_tab.py
# - ImageViewerPanel -> front_end_components/images_tab.py  
# - SysMonitorPanel -> front_end_components/monitor_tab.py