# File: _front_end.py
# Purpose: Entry point for the Owl Monitoring System GUI

import tkinter as tk
import sys
import os
from utilities.logging_utils import get_logger
from _front_end_app import OwlApp

if __name__ == "__main__":
    try:
        # Initialize root window
        root = tk.Tk()
        
        # Initialize logger
        logger = get_logger()
        logger.info("Tkinter root window created")
        
        # Short delay for window manager
        root.after(100)
        
        # Create application
        app = OwlApp(root)
        
        # Log final window geometry
        logger.info(f"Final window geometry: {root.geometry()}")
        
        # Start main loop
        root.mainloop()
        
    except Exception as e:
        print(f"Fatal error in GUI: {e}")
        raise