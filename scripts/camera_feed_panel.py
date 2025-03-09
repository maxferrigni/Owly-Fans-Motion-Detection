# File: camera_feed_panel.py
# Purpose: Simple base image display panel - Version 1.5.3
# Version: 1.5.3
# 
# Update in v1.5.3:
# - Completely redesigned to show only base images
# - Simplified frame structure
# - Removed monitoring functionality
# - Improved error handling

import tkinter as tk
from tkinter import ttk
import os
from datetime import datetime

from utilities.logging_utils import get_logger
from utilities.constants import CAMERA_MAPPINGS, get_base_image_path
from simple_image_viewer import SimpleImageViewer

class BaseImagesPanel(ttk.LabelFrame):
    """Simple panel to display current base images"""
    
    def __init__(self, parent, logger=None):
        super().__init__(parent, text="Current Base Images")
        
        self.logger = logger or get_logger()
        self.viewers = {}
        
        # Create panel components
        self.create_interface()
        
    def create_interface(self):
        """Create simple interface for base images"""
        try:
            # Create a single main frame
            main_frame = ttk.Frame(self)
            main_frame.pack(fill="both", expand=True, padx=5, pady=5)
            
            # Create a viewer for each camera type
            camera_names = list(CAMERA_MAPPINGS.keys())
            
            # Create a grid layout for images
            for i, camera_name in enumerate(camera_names):
                # Create image viewer with title
                title = f"{camera_name}"
                viewer = SimpleImageViewer(main_frame, title)
                viewer.grid(row=i//3, column=i%3, padx=10, pady=10, sticky="nw")
                
                # Store reference to viewer
                self.viewers[camera_name] = viewer
            
            # Configure grid weights
            for i in range((len(camera_names) + 2) // 3):
                main_frame.rowconfigure(i, weight=1)
            for i in range(min(3, len(camera_names))):
                main_frame.columnconfigure(i, weight=1)
                
            # Add update button
            control_frame = ttk.Frame(self)
            control_frame.pack(fill="x", padx=5, pady=5)
            
            update_btn = ttk.Button(
                control_frame,
                text="Update Base Images",
                command=self.update_images
            )
            update_btn.pack(side=tk.LEFT, padx=5)
            
            # Add last update time label
            self.last_update_label = ttk.Label(
                control_frame,
                text="Last updated: Never"
            )
            self.last_update_label.pack(side=tk.RIGHT, padx=5)
            
            # Run initial update
            self.update_images()
                
            self.logger.info("Base images panel initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error creating base images panel: {e}")
            error_label = ttk.Label(
                self,
                text=f"Error initializing base images panel: {e}",
                foreground="red"
            )
            error_label.pack(padx=10, pady=10)
    
    def update_images(self):
        """Update all viewers with the current base images"""
        try:
            update_time = datetime.now().strftime('%H:%M:%S')
            lighting_conditions = ['day', 'night', 'transition']
            
            # Get base images for each camera and lighting condition
            for camera_name, viewer in self.viewers.items():
                try:
                    # Load day base image by default
                    viewer.load_base_image(camera_name, 'day', max_size=(250, 200))
                        
                except Exception as e:
                    self.logger.error(f"Error updating base image for {camera_name}: {e}")
            
            # Update last update time
            self.last_update_label.config(text=f"Last updated: {update_time}")
            self.logger.info(f"Base images updated at {update_time}")
                
        except Exception as e:
            self.logger.error(f"Error updating base images: {e}")
    
    def destroy(self):
        """Clean up resources when panel is destroyed"""
        super().destroy()


if __name__ == "__main__":
    # Test code for standalone testing
    root = tk.Tk()
    root.title("Base Images Panel Test")
    
    # Create logger
    try:
        from utilities.logging_utils import get_logger
        logger = get_logger()
    except:
        import logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger()
    
    # Create panel
    panel = BaseImagesPanel(root, logger)
    panel.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Start the main loop
    root.mainloop()