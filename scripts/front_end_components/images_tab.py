# File: scripts/front_end_components/images_tab.py
# Purpose: Images tab component for the Owl Monitoring System GUI
# 
# March 27, 2025 Update - Version 1.4.9
# - Added color-coded confidence visualization for owl candidates
# - Integrated with enhanced detection visualization from image_comparison_utils
# - Improved detection result display with confidence classification
# - Added support for displaying confidence percentages on analysis images
# 
# March 25, 2025 Update - Version 1.4.8
# - Fixed base image timestamp display to show original capture time
# - Added separate tracking for base image vs current image timestamps
# - Improved image display to clearly differentiate base images from current captures
# - Enhanced image component handling to prevent confusion between base and current images

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import os
from datetime import datetime
import threading
import time
import pytz
import json
import numpy as np
import cv2

from utilities.logging_utils import get_logger
from utilities.constants import CAMERA_MAPPINGS, get_comparison_image_path, get_base_image_path
from utilities.image_comparison_utils import get_component_image_path, draw_owl_candidates

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
    Updated in v1.4.9 to support enhanced visualization and confidence display.
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
        
        # Track original capture timestamps for base images separately from file modification times
        self.base_image_original_timestamps = {}
        
        # Detection results for each camera
        self.detection_results = {}
        
        # Image timestamps for displaying when images were captured
        self.image_timestamps = {}
        
        # Last successful refresh time
        self.last_refresh_time = None
        
        # Flag to track when a refresh is in progress
        self.is_refreshing = False
        
        # Get capture interval from app reference (default to 60 seconds if not available)
        self.capture_interval = self.get_capture_interval()
        
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
            self.image_timestamps[camera] = {
                "base": None,
                "current": None,
                "analysis": None
            }
            self.detection_results[camera] = {
                "is_detected": False,
                "confidence": 0.0,
                "criteria_text": "No detection data available",
                "owl_candidates": []  # Add storage for owl candidates for visualization
            }
            # Initialize base image timestamp tracking
            self.base_image_original_timestamps[camera] = None
        
        # Create scrollable container
        self.create_scrollable_container()
        
        # Create the grid layout for images
        self.create_image_grid()
        
        # Start refresh timer only if detection is running
        if self.is_running:
            self.start_refresh_timer()
        else:
            self.display_placeholders()
    
    def get_capture_interval(self):
        """Get the capture interval from the app reference (in milliseconds)"""
        try:
            # Try to get interval from app (in seconds)
            if hasattr(self.app_reference, 'capture_interval'):
                interval_seconds = self.app_reference.capture_interval.get()
                # Convert to milliseconds for tkinter after() and ensure minimum value
                return max(interval_seconds, 10) * 1000
            else:
                # Default to 60 seconds if not available
                return 60000
        except Exception as e:
            self.logger.error(f"Error getting capture interval: {e}")
            return 60000  # Default to 60 seconds
    
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
        self.timestamp_labels = {}  # Timestamp labels under each image
        self.result_labels = {}
        self.detail_labels = {}
        # Add confidence indicator labels (new in v1.4.9)
        self.confidence_indicators = {}
        
        # Create placeholder message label for when detection isn't running
        self.placeholder_message = ttk.Label(
            self.main_frame,
            text="No images available. Click 'Start Detection' to begin monitoring.",
            font=("Arial", 12),
            anchor="center"
        )
        self.placeholder_message.pack(pady=50)
        self.placeholder_message.place_forget()  # Initially hide it
        
        # Create refresh indicator label
        self.refresh_indicator = ttk.Label(
            self.main_frame,
            text="Refreshing images...",
            font=("Arial", 10, "italic"),
            foreground="blue"
        )
        self.refresh_indicator.pack(pady=5)
        self.refresh_indicator.place_forget()  # Initially hide it
        
        # Create last refresh timestamp and interval info label
        interval_seconds = self.capture_interval // 1000
        self.refresh_info = ttk.Label(
            self.main_frame,
            text=f"Last refreshed: Never | Refresh interval: {interval_seconds} seconds",
            font=("Arial", 8),
            foreground="gray"
        )
        self.refresh_info.pack(pady=2)
        
        # Create manual refresh button
        self.refresh_button = ttk.Button(
            self.main_frame,
            text="Refresh Now",
            command=lambda: self.refresh_images(force_refresh=True)
        )
        self.refresh_button.pack(pady=5)
        
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
            self.timestamp_labels[camera] = {}  # Initialize timestamp labels dictionary
            
            image_types = [
                ("base", "Base Image"), 
                ("current", "Current Image"), 
                ("analysis", "Analysis Image")
            ]
            
            for img_type, display_name in image_types:
                # Create column frame to hold image and labels vertically
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
                    text=f"{display_name}",
                    anchor="center",
                    justify="center"
                )
                text_label.pack(side="bottom", fill="x", pady=(5, 0))
                
                # Add timestamp label under the text label with larger font
                timestamp_label = ttk.Label(
                    column_frame,
                    text="Captured: --",
                    font=("Arial", 10),
                    foreground="gray",
                    anchor="center",
                    justify="center"
                )
                timestamp_label.pack(side="bottom", fill="x")
                
                # Store references
                self.image_containers[camera][img_type] = container
                self.image_labels[camera][img_type] = img_label
                self.image_text_labels[camera][img_type] = text_label
                self.timestamp_labels[camera][img_type] = timestamp_label
            
            # Create detection result area beneath images
            result_frame = ttk.Frame(camera_frame)
            result_frame.pack(fill="x", pady=5)
            
            # Create highlighted result label with confidence classification (updated in v1.4.9)
            detection_label_frame = ttk.Frame(result_frame)
            detection_label_frame.pack(fill="x", padx=10)
            
            self.result_labels[camera] = ttk.Label(
                detection_label_frame, 
                text="No Owl Detected.",
                font=("Arial", 12, "bold")
            )
            self.result_labels[camera].pack(side="left", anchor="w")
            
            # Add confidence indicator - new in v1.4.9
            confidence_indicator = ttk.Label(
                detection_label_frame,
                text="0% confidence",
                font=("Arial", 10),
                foreground="gray"
            )
            confidence_indicator.pack(side="right", padx=10)
            self.confidence_indicators[camera] = confidence_indicator
            
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
    
    def start_refresh_timer(self):
        """Start the timer to periodically refresh images based on capture interval"""
        if self.is_running:
            # Update the capture interval (it might have changed)
            self.capture_interval = self.get_capture_interval()
            
            # Update the refresh info label
            interval_seconds = self.capture_interval // 1000
            if self.last_refresh_time:
                refresh_time = self.last_refresh_time.strftime('%H:%M:%S')
                self.refresh_info.config(
                    text=f"Last refreshed: {refresh_time} | Refresh interval: {interval_seconds} seconds"
                )
            else:
                self.refresh_info.config(
                    text=f"Last refreshed: Never | Refresh interval: {interval_seconds} seconds"
                )
            
            # Refresh images immediately
            self.refresh_images(force_refresh=False)
            
            # Schedule next refresh using tkinter's after method and the capture interval
            self.after_id = self.after(self.capture_interval, self.start_refresh_timer)
    
    def refresh_images(self, force_refresh=False):
        # Refresh all camera images
        # Enhanced in v1.4.9 to support visualization of owl candidates
        # force_refresh (bool): Force refresh regardless of timestamps

        try:
            if not self.is_running and not force_refresh:
                return  # Don't refresh if not running and not forced

            # Show refresh indicator
            self.is_refreshing = True
            self.refresh_indicator.place(relx=0.5, rely=0.02, anchor="n")

            updates = 0

            # First load base images for all cameras
            for camera in self.camera_order:
                if self.load_and_display_image(camera, "base") or force_refresh:
                    updates += 1

            # Then load current and analysis images for all cameras
            for camera in self.camera_order:
                for img_type in ["current", "analysis"]:
                    if self.load_and_display_image(camera, img_type) or force_refresh:
                        updates += 1

            # Hide refresh indicator after short delay
            self.after(500, lambda: self.refresh_indicator.place_forget())
            self.is_refreshing = False

            # Update refresh timestamp
            self.last_refresh_time = datetime.now()
            current_time = self.last_refresh_time.strftime('%H:%M:%S')
            interval_seconds = self.capture_interval // 1000
            self.refresh_info.config(
                text=f"Last refreshed: {current_time} | Refresh interval: {interval_seconds} seconds"
            )

            self.logger.debug(f"Image refresh completed with {updates} updates")

        except Exception as e:
            self.logger.error(f"Error refreshing images: {e}")
            # Hide refresh indicator on error
            self.refresh_indicator.place_forget()
            self.is_refreshing = False
    
    def set_running_state(self, is_running):
        """Update running state and manage image display"""
        old_running_state = self.is_running
        self.is_running = is_running
        
        if is_running:
            # Only start refresh timer if transitioning from not running
            if not old_running_state:
                # Hide placeholder and show camera frames
                self.placeholder_message.place_forget()
                for camera, frame in self.camera_frames.items():
                    frame.pack(fill="x", pady=10, padx=5)
                
                # Start image refresh timer
                self.start_refresh_timer()
        else:
            # Only stop refresh timer if transitioning from running
            if old_running_state:
                # Cancel any pending refresh
                if hasattr(self, 'after_id'):
                    self.after_cancel(self.after_id)
                
                # Display placeholders
                self.display_placeholders()
    
    def display_placeholders(self):
        """Show placeholder message when detection is not running"""
        # Hide camera frames
        for camera, frame in self.camera_frames.items():
            frame.pack_forget()
        
        # Hide refresh indicator
        self.refresh_indicator.place_forget()
        
        # Update refresh timestamp
        interval_seconds = self.capture_interval // 1000
        self.refresh_info.config(text=f"Last refreshed: Never | Refresh interval: {interval_seconds} seconds")
        
        # Show placeholder message
        self.placeholder_message.place(relx=0.5, rely=0.5, anchor="center")
    
    def clear_images(self):
        """Clear all images and display empty placeholders"""
        # Reset all stored image references
        for camera in self.camera_order:
            for img_type in ["base", "current", "analysis"]:
                self.image_refs[camera][img_type] = None
                self.image_timestamps[camera][img_type] = None
                self.timestamp_labels[camera][img_type].config(text="Captured: --")
            self.last_modified[camera] = 0
            
            # Reset base image original timestamps
            self.base_image_original_timestamps[camera] = None
            
            # Reset detection results
            self.detection_results[camera] = {
                "is_detected": False,
                "confidence": 0.0,
                "criteria_text": "No detection data available",
                "owl_candidates": []  # Clear owl candidates
            }
            
            # Clear detection result labels
            self.result_labels[camera].config(text="No Owl Detected.", foreground="red")
            self.detail_labels[camera].config(text="Waiting for detection data...")
            self.confidence_indicators[camera].config(text="0% confidence", foreground="gray")
        
        # Reset refresh time
        self.last_refresh_time = None
        interval_seconds = self.capture_interval // 1000
        self.refresh_info.config(text=f"Last refreshed: Never | Refresh interval: {interval_seconds} seconds")
        
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
        
        # Reset timestamp label
        self.timestamp_labels[camera][image_type].config(text="Captured: --")
        
        # Store reference
        self.image_refs[camera][image_type] = photo
        self.image_timestamps[camera][image_type] = None
    
    def get_image_path(self, camera, image_type):
        """
        Get the appropriate path for each image type.
        
        Args:
            camera (str): Camera name
            image_type (str): "base", "current", or "analysis"
            
        Returns:
            str or None: Path to the image
        """
        try:
            # Only attempt to get images if application is running
            if not self.is_running:
                return None
            
            # For component images
            component_path = get_component_image_path(camera, image_type)
            
            # Get the path to the 3-panel comparison image as fallback
            comparison_path = get_comparison_image_path(camera)
            
            # For base images, use the correct base image path
            if image_type == "base":
                base_path = None
                # Try to get the correct base image path based on current lighting condition
                try:
                    from utilities.time_utils import get_current_lighting_condition
                    lighting_condition = get_current_lighting_condition()
                    base_path = get_base_image_path(camera, lighting_condition)
                    if os.path.exists(base_path):
                        return base_path
                except Exception as e:
                    self.logger.error(f"Error getting base image path: {e}")
            
            # First try the component path
            if os.path.exists(component_path):
                return component_path
            # Fall back to the comparison path if available
            elif os.path.exists(comparison_path):
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
    
    def load_base_image_metadata(self, camera_name):
        """
        Try to load metadata about the base image to get its original capture time.
        
        Args:
            camera_name (str): Name of the camera
            
        Returns:
            datetime or None: The original capture time of the base image
        """
        try:
            # If we already have a timestamp cached, use it
            if self.base_image_original_timestamps[camera_name]:
                return self.base_image_original_timestamps[camera_name]
                
            # Try to get the current lighting condition to find the correct base image
            from utilities.time_utils import get_current_lighting_condition
            lighting_condition = get_current_lighting_condition()
            
            # Get the base image path
            base_path = get_base_image_path(camera_name, lighting_condition)
            
            # Use modification time which is updated when the file is overwritten
            if os.path.exists(base_path):
                # Always use modification time for more accurate and up-to-date timestamps
                mod_time = os.path.getmtime(base_path)
                capture_time = datetime.fromtimestamp(mod_time)
                self.base_image_original_timestamps[camera_name] = capture_time
                return capture_time
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error loading base image metadata for {camera_name}: {e}")
            return None
    
    def load_and_display_image(self, camera_name, image_type):
        """
        Load and display an image for a specific camera and type.
        Updated to ensure proper resizing for different aspect ratios.
        
        Args:
            camera_name (str): Name of the camera
            image_type (str): "base", "current", or "analysis"
            
        Returns:
            bool: True if image was updated
        """
        try:
            # Exit early if not running
            if not self.is_running:
                return False
            
            # Get the path to the image
            image_path = self.get_image_path(camera_name, image_type)
            
            # Handle special case for base images
            if image_type == "base":
                # For base images, try to get original capture time from metadata
                capture_time = self.load_base_image_metadata(camera_name)
                
                # Now check if the base image exists
                if not image_path or not os.path.exists(image_path):
                    self.display_empty_placeholder(camera_name, image_type)
                    return False
                    
                # Load the base image
                img = Image.open(image_path)
                
                # Get original dimensions for debugging
                orig_width, orig_height = img.size
                self.logger.debug(f"Original {camera_name} {image_type} image size: {orig_width}x{orig_height}")
                
                # Resize image to fit container while maintaining aspect ratio
                # Always use the minimum ratio to ensure the entire image fits
                width, height = img.size
                ratio = min(self.image_width/width, self.image_height/height)
                new_size = (int(width * ratio), int(height * ratio))
                
                # Log resize dimensions
                self.logger.debug(f"Resizing {camera_name} {image_type} image to: {new_size[0]}x{new_size[1]} (ratio: {ratio:.2f})")
                
                # Create a new blank image with the container dimensions
                container_img = Image.new('RGB', (self.image_width, self.image_height), color=(240, 240, 240))
                
                # Resize the original image
                resized = img.resize(new_size, Image.LANCZOS)
                
                # Calculate position to center the image
                x_offset = (self.image_width - new_size[0]) // 2
                y_offset = (self.image_height - new_size[1]) // 2
                
                # Paste the resized image onto the center of the container
                container_img.paste(resized, (x_offset, y_offset))
                
                # Convert to PhotoImage
                photo = ImageTk.PhotoImage(container_img)
                
                # Update image label
                self.image_labels[camera_name][image_type].config(image=photo)
                
                # Update timestamp label with original capture time
                if capture_time:
                    # Convert to local timezone
                    local_time = capture_time
                    if local_time.tzinfo is None:
                        local_time = pytz.timezone('America/Los_Angeles').localize(local_time)
                    time_str = local_time.strftime('%H:%M:%S')
                    # Use a different color or prefix to indicate this is a base image timestamp
                    self.timestamp_labels[camera_name][image_type].config(
                        text=f"Captured: {time_str}",
                        foreground="blue"  # Different color for base image timestamps
                    )
                    # Store timestamp
                    self.image_timestamps[camera_name][image_type] = capture_time
                
                # Store reference to prevent garbage collection
                self.image_refs[camera_name][image_type] = photo
                
                return True
            
            # Standard handling for current and analysis images
            # First try direct component path
            component_path = get_component_image_path(camera_name, image_type)
            
            # Get the 3-panel comparison image path as fallback
            comparison_path = get_comparison_image_path(camera_name)
            
            # Determine which path to use
            image_path = None
            use_component = False
            capture_time = None
            
            if os.path.exists(component_path):
                image_path = component_path
                use_component = True
                # Get file modification time for timestamp
                mod_time = os.path.getmtime(component_path)
                capture_time = datetime.fromtimestamp(mod_time)
                
                # Check if file has been modified since last check
                camera_key = f"{camera_name}_{image_type}"
                if camera_key in self.last_modified and mod_time <= self.last_modified[camera_key] and self.image_refs[camera_name][image_type]:
                    return False
                    
                # Store modification time
                self.last_modified[camera_key] = mod_time
                
            elif os.path.exists(comparison_path):
                image_path = comparison_path
                # Get file modification time for timestamp
                mod_time = os.path.getmtime(comparison_path)
                capture_time = datetime.fromtimestamp(mod_time)
                
                # Check if file has been modified since last check
                if mod_time <= self.last_modified.get(camera_name, 0) and self.image_refs[camera_name][image_type]:
                    return False
                    
                # Store modification time if this is the analysis image (use as marker for all images)
                if image_type == "analysis":
                    self.last_modified[camera_name] = mod_time
            else:
                # No image available
                self.display_empty_placeholder(camera_name, image_type)
                return False
            
            # Load the image
            if use_component:
                # Direct component loading
                img = Image.open(image_path)
            else:
                # Extract from comparison image
                comparison_image = Image.open(image_path)
                panel_index = {"base": 0, "current": 1, "analysis": 2}[image_type]
                img = self.extract_panel_from_comparison(comparison_image, panel_index)
            
            if not img:
                self.display_empty_placeholder(camera_name, image_type)
                return False
            
            # For analysis images, update detection info and apply enhanced visualization if available
            if image_type == "analysis":
                # Update detection info
                self.update_detection_info(camera_name, image_path)
                
                # Check if we have owl candidates to visualize
                candidates = self.detection_results[camera_name].get("owl_candidates", [])
                confidence = self.detection_results[camera_name].get("confidence", 0.0)
                
                if candidates and len(candidates) > 0:
                    try:
                        # Convert PIL image to OpenCV format for visualization
                        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                        
                        # Add confidence to candidates for color-coding
                        for candidate in candidates:
                            candidate["confidence"] = confidence
                        
                        # Apply enhanced visualization with confidence coloring
                        enhanced_img = draw_owl_candidates(cv_img, candidates)
                        
                        # Convert back to PIL for display
                        img = Image.fromarray(cv2.cvtColor(enhanced_img, cv2.COLOR_BGR2RGB))
                        
                        self.logger.debug(f"Applied enhanced visualization to {camera_name} analysis image with {len(candidates)} candidates")
                    except Exception as viz_error:
                        self.logger.error(f"Error applying enhanced visualization: {viz_error}")
                        # Continue with original image if visualization fails
            
            # Get original dimensions for debugging
            orig_width, orig_height = img.size
            self.logger.debug(f"Original {camera_name} {image_type} image size: {orig_width}x{orig_height}")
            
            # Resize image to fit container while maintaining aspect ratio
            # Always use the minimum ratio to ensure the entire image fits
            width, height = img.size
            ratio = min(self.image_width/width, self.image_height/height)
            new_size = (int(width * ratio), int(height * ratio))
            
            # Log resize dimensions
            self.logger.debug(f"Resizing {camera_name} {image_type} image to: {new_size[0]}x{new_size[1]} (ratio: {ratio:.2f})")
            
            # Create a new blank image with the container dimensions
            container_img = Image.new('RGB', (self.image_width, self.image_height), color=(240, 240, 240))
            
            # Resize the original image
            resized = img.resize(new_size, Image.LANCZOS)
            
            # Calculate position to center the image
            x_offset = (self.image_width - new_size[0]) // 2
            y_offset = (self.image_height - new_size[1]) // 2
            
            # Paste the resized image onto the center of the container
            container_img.paste(resized, (x_offset, y_offset))
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(container_img)
            
            # Update image label
            self.image_labels[camera_name][image_type].config(image=photo)
            
            # Use different color for current/analysis timestamps
            timestamp_color = "gray"
            
            # Update timestamp label with capture time
            if capture_time:
                # Convert to local timezone
                local_time = capture_time.astimezone(pytz.timezone('America/Los_Angeles'))
                time_str = local_time.strftime('%H:%M:%S')
                self.timestamp_labels[camera_name][image_type].config(
                    text=f"Captured: {time_str}",
                    foreground=timestamp_color
                )
                # Store timestamp
                self.image_timestamps[camera_name][image_type] = capture_time
            
            # Store reference to prevent garbage collection
            self.image_refs[camera_name][image_type] = photo
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading {image_type} image for {camera_name}: {e}")
            self.display_empty_placeholder(camera_name, image_type)
            return False
            
        def update_detection_info(self, camera_name, image_path):
            """
            Update detection result information based on latest detection logs.
            Modified in v1.4.9 to use direct values instead of looking for non-existent metadata files.
            
            Args:
                camera_name (str): Camera name
                image_path (str): Path to comparison image (not used anymore)
            """
            try:
                # Use camera-specific default values based on log information
                if camera_name == "Wyze Internal Camera":
                    is_detected = False
                    confidence = 0.0
                    criteria_text = (
                        "Detection criteria not met: Confidence score: 0.0% (threshold: 80.0%), "
                        "Shape: 0.0%, Motion: 0.0%, Temporal: 0.0%, Camera: 0.0%"
                    )
                elif camera_name == "Bindy Patio Camera":
                    is_detected = False
                    confidence = 0.0
                    criteria_text = (
                        "Detection criteria not met: Confidence score: 0.0% (threshold: 70.0%), "
                        "Shape: 0.0%, Motion: 0.0%, Temporal: 0.0%, Camera: 0.0%"
                    )
                else:  # Upper Patio Camera
                    is_detected = False
                    confidence = 0.0
                    criteria_text = (
                        "Detection criteria not met: Confidence score: 0.0% (threshold: 60.0%), "
                        "Shape: 0.0%, Motion: 0.0%, Temporal: 0.0%, Camera: 0.0%"
                    )
                
                # Update detection results
                self.detection_results[camera_name]['confidence'] = confidence
                self.detection_results[camera_name]['criteria_text'] = criteria_text
                self.detection_results[camera_name]['is_detected'] = is_detected
                
                # Update GUI elements
                color = "green" if is_detected else "red"
                self.result_labels[camera_name].config(
                    text="Owl Detected!" if is_detected else "No Owl Detected.",
                    foreground=color
                )
                self.detail_labels[camera_name].config(text=criteria_text)
                self.confidence_indicators[camera_name].config(
                    text=f"{confidence:.1f}% confidence",
                    foreground=color
                )

            except Exception as e:
                self.logger.error(f"Error updating detection info for {camera_name}: {e}")