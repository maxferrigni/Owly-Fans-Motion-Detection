# File: scripts/front_end_image_viewer.py
# Purpose: Simple component for displaying base images and alert images
# in the Owl Monitoring System GUI
#
# March 7, 2025 Update - Version 1.4.3
# - Complete redesign for improved reliability
# - Fixed image loading and display logic
# - Added explicit sizing constraints
# - Improved error handling throughout

import tkinter as tk
from tkinter import ttk
import os
import time
import threading
import traceback
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

class ImageViewer(ttk.Frame):
    """
    Simple component for displaying base images and alert images.
    Completely redesigned for reliability in v1.4.3.
    """
    def __init__(self, parent_frame, camera_configs):
        # Initialize as a ttk.Frame (subclass)
        super().__init__(parent_frame)
        
        # Store parameters
        self.parent_frame = parent_frame
        self.camera_configs = camera_configs
        self.logger = get_logger()
        
        # Track images and references
        self.photo_refs = {}  # Prevent garbage collection
        self.image_paths = {
            "day": None,
            "night": None,
            "transition": None,
            "comparison": None
        }
        self.has_loaded = False  # Track if we've loaded images
        self.running = True
        
        # Create default "no image" photo
        self.create_no_image_photo()
        
        # Create the interface with fixed dimensions
        self.create_interface()
        
        # Load images in a separate thread with proper timeout
        self.load_thread = threading.Thread(target=self.load_all_images, daemon=True)
        self.load_thread.start()
        
        # Rather than starting an infinite loop with after(), use a single delayed update
        # This ensures we don't block the UI thread or cause hangs
        self.after(15000, self.schedule_single_refresh)
    
    def create_no_image_photo(self):
        """Create a default "No Image" display as fallback"""
        try:
            # Create a simple "No Image" indicator
            no_image = Image.new('RGB', (120, 80), color=(240, 240, 240))
            
            # Set up basic drawing
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(no_image)
            draw.rectangle([0, 0, 119, 79], outline=(200, 200, 200), width=1)
            draw.text((30, 35), "No Image", fill=(100, 100, 100))
            
            # Convert to PhotoImage and store
            self.no_image_photo = ImageTk.PhotoImage(no_image)
        except Exception as e:
            self.logger.error(f"Error creating no-image placeholder: {e}")
            # If we can't create a placeholder, we'll handle this elsewhere
            self.no_image_photo = None
    
    def create_interface(self):
        """Create the UI layout with proper sizing constraints"""
        try:
            # Main horizontal layout - Split into two equal sections
            self.configure(height=175)  # Set fixed height

            # Base images panel (left side)
            self.base_panel = ttk.LabelFrame(self, text="Base Images")
            self.base_panel.pack(side="left", fill="both", expand=True, padx=2, pady=2)
            
            # Comparison image panel (right side)
            self.alert_panel = ttk.LabelFrame(self, text="Latest Alert")
            self.alert_panel.pack(side="right", fill="both", expand=True, padx=2, pady=2)
            
            # Create base image containers (3 columns for day, night, transition)
            self.base_frame = ttk.Frame(self.base_panel)
            self.base_frame.pack(fill="both", expand=True, padx=2, pady=2)
            
            # Create image labels
            self.base_labels = {}
            
            # Create the three image positions with informative labels
            for i, condition in enumerate(["day", "night", "transition"]):
                frame = ttk.Frame(self.base_frame)
                frame.grid(row=0, column=i, padx=2, pady=2, sticky="nsew")
                
                # Add condition label
                ttk.Label(
                    frame, 
                    text=condition.capitalize(),
                    font=("Arial", 8)
                ).pack(pady=1)
                
                # Create label with fixed dimensions
                label = ttk.Label(frame)
                label.pack(padx=2, pady=2)
                
                # Set a default "loading" message
                label.configure(text="Loading...", compound="center")
                
                # Store the label reference
                self.base_labels[condition] = label
            
            # Configure base frame grid to distribute space evenly
            for i in range(3):
                self.base_frame.columnconfigure(i, weight=1)
            
            # Create comparison image container
            self.comparison_label = ttk.Label(self.alert_panel)
            self.comparison_label.pack(fill="both", expand=True, padx=2, pady=2)
            self.comparison_label.configure(text="Loading...", compound="center")
            
            # Set initial "no image" photos if available
            if hasattr(self, 'no_image_photo') and self.no_image_photo:
                for condition in ["day", "night", "transition"]:
                    self.base_labels[condition].configure(image=self.no_image_photo, text="")
                self.comparison_label.configure(image=self.no_image_photo, text="")
            
        except Exception as e:
            self.logger.error(f"Error creating image viewer interface: {e}")
            self.logger.error(traceback.format_exc())
    
    def load_all_images(self):
        """Load all images safely, with error handling for each image"""
        try:
            # Get the first camera from configs
            camera_name = next(iter(self.camera_configs)) if self.camera_configs else "Wyze Internal Camera"
            
            # Load each type of image separately with its own error handling
            if self.running:
                self.load_base_image(camera_name, "day")
            if self.running:
                self.load_base_image(camera_name, "night")
            if self.running:
                self.load_base_image(camera_name, "transition")
            if self.running:
                self.load_comparison_image()
            
            # Mark that we've loaded images
            self.has_loaded = True
            
        except Exception as e:
            self.logger.error(f"Error in load_all_images: {e}")
            self.logger.error(traceback.format_exc())
    
    def load_base_image(self, camera_name, condition):
        """Load a single base image with robust error handling"""
        try:
            # Get the path for this image
            image_path = get_base_image_path(camera_name, condition)
            self.image_paths[condition] = image_path
            
            # Check if file exists
            if not os.path.exists(image_path):
                self.logger.warning(f"Base image not found: {image_path}")
                # Use "No Image" placeholder
                if hasattr(self, 'no_image_photo') and self.no_image_photo:
                    self.update_image_display(condition, None, f"No {condition} image")
                return
            
            # Try to load and resize the image
            try:
                # Load image
                img = Image.open(image_path).convert("RGB")
                
                # Resize to small dimensions for the panel
                img = img.resize((120, 80), Image.LANCZOS)
                
                # Convert to PhotoImage and store reference
                photo = ImageTk.PhotoImage(img)
                self.photo_refs[f"base_{condition}"] = photo
                
                # Update the label safely on the main thread
                if self.running:
                    self.after_idle(lambda: self.update_image_display(condition, photo))
                
            except Exception as img_error:
                self.logger.error(f"Error loading {condition} image: {img_error}")
                # Use fallback image
                if hasattr(self, 'no_image_photo') and self.no_image_photo:
                    self.update_image_display(condition, None, f"Error: {condition}")
            
        except Exception as e:
            self.logger.error(f"Error in load_base_image({condition}): {e}")
    
    def load_comparison_image(self):
        """Load the latest comparison/alert image with error handling"""
        try:
            # Find the most recent comparison image
            latest_file = None
            latest_time = 0
            
            # Check each comparison image type
            for filename in COMPARISON_IMAGE_FILENAMES.values():
                file_path = os.path.join(IMAGE_COMPARISONS_DIR, filename)
                if os.path.exists(file_path):
                    mod_time = os.path.getmtime(file_path)
                    if mod_time > latest_time:
                        latest_time = mod_time
                        latest_file = file_path
            
            # Update stored path
            self.image_paths["comparison"] = latest_file
            
            # If we found a file, load it
            if latest_file and os.path.exists(latest_file):
                try:
                    # Load and resize the image
                    img = Image.open(latest_file).convert("RGB")
                    
                    # Get available width - restrict to reasonable size
                    img_width, img_height = img.size
                    
                    # Calculate new dimensions keeping aspect ratio
                    # Height is more constrained in our layout
                    max_height = 130  # Maximum height for the panel
                    scale_factor = max_height / img_height
                    new_width = int(img_width * scale_factor)
                    new_height = max_height
                    
                    # Resize the image
                    img_resized = img.resize((new_width, new_height), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img_resized)
                    
                    # Store reference and update label safely on main thread
                    self.photo_refs["comparison"] = photo
                    if self.running:
                        self.after_idle(lambda: self.update_comparison_display(photo))
                    
                except Exception as img_error:
                    self.logger.error(f"Error loading comparison image: {img_error}")
                    # Use fallback image
                    if hasattr(self, 'no_image_photo') and self.no_image_photo:
                        self.update_comparison_display(None, "Error loading")
            else:
                self.logger.debug("No comparison images found")
                # Use fallback image
                if hasattr(self, 'no_image_photo') and self.no_image_photo:
                    self.update_comparison_display(None, "No alert images")
                
        except Exception as e:
            self.logger.error(f"Error in load_comparison_image: {e}")
    
    def update_image_display(self, condition, photo, text=None):
        """Update a single base image display safely"""
        if not self.running:
            return
            
        try:
            if condition in self.base_labels:
                label = self.base_labels[condition]
                
                if photo:
                    label.configure(image=photo, text="", compound="image")
                elif text:
                    # If no photo but we have text, display text
                    if hasattr(self, 'no_image_photo') and self.no_image_photo:
                        label.configure(image=self.no_image_photo, text=text, compound="center")
                    else:
                        label.configure(image="", text=text)
        except Exception as e:
            self.logger.error(f"Error updating {condition} image display: {e}")
    
    def update_comparison_display(self, photo, text=None):
        """Update the comparison image display safely"""
        if not self.running:
            return
            
        try:
            if photo:
                self.comparison_label.configure(image=photo, text="", compound="image")
            elif text:
                # If no photo but we have text, display text
                if hasattr(self, 'no_image_photo') and self.no_image_photo:
                    self.comparison_label.configure(image=self.no_image_photo, text=text, compound="center")
                else:
                    self.comparison_label.configure(image="", text=text)
        except Exception as e:
            self.logger.error(f"Error updating comparison display: {e}")
    
    def schedule_single_refresh(self):
        """Schedule a single refresh, not a recurring one"""
        try:
            # Only refresh if we're still running
            if self.running:
                # Refresh in a background thread
                refresh_thread = threading.Thread(target=self.refresh_images, daemon=True)
                refresh_thread.start()
                
                # Schedule another single refresh in 20 seconds
                self.after(20000, self.schedule_single_refresh)
        except Exception as e:
            self.logger.error(f"Error scheduling refresh: {e}")
            # Try again in 60 seconds if there was an error
            self.after(60000, self.schedule_single_refresh)
    
    def refresh_images(self):
        """Refresh all images with checks for changes"""
        try:
            # Skip if not running
            if not self.running:
                return
                
            # Skip if we never loaded images successfully
            if not self.has_loaded:
                return
                
            # Get the first camera from configs
            camera_name = next(iter(self.camera_configs)) if self.camera_configs else "Wyze Internal Camera"
            
            # Check each image for changes
            self.check_and_reload_image(camera_name, "day")
            self.check_and_reload_image(camera_name, "night")
            self.check_and_reload_image(camera_name, "transition")
            self.check_and_reload_comparison()
            
        except Exception as e:
            self.logger.error(f"Error refreshing images: {e}")
    
    def check_and_reload_image(self, camera_name, condition):
        """Check if an image has changed and reload if needed"""
        try:
            # Skip if not running
            if not self.running:
                return
                
            # Get path for the base image
            image_path = get_base_image_path(camera_name, condition)
            
            # Check if file exists
            if not os.path.exists(image_path):
                return
                
            # Check if path has changed or file was modified
            if (self.image_paths[condition] != image_path or
                (self.image_paths[condition] and 
                 os.path.getmtime(image_path) > os.path.getmtime(self.image_paths[condition]))):
                # Image has changed, reload it
                self.load_base_image(camera_name, condition)
                
        except Exception as e:
            self.logger.error(f"Error checking {condition} image for changes: {e}")
    
    def check_and_reload_comparison(self):
        """Check if comparison image has changed and reload if needed"""
        try:
            # Skip if not running
            if not self.running:
                return
                
            # Find the most recent comparison image
            latest_file = None
            latest_time = 0
            
            # Check each comparison image type
            for filename in COMPARISON_IMAGE_FILENAMES.values():
                file_path = os.path.join(IMAGE_COMPARISONS_DIR, filename)
                if os.path.exists(file_path):
                    mod_time = os.path.getmtime(file_path)
                    if mod_time > latest_time:
                        latest_time = mod_time
                        latest_file = file_path
            
            # If no comparison images found
            if not latest_file:
                return
                
            # Check if path has changed or file was modified
            current_path = self.image_paths["comparison"]
            if (current_path != latest_file or
                (current_path and latest_file and 
                 os.path.getmtime(latest_file) > os.path.getmtime(current_path))):
                # Comparison image has changed, reload it
                self.load_comparison_image()
                
        except Exception as e:
            self.logger.error(f"Error checking comparison image for changes: {e}")
    
    def destroy(self):
        """Clean up resources when destroyed"""
        self.running = False
        super().destroy()