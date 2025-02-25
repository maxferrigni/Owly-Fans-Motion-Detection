# File: _front_end_panels.py
# Purpose: Reusable GUI components for the Owl Monitoring System

import tkinter as tk
from tkinter import scrolledtext, ttk
from datetime import datetime

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
            font=('Consolas', 10)  # Changed to Consolas for better readability
        )
        self.log_display.pack(fill="both", expand=True)
        
        # Configure tags for coloring - using more visible colors
        self.log_display.tag_configure("ERROR", foreground="#FF0000")  # Bright red
        self.log_display.tag_configure("WARNING", foreground="#FF8C00")  # Dark orange
        self.log_display.tag_configure("INFO", foreground="#000080")  # Navy blue
        self.log_display.tag_configure("HIGHLIGHT", background="#FFFF00")  # Yellow highlight
        
        # Configure the base text color and background
        self.log_display.config(bg="#F8F8F8", fg="#000000")  # Light gray background, black text

    def apply_filters(self):
        """Apply all active filters to log display"""
        # Get current filters
        level = self.level_var.get()
        search = self.search_var.get().lower()
        
        # Fixed: Properly show/hide log entries based on level
        self.log_display.tag_remove("filtered", "1.0", tk.END)
        
        if level != "ALL":
            for tag in ["ERROR", "WARNING", "INFO"]:
                if tag != level:
                    # Find all ranges with this tag
                    index = "1.0"
                    while True:
                        index = self.log_display.tag_nextrange(tag, index, tk.END)
                        if not index:
                            break
                        # Add filtered tag to hide these entries
                        self.log_display.tag_add("filtered", index[0], index[1])
                        index = index[1]
            
            # Configure the filtered tag to hide text
            self.log_display.tag_configure("filtered", elide=True)
        else:
            # Show all entries
            self.log_display.tag_configure("filtered", elide=False)
        
        # Apply search highlighting
        self.log_display.tag_remove("HIGHLIGHT", "1.0", tk.END)
        if search:
            pos = "1.0"
            while True:
                pos = self.log_display.search(search, pos, tk.END, nocase=True)
                if not pos:
                    break
                end_pos = f"{pos}+{len(search)}c"
                self.log_display.tag_add("HIGHLIGHT", pos, end_pos)
                pos = end_pos

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
        self.withdraw()
        
    def show(self):
        """Show the log window"""
        self.deiconify()
        self.position_window()

class AlertHierarchyFrame(ttk.LabelFrame):
    """Frame showing alert hierarchy and settings"""
    def __init__(self, parent, alert_manager):
        super().__init__(parent, text="Alert Hierarchy Settings")
        self.alert_manager = alert_manager
        
        # Create alert hierarchy display
        self.create_hierarchy_display()
        
        # Create delay settings
        self.create_delay_settings()

    def create_hierarchy_display(self):
        """Create display showing alert hierarchy"""
        # Using a more compact layout
        hierarchy_frame = ttk.Frame(self)
        hierarchy_frame.pack(fill="x", padx=5, pady=2)
        
        # Header with smaller font
        ttk.Label(
            hierarchy_frame,
            text="Alert Priority (Highest to Lowest):",
            font=('Arial', 8, 'bold')
        ).pack(anchor="w")
        
        # Priority list
        priorities = {
            "Owl In Box": "Highest Priority - Overrides All",
            "Owl On Box": "Medium Priority - Overrides Area",
            "Owl In Area": "Lowest Priority"
        }
        
        # More compact display of priorities
        for alert_type, description in priorities.items():
            frame = ttk.Frame(hierarchy_frame)
            frame.pack(fill="x", pady=1)
            ttk.Label(
                frame,
                text=f"• {alert_type}:",
                width=15
            ).pack(side="left")
            ttk.Label(
                frame,
                text=description,
                font=('Arial', 8, 'italic')
            ).pack(side="left")

    def create_delay_settings(self):
        """Create alert delay settings"""
        delay_frame = ttk.LabelFrame(self, text="Alert Delay Settings")
        delay_frame.pack(fill="x", padx=5, pady=2)
        
        # Base delay setting in a more compact layout
        base_delay_frame = ttk.Frame(delay_frame)
        base_delay_frame.pack(fill="x", pady=2)
        
        ttk.Label(
            base_delay_frame,
            text="Base Alert Delay:"
        ).pack(side="left")
        
        self.base_delay = ttk.Entry(
            base_delay_frame,
            width=5
        )
        self.base_delay.insert(0, "30")
        self.base_delay.pack(side="left", padx=5)
        
        ttk.Label(
            base_delay_frame,
            text="minutes"
        ).pack(side="left")
        
        # Help text with smaller font and more compact layout
        help_text = "Base delay applies to alerts of the same type. Higher priority alerts can override lower priority alerts."
        
        help_label = ttk.Label(
            delay_frame,
            text=help_text,
            wraplength=300,
            justify="left",
            font=('Arial', 8, 'italic')
        )
        help_label.pack(pady=2)

    def get_base_delay(self):
        """Get current base delay setting"""
        try:
            return int(self.base_delay.get())
        except ValueError:
            return 30  # Default value

class StatusPanel(ttk.LabelFrame):
    """Panel showing system status indicators"""
    def __init__(self, parent):
        super().__init__(parent, text="System Status")
        
        self.status_labels = {}
        self.create_status_indicators()
        self.create_control_buttons()

    def create_status_indicators(self):
        """Create system status indicators"""
        # Using a grid layout for more compact display
        indicators = [
            ("Motion Detection", "stopped"),
            ("Local Saving", "enabled"),
            ("Alert System", "ready"),
            ("Base Images", "not verified")
        ]
        
        # Create 2x2 grid for indicators
        for i, (label, initial_status) in enumerate(indicators):
            row = i // 2
            col = i % 2
            
            frame = ttk.Frame(self)
            frame.grid(row=row, column=col, sticky="w", padx=5, pady=2)
            
            ttk.Label(
                frame,
                text=f"{label}:",
                width=15
            ).pack(side="left")
            
            status_label = ttk.Label(frame, text=initial_status)
            status_label.pack(side="left")
            
            self.status_labels[label] = status_label

    def create_control_buttons(self):
        """Create control buttons"""
        button_frame = ttk.Frame(self)
        button_frame.grid(row=2, column=0, columnspan=2, sticky="e", pady=3)
        
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