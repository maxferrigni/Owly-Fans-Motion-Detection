# File: camera_feed_panel.py
# Purpose: Organize and display camera feeds and comparison images
# Version: 1.5.1

import tkinter as tk
from tkinter import ttk
import os
import threading
import time
from datetime import datetime
from PIL import Image, ImageTk

from utilities.logging_utils import get_logger
from utilities.constants import IMAGE_COMPARISONS_DIR, CAMERA_MAPPINGS
from simple_image_viewer import SimpleImageViewer

class CameraFeedPanel(ttk.LabelFrame):
    """Panel to display camera feeds and comparison images"""
    
    def __init__(self, parent, logger=None):
        super().__init__(parent, text="Camera Feeds")
        
        self.logger = logger or get_logger()
        self.viewers = {}
        self.comparison_paths = {}
        self.update_thread = None
        self.running = False
        
        # Create panel components
        self.create_interface()
        
    def create_interface(self):
        """Create the camera feed interface components"""
        try:
            # Create main container
            main_frame = ttk.Frame(self)
            main_frame.pack(fill="both", expand=True, padx=5, pady=5)
            
            # Create a viewer for each camera
            camera_names = list(CAMERA_MAPPINGS.keys())
            
            # Determine layout based on number of cameras
            num_cameras = len(camera_names)
            cols = min(2, num_cameras)  # Maximum 2 columns
            rows = (num_cameras + cols - 1) // cols  # Ceiling division
            
            # Create a grid of viewers
            for i, camera_name in enumerate(camera_names):
                row = i // cols
                col = i % cols
                
                # Create frame for this camera
                camera_frame = ttk.LabelFrame(main_frame, text=camera_name)
                camera_frame.grid(row=row, col=col, padx=5, pady=5, sticky="nsew")
                
                # Add image viewer
                viewer = SimpleImageViewer(camera_frame, f"{CAMERA_MAPPINGS[camera_name]} Camera")
                viewer.pack(fill="both", expand=True, padx=5, pady=5)
                
                # Store reference to viewer
                self.viewers[camera_name] = viewer
                
                # Initial message
                self.comparison_paths[camera_name] = None
            
            # Configure grid weights
            for i in range(rows):
                main_frame.rowconfigure(i, weight=1)
            for i in range(cols):
                main_frame.columnconfigure(i, weight=1)
                
            # Add update controls
            control_frame = ttk.Frame(self)
            control_frame.pack(fill="x", padx=5, pady=5)
            
            # Add auto-update checkbox
            self.auto_update = tk.BooleanVar(value=True)
            auto_cb = ttk.Checkbutton(
                control_frame,
                text="Auto-update images",
                variable=self.auto_update,
                command=self.toggle_auto_update
            )
            auto_cb.pack(side=tk.LEFT, padx=5)
            
            # Add manual update button
            update_btn = ttk.Button(
                control_frame,
                text="Update Now",
                command=self.update_images
            )
            update_btn.pack(side=tk.LEFT, padx=5)
            
            # Add last update time label
            self.last_update_label = ttk.Label(
                control_frame,
                text="Last updated: Never"
            )
            self.last_update_label.pack(side=tk.RIGHT, padx=5)
            
            # Start auto-update if enabled
            if self.auto_update.get():
                self.start_auto_update()
                
            self.logger.info("Camera feed panel initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error creating camera feed interface: {e}")
            error_label = ttk.Label(
                self,
                text=f"Error initializing camera feed panel: {e}",
                foreground="red"
            )
            error_label.pack(padx=10, pady=10)
    
    def update_images(self):
        """Update all image viewers with the latest comparison images"""
        try:
            update_time = datetime.now().strftime('%H:%M:%S')
            images_updated = False
            
            for camera_name, viewer in self.viewers.items():
                try:
                    # Get the alert type for this camera
                    alert_type = CAMERA_MAPPINGS.get(camera_name)
                    if not alert_type:
                        continue
                    
                    # Construct expected path for comparison image
                    alert_type_clean = alert_type.lower().replace(' ', '_')
                    comparison_filename = f"{alert_type_clean}_comparison.jpg"
                    comparison_path = os.path.join(IMAGE_COMPARISONS_DIR, comparison_filename)
                    
                    # Check if file exists and has been modified since last update
                    if os.path.exists(comparison_path):
                        if (self.comparison_paths.get(camera_name) != comparison_path or
                            (self.comparison_paths.get(camera_name) == comparison_path and
                             os.path.getmtime(comparison_path) > viewer.last_update_time)):
                            
                            # Load the image
                            max_size = (400, 300)  # Larger display size for main panel
                            if viewer.load_image(comparison_path, max_size):
                                self.comparison_paths[camera_name] = comparison_path
                                images_updated = True
                                self.logger.debug(f"Updated image for {camera_name}")
                    else:
                        self.logger.debug(f"Comparison image not found for {camera_name}: {comparison_path}")
                        
                except Exception as e:
                    self.logger.error(f"Error updating image for {camera_name}: {e}")
            
            # Update last update time if any images were updated
            if images_updated:
                self.last_update_label.config(text=f"Last updated: {update_time}")
                
        except Exception as e:
            self.logger.error(f"Error updating images: {e}")
    
    def toggle_auto_update(self):
        """Toggle automatic image updates"""
        try:
            if self.auto_update.get():
                self.start_auto_update()
            else:
                self.stop_auto_update()
        except Exception as e:
            self.logger.error(f"Error toggling auto-update: {e}")
    
    def start_auto_update(self):
        """Start auto-update thread"""
        if self.update_thread and self.update_thread.is_alive():
            return  # Already running
            
        self.running = True
        self.update_thread = threading.Thread(target=self.auto_update_loop, daemon=True)
        self.update_thread.start()
        self.logger.info("Auto-update started")
    
    def stop_auto_update(self):
        """Stop auto-update thread"""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=1)
        self.logger.info("Auto-update stopped")
    
    def auto_update_loop(self):
        """Background thread to update images periodically"""
        update_interval = 5  # seconds
        
        while self.running:
            try:
                # Update images
                self.update_images()
                
                # Sleep in small increments to allow for clean shutdown
                for _ in range(update_interval * 10):  # 10 checks per second
                    if not self.running:
                        break
                    time.sleep(0.1)
                    
            except Exception as e:
                self.logger.error(f"Error in auto-update loop: {e}")
                # Sleep before retry
                time.sleep(update_interval)
    
    def destroy(self):
        """Clean up resources when panel is destroyed"""
        self.stop_auto_update()
        super().destroy()


if __name__ == "__main__":
    # Test code for standalone testing
    root = tk.Tk()
    root.title("Camera Feed Panel Test")
    
    # Create logger
    try:
        from utilities.logging_utils import get_logger
        logger = get_logger()
    except:
        import logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger()
    
    # Create panel
    panel = CameraFeedPanel(root, logger)
    panel.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Start the main loop
    root.mainloop()