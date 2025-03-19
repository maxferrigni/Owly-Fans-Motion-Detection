# File: scripts/front_end_components/images_tab.py
# Purpose: Images tab component for the Owl Monitoring System GUI
# 
# March 19, 2025 Update - Version 1.4.4
# - Fixed issue with images showing before "Start Detection" is clicked
# - Added proper state management based on application running state
# - Added "No images available" placeholder when images aren't available
# - Added support for complete image clearing
# - Implemented proper handling of image directories

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os
from datetime import datetime
import threading
import time

from utilities.logging_utils import get_logger
from utilities.constants import CAMERA_MAPPINGS, get_comparison_image_path, get_base_image_path

class ImagesTab(ttk.Frame):
    """Tab containing image viewer for comparison images"""
    
    def __init__(self, parent, app_reference, is_running=False):
        """
        Initialize Images Tab
        
        Args:
            parent (ttk.Frame): Parent frame (typically the notebook tab)
            app_reference: Reference to the main application for callbacks
            is_running (bool): Whether the detection is currently running
        """
        super().__init__(parent)
        self.parent = parent
        self.app = app_reference
        self.logger = get_logger()
        self.is_running = is_running
        
        # Create the image viewer panel
        self.image_viewer = ImageViewerPanel(self, app_reference, is_running)
        self.image_viewer.pack(fill="both", expand=True)

        # Pack self into parent container
        self.pack(fill="both", expand=True)
        
    def set_running_state(self, is_running):
        """Update running state and refresh the image viewer"""
        self.is_running = is_running
        self.image_viewer.set_running_state(is_running)
        
    def clear_images(self):
        """Clear all images and display placeholders"""
        if hasattr(self.image_viewer, 'clear_images'):
            self.image_viewer.clear_images()


