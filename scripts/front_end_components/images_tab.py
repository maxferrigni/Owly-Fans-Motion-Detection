# File: scripts/front_end_components/images_tab.py
# Purpose: Images tab component for the Owl Monitoring System GUI
# 
# March 17, 2025 Update - Version 1.4.1
# - Extracted from front_end_app.py and front_end_panels.py
# - Centralized image viewing functionality

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os
from datetime import datetime
import threading
import time

from utilities.logging_utils import get_logger
from utilities.constants import CAMERA_MAPPINGS, get_comparison_image_path


class ImagesTab(ttk.Frame):
    """Tab containing image viewer for comparison images"""
    
    def __init__(self, parent, app_reference):
        """
        Initialize Images Tab
        
        Args:
            parent (ttk.Frame): Parent frame (typically the notebook tab)
            app_reference: Reference to the main application for callbacks
        """
        super().__init__(parent)
        self.parent = parent
        self.app = app_reference
        self.logger = get_logger()
        
        # Create the image viewer panel
        self.image_viewer = ImageViewerPanel(self)
        self.image_viewer.pack(fill="both", expand=True)


class ImageViewerPanel(ttk.Frame):
    """
    Simple panel for displaying camera comparison images.
    Moved from front_end_panels.py
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.logger = get_logger()
        
        # Store image references to prevent garbage collection
        self.image_refs = {
            "Wyze Internal Camera": None,
            "Bindy Patio Camera": None,
            "Upper Patio Camera": None
        }
        
        # Last modification times to detect changes
        self.last_modified = {
            "Wyze Internal Camera": 0,
            "Bindy Patio Camera": 0,
            "Upper Patio Camera": 0
        }
        
        # Create UI components
        self.create_layout()
        
        # Start refresh timer
        self.refresh_images()
        
    def create_layout(self):
        """Create simple layout with three image displays in vertical column"""
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create scrollable canvas for images
        self.canvas_frame = ttk.Frame(main_frame)
        self.canvas_frame.pack(fill="both", expand=True)
        
        # Create image frames - one for each camera (vertically stacked)
        self.camera_frames = {}
        self.image_labels = {}
        self.status_labels = {}
        
        # Set camera order: Wyze (top), Bindy (middle), Upper (bottom)
        camera_order = ["Wyze Internal Camera", "Bindy Patio Camera", "Upper Patio Camera"]
        
        for i, camera in enumerate(camera_order):
            # Create frame for this camera
            camera_frame = ttk.LabelFrame(self.canvas_frame, text=camera)
            camera_frame.pack(fill="x", pady=5)
            self.camera_frames[camera] = camera_frame
            
            # Add image label
            image_label = ttk.Label(camera_frame)
            image_label.pack(pady=2)
            self.image_labels[camera] = image_label
            
            # Add status label
            status_label = ttk.Label(
                camera_frame, 
                text="No image available", 
                font=("Arial", 8, "italic")
            )
            status_label.pack(pady=2)
            self.status_labels[camera] = status_label
    
    def load_image(self, camera):
        """
        Load comparison image for a specific camera.
        Returns True if image was updated.
        """
        try:
            # Get image path based on camera type
            image_path = get_comparison_image_path(camera)
            
            # Check if file exists
            if not os.path.exists(image_path):
                self.status_labels[camera].config(
                    text="No comparison image available"
                )
                return False
            
            # Check if file was modified since last load
            mod_time = os.path.getmtime(image_path)
            if mod_time <= self.last_modified[camera]:
                return False  # No update needed
            
            # Load and resize image
            image = Image.open(image_path)
            
            # Calculate new size to fit in frame
            # Target width around 850px (to fit in 900px window with margins)
            # Maintain aspect ratio
            width, height = image.size
            target_width = 850
            ratio = target_width / width
            new_size = (target_width, int(height * ratio))
            
            # Resize image
            resized = image.resize(new_size, Image.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(resized)
            
            # Update image label
            self.image_labels[camera].config(image=photo)
            
            # Store reference to prevent garbage collection
            self.image_refs[camera] = photo
            
            # Update last modified time
            self.last_modified[camera] = mod_time
            
            # Update status label with timestamp
            timestamp = datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M:%S")
            self.status_labels[camera].config(
                text=f"Last updated: {timestamp}"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading image for {camera}: {e}")
            self.status_labels[camera].config(
                text=f"Error loading image: {str(e)[:50]}..."
            )
            return False
    
    def refresh_images(self):
        """Refresh all camera images"""
        try:
            # Load images for all cameras
            updates = 0
            for camera in self.image_labels.keys():
                if self.load_image(camera):
                    updates += 1
                    
            # Schedule next refresh
            # Every 5 seconds if no updates, more frequently if updates found
            refresh_time = 1000 if updates > 0 else 5000
            self.after(refresh_time, self.refresh_images)
            
        except Exception as e:
            self.logger.error(f"Error refreshing images: {e}")
            # On error, retry after longer delay
            self.after(10000, self.refresh_images)