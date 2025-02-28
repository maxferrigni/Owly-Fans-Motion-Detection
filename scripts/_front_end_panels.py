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