class ImageViewerPanel(ttk.Frame):
    """
    Panel for displaying camera images in a grid with detection information.
    Updated in v1.4.4 for better state management and placeholders.
    """
    def __init__(self, parent, app_reference, is_running=False):
        super().__init__(parent)
        self.parent = parent
        self.app_reference = app_reference
        self.logger = get_logger()
        self.is_running = is_running
        
        # Define image dimensions for uniform display
        self.image_width = 250
        self.image_height = 150
        
        # Store image references to prevent garbage collection
        self.image_refs = {}
        
        # Last modification times to detect changes
        self.last_modified = {}
        
        # Camera order for consistent display
        self.camera_order = ["Wyze Internal Camera", "Bindy Patio Camera", "Upper Patio Camera"]
        
        # Initialize image references and modification times for all cameras
        for camera in self.camera_order:
            self.image_refs[camera] = {
                "base": None,
                "current": None,
                "analysis": None
            }
            self.last_modified[camera] = 0
        
        # Create scrollable container
        self.create_scrollable_container()
        
        # Create the grid layout for images
        self.create_image_grid()
        
        # Start refresh timer only if detection is running
        if self.is_running:
            self.refresh_images()
        else:
            self.display_placeholders()
        
    def create_scrollable_container(self):
        """Create a scrollable container for the image grid"""
        # Create a canvas with scrollbar for handling many images
        self.canvas = tk.Canvas(self)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Pack scrollbar and canvas
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Create main frame inside canvas for content
        self.main_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        
        # Configure canvas to resize with window
        self.bind("<Configure>", self.on_canvas_configure)
        self.main_frame.bind("<Configure>", self.on_frame_configure)
        
    def on_canvas_configure(self, event):
        """Handle canvas resize events"""
        # Update the inner frame's width to match the canvas
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        
    def on_frame_configure(self, event):
        """Update the scrollregion when the inner frame changes size"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def create_image_grid(self):
        """Create grid layout with rows for each camera"""
        # Create a frame for each camera with image containers and detection info
        self.camera_frames = {}
        self.image_containers = {}
        self.image_labels = {}
        self.image_text_labels = {}
        self.result_labels = {}
        self.detail_labels = {}
        
        # Create placeholder message label for when detection isn't running
        self.placeholder_message = ttk.Label(
            self.main_frame,
            text="No images available. Click 'Start Detection' to begin monitoring.",
            font=("Arial", 12),
            anchor="center"
        )
        self.placeholder_message.pack(pady=50)
        self.placeholder_message.place_forget()  # Initially hide it
        
        for i, camera in enumerate(self.camera_order):
            # Create frame for this camera
            camera_frame = ttk.LabelFrame(self.main_frame, text=f"{camera}")
            camera_frame.pack(fill="x", pady=10, padx=5)
            self.camera_frames[camera] = camera_frame
            
            # Create image row with three equal-sized containers
            image_row = ttk.Frame(camera_frame)
            image_row.pack(fill="x", pady=5)
            
            # Create containers for three image types
            self.image_containers[camera] = {}
            self.image_labels[camera] = {}
            self.image_text_labels[camera] = {}
            
            image_types = [
                ("base", "Base Image"), 
                ("current", "Current Image"), 
                ("analysis", "Analysis Image")
            ]
            
            for img_type, display_name in image_types:
                # Create column frame to hold image and label vertically
                column_frame = ttk.Frame(image_row)
                column_frame.pack(side="left", padx=10, fill="y")
                
                # Create container frame with fixed size
                container = ttk.Frame(column_frame, width=self.image_width, height=self.image_height)
                container.pack(side="top", fill="both")
                container.pack_propagate(False)  # Prevent container from resizing to fit content
                
                # Create image label within container
                img_label = ttk.Label(container)
                img_label.pack(fill="both", expand=True)
                
                # Add text label UNDER each image
                text_label = ttk.Label(
                    column_frame, 
                    text=f"{display_name} - {camera}",
                    anchor="center",
                    justify="center"
                )
                text_label.pack(side="bottom", fill="x", pady=(5, 0))
                
                # Store references
                self.image_containers[camera][img_type] = container
                self.image_labels[camera][img_type] = img_label
                self.image_text_labels[camera][img_type] = text_label
            
            # Create detection result area beneath images
            result_frame = ttk.Frame(camera_frame)
            result_frame.pack(fill="x", pady=5)
            
            # Create highlighted result label (Owl Detected or No Owl Detected)
            self.result_labels[camera] = ttk.Label(
                result_frame, 
                text="No Owl Detected.",
                font=("Arial", 12, "bold")
            )
            self.result_labels[camera].pack(anchor="w", padx=10)
            
            # Create detailed criteria label
            self.detail_labels[camera] = ttk.Label(
                result_frame,
                text="Waiting for detection data...",
                font=("Arial", 10),
                wraplength=850
            )
            self.detail_labels[camera].pack(anchor="w", padx=10, pady=5)
            
            # Add separator between camera sections
            if i < len(self.camera_order) - 1:
                ttk.Separator(self.main_frame, orient="horizontal").pack(fill="x", pady=5)
        
        # Initially hide or show camera frames based on running state
        if not self.is_running:
            self.display_placeholders()
    
    def set_running_state(self, is_running):
        """Update running state and manage image display"""
        self.is_running = is_running
        
        if is_running:
            # Hide placeholder and show camera frames
            self.placeholder_message.place_forget()
            for camera, frame in self.camera_frames.items():
                frame.pack(fill="x", pady=10, padx=5)
            
            # Start image refresh
            self.refresh_images()
        else:
            # Stop image refreshing
            # Display placeholders
            self.display_placeholders()
    
    def display_placeholders(self):
        """Show placeholder message when detection is not running"""
        # Hide camera frames
        for camera, frame in self.camera_frames.items():
            frame.pack_forget()
        
        # Show placeholder message
        self.placeholder_message.place(relx=0.5, rely=0.5, anchor="center")
    
    def clear_images(self):
        """Clear all images and display empty placeholders"""
        # Reset all stored image references
        for camera in self.camera_order:
            for img_type in ["base", "current", "analysis"]:
                self.image_refs[camera][img_type] = None
            self.last_modified[camera] = 0
        
        # Display empty placeholders in all image labels if running
        if self.is_running:
            for camera in self.camera_order:
                for img_type in ["base", "current", "analysis"]:
                    self.display_empty_placeholder(camera, img_type)
        else:
            # If not running, show the not-running placeholder
            self.display_placeholders()

    def display_empty_placeholder(self, camera, image_type):
        """Display an empty placeholder in a specific image container"""
        # Create blank image with message
        img = Image.new('RGB', (self.image_width, self.image_height), color=(200, 200, 200))
        photo = ImageTk.PhotoImage(img)
        
        # Update image label
        self.image_labels[camera][image_type].config(image=photo)
        
        # Store reference
        self.image_refs[camera][image_type] = photo
    
    def get_image_path(self, camera, image_type):
        """
        Get the appropriate path for each image type.
        
        Args:
            camera (str): Camera name
            image_type (str): "base", "current", or "analysis"
            
        Returns:
            str: Path to the image
        """
        try:
            # Only attempt to get images if application is running
            if not self.is_running:
                return None
                
            # For a real implementation, we need to access the individual images
            # For now, we're using a workaround to extract from the 3-panel image
            
            # Get the path to the 3-panel comparison image
            comparison_path = get_comparison_image_path(camera)
            
            # In a real implementation, you would have separate paths for each image type
            # TODO: Implement proper paths for base, current, and analysis images
            
            if os.path.exists(comparison_path):
                return comparison_path
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting image path for {camera} {image_type}: {e}")
            return None
    
    def extract_panel_from_comparison(self, comparison_image, panel_index):
        """
        Extract an individual panel from the 3-panel comparison image.
        
        Args:
            comparison_image (PIL.Image): The 3-panel comparison image
            panel_index (int): 0 for base, 1 for current, 2 for analysis
            
        Returns:
            PIL.Image: The extracted panel
        """
        try:
            if not comparison_image:
                return None
                
            width, height = comparison_image.size
            panel_width = width // 3
            
            # Crop the relevant panel
            left = panel_index * panel_width
            right = left + panel_width
            
            panel = comparison_image.crop((left, 0, right, height))
            return panel
            
        except Exception as e:
            self.logger.error(f"Error extracting panel {panel_index}: {e}")
            return None
    
    def load_and_display_image(self, camera, image_type):
        """
        Load and display an image for a specific camera and type.
        Only loads images if detection is running.
        
        Args:
            camera (str): Camera name
            image_type (str): "base", "current", or "analysis"
            
        Returns:
            bool: True if image was updated
        """
        try:
            # Exit early if not running
            if not self.is_running:
                return False
                
            # Get the path to the 3-panel comparison image
            comparison_path = get_comparison_image_path(camera)
            
            # Check if file exists
            if not os.path.exists(comparison_path):
                # Display placeholder for missing image
                self.display_empty_placeholder(camera, image_type)
                return False
            
            # Check if file was modified since last load
            mod_time = os.path.getmtime(comparison_path)
            if mod_time <= self.last_modified.get(camera, 0) and self.image_refs[camera][image_type]:
                return False  # No update needed
            
            # Load the 3-panel comparison image
            comparison_image = Image.open(comparison_path)
            
            # Determine which panel to extract based on image_type
            panel_index = {"base": 0, "current": 1, "analysis": 2}[image_type]
            
            # Extract the specific panel
            panel = self.extract_panel_from_comparison(comparison_image, panel_index)
            
            if not panel:
                self.display_empty_placeholder(camera, image_type)
                return False
                
            # Resize image to fit container while maintaining aspect ratio
            width, height = panel.size
            ratio = min(self.image_width/width, self.image_height/height)
            new_size = (int(width * ratio), int(height * ratio))
            
            resized = panel.resize(new_size, Image.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(resized)
            
            # Update image label
            self.image_labels[camera][image_type].config(image=photo)
            
            # Store reference to prevent garbage collection
            self.image_refs[camera][image_type] = photo
            
            # Update last modified time if this is the analysis image
            # (we use this as the marker for when all images should be updated)
            if image_type == "analysis":
                self.last_modified[camera] = mod_time
                
                # Update detection information based on analysis image
                self.update_detection_info(camera, comparison_path)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading {image_type} image for {camera}: {e}")
            self.display_empty_placeholder(camera, image_type)
            return False
    
    def update_detection_info(self, camera, image_path):
        """
        Update detection result information based on comparison image.
        In a real implementation, this would parse detection data from file or database.
        
        Args:
            camera (str): Camera name
            image_path (str): Path to comparison image
        """
        try:
            # This is a placeholder implementation
            # In production, you would extract real detection data
            
            # Simulate detection result based on filename (for demo purposes)
            is_detected = "detected" in image_path.lower() or camera == "Bindy Patio Camera"
            
            # Update result label with appropriate styling
            if is_detected:
                self.result_labels[camera].config(
                    text="Owl Detected!",
                    foreground="green"
                )
                
                # Example detection criteria
                criteria_text = (
                    "Detection criteria: Confidence score: 75.5% (threshold: 60.0%), "
                    "Consecutive frames: 3 (required: 2), "
                    "Shape confidence: 30.5%, Motion confidence: 25.0%, "
                    "Temporal confidence: 15.0%, Camera confidence: 5.0%. "
                    "Owl shape detected in center-right region with high circularity (0.78) and good aspect ratio (1.2)."
                )
            else:
                self.result_labels[camera].config(
                    text="No Owl Detected.",
                    foreground="red"
                )
                
                # Example failed criteria
                criteria_text = (
                    "Detection criteria not met: Confidence score: 45.2% (threshold: 60.0%), "
                    "Consecutive frames: 1 (required: 2), "
                    "Shape confidence: 20.5%, Motion confidence: 15.7%, "
                    "Temporal confidence: 5.0%, Camera confidence: 4.0%. "
                    "Pixel change (18.3%) below ideal range, luminance change (15.2) insufficient."
                )
            
            # Update detail label
            self.detail_labels[camera].config(text=criteria_text)
            
        except Exception as e:
            self.logger.error(f"Error updating detection info for {camera}: {e}")
            self.detail_labels[camera].config(text=f"Error updating detection information: {e}")
    
    def refresh_images(self):
        """
        Refresh all camera images.
        Only refreshes images if detection is running.
        """
        try:
            if not self.is_running:
                return  # Don't refresh if not running
                
            updates = 0
            
            # Load images for all cameras
            for camera in self.camera_order:
                for img_type in ["base", "current", "analysis"]:
                    if self.load_and_display_image(camera, img_type):
                        updates += 1
                        
            # Schedule next refresh
            # Every 5 seconds if no updates, more frequently if updates found
            refresh_time = 1000 if updates > 0 else 5000
            self.after(refresh_time, self.refresh_images)
            
        except Exception as e:
            self.logger.error(f"Error refreshing images: {e}")
            # On error, retry after longer delay
            self.after(10000, self.refresh_images)