# File: scripts/front_end_image_viewer.py
# Purpose: Simple component for displaying base images and alert images
# in the Owl Monitoring System GUI
#
# March 7, 2025 Update - Version 1.4.1
# - Fixed image sizing for the bottom panel
# - Improved layout and spacing for better display
# - Added fixed dimensions for consistent UI appearance

import tkinter as tk
from tkinter import ttk
import os
import time
from PIL import Image, ImageTk
from datetime import datetime

# Import utilities
from utilities.logging_utils import get_logger
from utilities.constants import (
    BASE_IMAGES_DIR, 
    IMAGE_COMPARISONS_DIR,
    get_base_image_path, 
    COMPARISON_IMAGE_FILENAMES
)

class ImageViewer:
    """
    Simple component for displaying base images and alert images
    """
    def __init__(self, parent_frame, camera_configs):
        self.parent_frame = parent_frame
        self.camera_configs = camera_configs
        self.logger = get_logger()
        
        # Photo references to prevent garbage collection
        self.photo_refs = {}
        
        # Create the interface
        self.create_interface()
        
        # Load images initially
        self.load_all_images()
        
        # Set up auto-refresh every 60 seconds
        self.parent_frame.after(60000, self.refresh_images)
    
    def create_interface(self):
        """Create the basic interface layout with compact design"""
        # Main container with horizontal layout
        self.main_frame = ttk.Frame(self.parent_frame)
        self.main_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Left side - Base images (with fixed width)
        self.base_frame = ttk.LabelFrame(self.main_frame, text="Base Images")
        self.base_frame.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        
        # Image containers for base images (day, night, transition)
        self.base_images_frame = ttk.Frame(self.base_frame)
        self.base_images_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        self.base_labels = {}
        
        # Create smaller, more compact image containers
        for i, condition in enumerate(["day", "night", "transition"]):
            frame = ttk.Frame(self.base_images_frame)
            frame.grid(row=0, column=i, padx=2, pady=2, sticky="nsew")
            
            # Condition label with smaller font
            ttk.Label(
                frame, 
                text=condition.capitalize(),
                font=("Arial", 8)  # Smaller font
            ).pack(pady=1)
            
            # Image container with fixed size
            label = ttk.Label(frame)
            label.pack(fill="both", expand=True)
            self.base_labels[condition] = label
        
        # Configure grid to distribute space evenly
        for i in range(3):
            self.base_images_frame.columnconfigure(i, weight=1)
        
        # Right side - Latest comparison image (with fixed width)
        self.comp_frame = ttk.LabelFrame(self.main_frame, text="Latest Alert")
        self.comp_frame.pack(side="right", fill="both", expand=True, padx=2, pady=2)
        
        # Single comparison image
        self.comp_label = ttk.Label(self.comp_frame)
        self.comp_label.pack(fill="both", expand=True)
    
    def load_all_images(self):
        """Load all images (base and comparison)"""
        self.load_base_images()
        self.load_comparison_image()
    
    def load_base_images(self):
        """Load base images for all conditions with optimized sizing"""
        try:
            # Get the first camera from configs
            camera_name = next(iter(self.camera_configs)) if self.camera_configs else "Wyze Internal Camera"
            
            # Load base images for each lighting condition
            for condition in ["day", "night", "transition"]:
                try:
                    # Get the path for this condition
                    image_path = get_base_image_path(camera_name, condition)
                    
                    # Check if file exists
                    if os.path.exists(image_path):
                        self.logger.debug(f"Loading {condition} base image: {image_path}")
                        
                        # Load and resize image - smaller size for compact display
                        img = Image.open(image_path)
                        img = img.resize((120, 80), Image.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        
                        # Store reference and update label
                        self.photo_refs[f"base_{condition}"] = photo
                        self.base_labels[condition].configure(image=photo)
                    else:
                        self.logger.debug(f"Base image not found: {image_path}")
                        self.base_labels[condition].configure(text=f"No {condition} image")
                except Exception as e:
                    self.logger.error(f"Error loading {condition} base image: {e}")
                    self.base_labels[condition].configure(text=f"Error loading")
        except Exception as e:
            self.logger.error(f"Error loading base images: {e}")
    
    def load_comparison_image(self):
        """Load the latest comparison/alert image with optimized sizing"""
        try:
            # Find the most recent comparison image
            latest_file = None
            latest_time = 0
            
            for filename in COMPARISON_IMAGE_FILENAMES.values():
                file_path = os.path.join(IMAGE_COMPARISONS_DIR, filename)
                if os.path.exists(file_path):
                    mod_time = os.path.getmtime(file_path)
                    if mod_time > latest_time:
                        latest_time = mod_time
                        latest_file = file_path
            
            # If we found a file, load it
            if latest_file and os.path.exists(latest_file):
                self.logger.debug(f"Loading comparison image: {latest_file}")
                
                # Load and resize the image
                img = Image.open(latest_file)
                
                # Get available width - restrict to reasonable size for the panel
                available_width = 250  # Fixed reasonable width
                
                # Calculate new dimensions keeping aspect ratio
                width, height = img.size
                new_width = min(available_width, width)
                new_height = int(height * (new_width / width))
                
                # Cap height to avoid oversized images
                if new_height > 150:
                    new_height = 150
                    new_width = int(width * (new_height / height))
                
                # Resize and display
                img_resized = img.resize((new_width, new_height), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img_resized)
                
                # Store reference and update label
                self.photo_refs["comparison"] = photo
                self.comp_label.configure(image=photo)
            else:
                self.logger.debug("No comparison images found")
                self.comp_label.configure(text="No alert images found")
        except Exception as e:
            self.logger.error(f"Error loading comparison image: {e}")
            self.comp_label.configure(text="Error loading alert image")
    
    def refresh_images(self):
        """Refresh all images"""
        try:
            self.load_all_images()
        except Exception as e:
            self.logger.error(f"Error refreshing images: {e}")
        
        # Schedule next refresh
        self.parent_frame.after(60000, self.refresh_images)

# For testing the component directly
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Image Viewer Test")
    root.geometry("800x200")  # Reduced height to match intended panel size
    
    # Sample configs
    sample_configs = {
        "Wyze Internal Camera": {"roi": [-1899, 698, -1255, 1039]},
        "Bindy Patio Camera": {"roi": [1441, 350, 1636, 526]},
        "Upper Patio Camera": {"roi": [395, 454, 900, 680]}
    }
    
    # Create frame
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)
    
    # Create viewer
    viewer = ImageViewer(frame, sample_configs)
    
    root.mainloop()