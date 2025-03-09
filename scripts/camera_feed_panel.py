# File: camera_feed_panel.py
# Purpose: Simplified base image display panel - Version 1.5.4
# 
# Update in v1.5.4:
# - Fixed redundant base image display issue
# - Added proper timing for image display related to detection state
# - Improved error handling
# - Enhanced loading indicators

import tkinter as tk
from tkinter import ttk
import os
from datetime import datetime
import threading
import time

from utilities.logging_utils import get_logger
from utilities.constants import CAMERA_MAPPINGS, get_base_image_path
from PIL import Image, ImageTk

class BaseImagesPanel(ttk.LabelFrame):
    """
    Simplified panel to display base images for all cameras.
    In v1.5.4: Images are only displayed after detection starts.
    """
    
    def __init__(self, parent, logger=None):
        super().__init__(parent, text="Camera Base Images")
        
        self.logger = logger or get_logger()
        self.image_references = {}  # Store references to prevent garbage collection
        self.detection_active = False  # Track if detection is running
        self.refresh_timer = None  # Timer reference for auto-refresh
        
        # Create panel components
        self.create_interface()
        
    def create_interface(self):
        """Create simplified interface for base images"""
        try:
            # Main container
            self.main_frame = ttk.Frame(self)
            self.main_frame.pack(fill="both", expand=True, padx=5, pady=5)
            
            # Add status indicator
            self.status_frame = ttk.Frame(self.main_frame)
            self.status_frame.pack(fill="x", pady=(0, 5))
            
            self.status_var = tk.StringVar(value="Waiting for detection to start...")
            self.status_label = ttk.Label(
                self.status_frame, 
                textvariable=self.status_var,
                font=("Arial", 10, "italic"),
                foreground="gray"
            )
            self.status_label.pack(side=tk.LEFT)
            
            # Add refresh button
            self.refresh_button = ttk.Button(
                self.status_frame,
                text="Refresh Images",
                command=self.refresh_images,
                state=tk.DISABLED  # Disabled until detection starts
            )
            self.refresh_button.pack(side=tk.RIGHT, padx=5)
            
            # Create image grid
            self.images_frame = ttk.Frame(self.main_frame)
            self.images_frame.pack(fill="both", expand=True)
            
            # Initialize image holders
            self.image_panels = {}
            
            # Create a grid of image panels
            camera_names = sorted(CAMERA_MAPPINGS.keys())
            
            for i, camera_name in enumerate(camera_names):
                # Create a labeled frame for each camera
                camera_frame = ttk.LabelFrame(self.images_frame, text=camera_name)
                camera_frame.grid(row=i//3, column=i%3, padx=5, pady=5, sticky="nsew")
                
                # Create placeholder frame with fixed size
                placeholder_frame = ttk.Frame(camera_frame, width=200, height=150)
                placeholder_frame.pack(padx=5, pady=5)
                placeholder_frame.pack_propagate(False)  # Maintain size
                
                # Add placeholder message
                placeholder_label = ttk.Label(
                    placeholder_frame,
                    text="Base image will appear\nafter detection starts",
                    justify="center"
                )
                placeholder_label.place(relx=0.5, rely=0.5, anchor="center")
                
                # Store references
                self.image_panels[camera_name] = {
                    "frame": placeholder_frame,
                    "placeholder": placeholder_label,
                    "image_label": None  # Will be created when needed
                }
            
            # Configure grid weights
            for i in range((len(camera_names) + 2) // 3):
                self.images_frame.rowconfigure(i, weight=1)
            for i in range(min(3, len(camera_names))):
                self.images_frame.columnconfigure(i, weight=1)
            
            # Add last update time indicator
            self.last_update_var = tk.StringVar(value="Detection not active")
            last_update_label = ttk.Label(
                self.main_frame,
                textvariable=self.last_update_var,
                font=("Arial", 8),
                foreground="gray"
            )
            last_update_label.pack(side=tk.LEFT, padx=5, pady=(5, 0))
            
            self.logger.info("Base images panel initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error creating base images panel: {e}")
            error_label = ttk.Label(
                self,
                text=f"Error initializing panel: {str(e)}",
                foreground="red",
                wraplength=300
            )
            error_label.pack(padx=10, pady=10)
    
    def detection_started(self):
        """Called when detection script starts"""
        self.detection_active = True
        self.status_var.set("Loading base images...")
        self.refresh_button.config(state=tk.NORMAL)
        
        # Schedule image loading after a short delay
        # This gives time for base images to be created
        self.after(2000, self.load_base_images)
    
    def detection_stopped(self):
        """Called when detection script stops"""
        self.detection_active = False
        self.status_var.set("Waiting for detection to start...")
        self.refresh_button.config(state=tk.DISABLED)
        self.last_update_var.set("Detection not active")
        
        # Cancel any pending refresh timer
        if self.refresh_timer:
            self.after_cancel(self.refresh_timer)
            self.refresh_timer = None
        
        # Clear all images and show placeholders
        self.clear_images()
    
    def clear_images(self):
        """Clear all images and show placeholders"""
        for camera_name, components in self.image_panels.items():
            # Remove image label if it exists
            if components["image_label"] is not None:
                components["image_label"].destroy()
                components["image_label"] = None
            
            # Show placeholder
            components["placeholder"].config(text="Base image will appear\nafter detection starts")
            components["placeholder"].place(relx=0.5, rely=0.5, anchor="center")
        
        # Clear image references to release memory
        self.image_references.clear()
    
    def load_base_images(self):
        """Load and display base images"""
        if not self.detection_active:
            return
        
        try:
            # Update status
            self.status_var.set("Loading base images...")
            
            # Get latest condition with base images
            latest_condition = self.get_latest_base_image_condition()
            
            found_images = False
            
            # Process each camera
            for camera_name, components in self.image_panels.items():
                try:
                    # Get the base image path
                    image_path = get_base_image_path(camera_name, latest_condition)
                    
                    # Check if file exists
                    if os.path.exists(image_path):
                        found_images = True
                        # Load and resize image
                        img = Image.open(image_path)
                        img.thumbnail((200, 150), Image.LANCZOS)
                        
                        # Convert to PhotoImage
                        photo = ImageTk.PhotoImage(img)
                        
                        # Hide placeholder
                        components["placeholder"].place_forget()
                        
                        # Create or update image label
                        if components["image_label"] is None:
                            components["image_label"] = ttk.Label(components["frame"])
                            components["image_label"].pack(fill="both", expand=True)
                        
                        # Update image
                        components["image_label"].config(image=photo)
                        
                        # Keep reference to prevent garbage collection
                        self.image_references[camera_name] = photo
                    else:
                        # No image found - show placeholder with message
                        if components["image_label"] is not None:
                            components["image_label"].destroy()
                            components["image_label"] = None
                        
                        components["placeholder"].config(
                            text=f"No {latest_condition} base image found"
                        )
                        components["placeholder"].place(relx=0.5, rely=0.5, anchor="center")
                        
                except Exception as e:
                    self.logger.error(f"Error loading base image for {camera_name}: {e}")
                    
                    # Show error in placeholder
                    if components["image_label"] is not None:
                        components["image_label"].destroy()
                        components["image_label"] = None
                    
                    components["placeholder"].config(
                        text=f"Error loading image:\n{str(e)[:40]}..."
                    )
                    components["placeholder"].place(relx=0.5, rely=0.5, anchor="center")
            
            # Update status based on results
            if found_images:
                self.status_var.set(f"Showing {latest_condition} base images")
                self.last_update_var.set(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
                
                # Schedule next automatic refresh in 5 minutes
                if self.refresh_timer:
                    self.after_cancel(self.refresh_timer)
                self.refresh_timer = self.after(300000, self.load_base_images)
            else:
                self.status_var.set("Waiting for base images to be captured...")
                self.last_update_var.set("No base images found")
                
                # Try again sooner if no images were found
                if self.refresh_timer:
                    self.after_cancel(self.refresh_timer)
                self.refresh_timer = self.after(10000, self.load_base_images)
            
        except Exception as e:
            self.logger.error(f"Error loading base images: {e}")
            self.status_var.set(f"Error: {str(e)[:50]}...")
            
            # Schedule retry
            if self.refresh_timer:
                self.after_cancel(self.refresh_timer)
            self.refresh_timer = self.after(30000, self.load_base_images)
    
    def get_latest_base_image_condition(self):
        """
        Determine which lighting condition has the most recent base images.
        
        Returns:
            str: The lighting condition with the most recent base images
        """
        try:
            latest_time = 0
            latest_condition = "day"  # Default to day
            
            # Check all lighting conditions
            for condition in ["day", "night", "transition"]:
                # Check all cameras for this condition
                for camera_name in CAMERA_MAPPINGS.keys():
                    image_path = get_base_image_path(camera_name, condition)
                    if os.path.exists(image_path):
                        mod_time = os.path.getmtime(image_path)
                        if mod_time > latest_time:
                            latest_time = mod_time
                            latest_condition = condition
            
            self.logger.debug(f"Latest base image condition: {latest_condition}")
            return latest_condition
            
        except Exception as e:
            self.logger.error(f"Error determining latest base image condition: {e}")
            return "day"  # Default to day on error
    
    def refresh_images(self):
        """Manual refresh of base images"""
        if self.detection_active:
            # Cancel any pending refresh
            if self.refresh_timer:
                self.after_cancel(self.refresh_timer)
                self.refresh_timer = None
                
            self.load_base_images()
    
    def destroy(self):
        """Clean up resources when panel is destroyed"""
        # Cancel any pending refresh
        if self.refresh_timer:
            self.after_cancel(self.refresh_timer)
            self.refresh_timer = None
            
        # Clear image references
        self.image_references.clear()
        
        super().destroy()


# For backwards compatibility, keep SimpleImageViewer class
class SimpleImageViewer(ttk.Frame):
    """A minimal image viewer without annotations or extra text"""
    def __init__(self, parent, title=None):
        super().__init__(parent)
        
        # Keep reference to loaded images
        self.image_references = {}
        
        # Track last update time for change detection
        self.last_update_time = 0
        
        # Save title if provided
        self.title = title
        
        # Create the UI
        self.create_interface()
        
    def create_interface(self):
        """Create a simple display with just the image"""
        # Add title if provided
        if self.title:
            self.title_label = ttk.Label(self, text=self.title)
            self.title_label.pack(pady=(0, 5))
        
        # Create image label - no additional text
        self.image_label = ttk.Label(self)
        self.image_label.pack(padx=5, pady=5)
        
    def load_image(self, image_path, max_size=(200, 150)):
        """Load and display an image without annotations"""
        if not os.path.exists(image_path):
            logger = get_logger()
            logger.warning(f"Image not found: {image_path}")
            return False
            
        # Load the image
        try:
            img = Image.open(image_path)
            
            # Update last update time
            import time
            self.last_update_time = time.time()
            
            # Resize if needed
            img.thumbnail(max_size, Image.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(img)
            
            # Update label - just the image, no text
            self.image_label.config(image=photo)
            
            # Keep reference to prevent garbage collection
            self.image_references[image_path] = photo
            
            return True
        except Exception as e:
            logger = get_logger()
            logger.error(f"Error loading image {image_path}: {e}")
            return False
    
    def load_base_image(self, camera_name, lighting_condition, max_size=(200, 150)):
        """
        Load and display a base image for a specific camera and lighting condition
        
        Args:
            camera_name (str): Name of the camera
            lighting_condition (str): Lighting condition ('day', 'night', or 'transition')
            max_size (tuple): Maximum size for display
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get the path for this base image
            image_path = get_base_image_path(camera_name, lighting_condition)
            
            # Load and display the image
            return self.load_image(image_path, max_size)
        except Exception as e:
            logger = get_logger()
            logger.error(f"Error loading base image for {camera_name} ({lighting_condition}): {e}")
            return False
        
    def clear(self):
        """Clear the displayed image"""
        self.image_label.config(image="")
        
        # Clear references to allow garbage collection
        self.image_references.clear()


if __name__ == "__main__":
    # Test the panel independently
    root = tk.Tk()
    root.title("Base Images Panel Test")
    
    # Create logger
    logger = get_logger()
    
    # Create panel
    panel = BaseImagesPanel(root, logger)
    panel.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Add test buttons
    test_frame = ttk.Frame(root)
    test_frame.pack(pady=10)
    
    ttk.Button(
        test_frame,
        text="Simulate Detection Start",
        command=lambda: panel.detection_started()
    ).pack(side=tk.LEFT, padx=5)
    
    ttk.Button(
        test_frame,
        text="Simulate Detection Stop",
        command=lambda: panel.detection_stopped()
    ).pack(side=tk.LEFT, padx=5)
    
    ttk.Button(
        test_frame,
        text="Manual Refresh",
        command=lambda: panel.refresh_images()
    ).pack(side=tk.LEFT, padx=5)
    
    # Start the main loop
    root.geometry("800x600")
    root.mainloop()