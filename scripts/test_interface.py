# File: test_interface.py
# Purpose: Handle test mode functionality for the Owl Monitoring System

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import os
import json
import numpy as np

from utilities.logging_utils import get_logger
from utilities.constants import CAMERA_MAPPINGS, CONFIGS_DIR
from utilities.owl_detection_utils import detect_owl_in_box
from utilities.image_comparison_utils import create_comparison_image

class TestInterface:
    def __init__(self, parent_frame, logger, alert_manager):
        self.parent_frame = parent_frame
        self.logger = logger or get_logger()
        self.alert_manager = alert_manager
        
        # Track loaded images
        self.base_images = {}  # {camera_type: Image}
        self.test_images = {}  # {camera_type: Image}
        
        # Create the test interface directly (no test mode toggle needed)
        self.create_interface()
        
    def create_interface(self):
        """Create test mode interface elements"""
        # Create main sections
        self.create_image_testing_interface()
        self.create_alert_testing_interface()
        self.create_results_display()
        
    def create_image_testing_interface(self):
        """Create interface for image-based testing"""
        self.image_frame = ttk.LabelFrame(self.parent_frame, text="Image Testing")
        self.image_frame.pack(pady=5, fill="both", expand=True)
        
        # Camera selection
        camera_frame = ttk.Frame(self.image_frame)
        camera_frame.pack(pady=5, fill="x")
        
        ttk.Label(camera_frame, text="Select Camera:").pack(side=tk.LEFT, padx=5)
        self.camera_var = tk.StringVar()
        self.camera_combo = ttk.Combobox(
            camera_frame, 
            textvariable=self.camera_var,
            values=list(CAMERA_MAPPINGS.keys()),
            state="readonly",
            width=30
        )
        self.camera_combo.pack(side=tk.LEFT, padx=5)
        self.camera_combo.bind('<<ComboboxSelected>>', self.on_camera_selected)
        
        # Image loading buttons
        button_frame = ttk.Frame(self.image_frame)
        button_frame.pack(pady=5, fill="x")
        
        ttk.Button(
            button_frame,
            text="Load Base Image",
            command=lambda: self.load_image("base")
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Load Test Image",
            command=lambda: self.load_image("test")
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Run Detection Test",
            command=self.run_detection_test
        ).pack(side=tk.LEFT, padx=5)
        
        # Image info display
        self.image_info = ttk.Label(self.image_frame, text="No images loaded")
        self.image_info.pack(pady=5)

    def create_alert_testing_interface(self):
        """Create interface for direct alert testing"""
        self.alert_frame = ttk.LabelFrame(self.parent_frame, text="Alert Testing")
        self.alert_frame.pack(pady=5, fill="x")
        
        button_frame = ttk.Frame(self.alert_frame)
        button_frame.pack(pady=5, fill="x")
        
        self.alert_buttons = {}
        for alert_type in ["Owl In Box", "Owl On Box", "Owl In Area"]:
            self.alert_buttons[alert_type] = ttk.Button(
                button_frame,
                text=f"Test {alert_type}",
                command=lambda t=alert_type: self.trigger_test_alert(t)
            )
            self.alert_buttons[alert_type].pack(side=tk.LEFT, padx=5)

    def create_results_display(self):
        """Create results display area"""
        self.results_frame = ttk.LabelFrame(self.parent_frame, text="Test Results")
        self.results_frame.pack(pady=5, fill="both", expand=True)
        
        self.results_text = tk.Text(
            self.results_frame,
            height=10,
            width=60,
            wrap=tk.WORD,
            font=('Consolas', 9)
        )
        self.results_text.pack(pady=5, padx=5, fill="both", expand=True)

    def on_camera_selected(self, event=None):
        """Handle camera selection"""
        camera = self.camera_var.get()
        if camera:
            config = self.load_camera_config()
            roi = config[camera]['roi']
            self.log_message(f"Selected {camera}\nROI: {roi}")

    def load_camera_config(self):
        """Load camera configuration"""
        try:
            config_path = os.path.join(CONFIGS_DIR, "config.json")
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return {}

    def load_image(self, image_type):
        """Load an image for testing"""
        camera = self.camera_var.get()
        if not camera:
            messagebox.showwarning("Warning", "Please select a camera first")
            return
            
        try:
            file_path = filedialog.askopenfilename(
                title=f"Select {image_type.title()} Image",
                filetypes=[("Image files", "*.jpg *.jpeg *.png")]
            )
            
            if file_path:
                # Load and validate image
                image = Image.open(file_path)
                
                # Get expected dimensions from config
                config = self.load_camera_config()
                roi = config[camera]['roi']
                expected_width = abs(roi[2] - roi[0])
                expected_height = abs(roi[3] - roi[1])
                
                # Resize if needed
                if image.size != (expected_width, expected_height):
                    image = image.resize((expected_width, expected_height))
                
                # Store image
                if image_type == "base":
                    self.base_images[camera] = image
                else:
                    self.test_images[camera] = image
                
                self.update_image_info()
                
        except Exception as e:
            self.logger.error(f"Error loading {image_type} image: {e}")
            messagebox.showerror("Error", f"Failed to load image: {e}")

    def update_image_info(self):
        """Update image information display"""
        camera = self.camera_var.get()
        base_loaded = camera in self.base_images
        test_loaded = camera in self.test_images
        
        info_text = f"Camera: {camera}\n"
        info_text += f"Base Image: {'Loaded' if base_loaded else 'Not Loaded'}\n"
        info_text += f"Test Image: {'Loaded' if test_loaded else 'Not Loaded'}"
        
        self.image_info.configure(text=info_text)

    def run_detection_test(self):
        """Run owl detection test with loaded images"""
        camera = self.camera_var.get()
        if not camera:
            messagebox.showwarning("Warning", "Please select a camera first")
            return
            
        if camera not in self.base_images or camera not in self.test_images:
            messagebox.showwarning("Warning", "Please load both base and test images")
            return
            
        try:
            # Get configuration
            config = self.load_camera_config()
            camera_config = config[camera]
            
            # Get alert type
            alert_type = CAMERA_MAPPINGS[camera]
            
            # Process images based on camera type
            if alert_type == "Owl In Box":
                is_owl_present, detection_info = detect_owl_in_box(
                    self.test_images[camera],
                    self.base_images[camera],
                    camera_config,
                    is_test=True
                )
                self.display_results(is_owl_present, detection_info)
                
            else:
                # Create comparison image and analyze
                comparison_path = create_comparison_image(
                    self.base_images[camera],
                    self.test_images[camera],
                    camera_name=camera,
                    threshold=camera_config["luminance_threshold"],
                    config=camera_config,
                    is_test=True
                )
                
                # Analyze comparison image
                diff_image = Image.open(comparison_path)
                width = diff_image.size[0] // 3
                diff_panel = diff_image.crop((width * 2, 0, width * 3, diff_image.height))
                
                # Calculate metrics
                pixels_array = np.array(diff_panel.convert('L'))
                changed_pixels = np.sum(pixels_array > camera_config["luminance_threshold"])
                total_pixels = pixels_array.size
                
                motion_detected = (changed_pixels / total_pixels) > camera_config["threshold_percentage"]
                
                detection_info = {
                    "pixel_change": changed_pixels / total_pixels * 100,
                    "luminance_change": np.mean(pixels_array),
                    "threshold_used": camera_config["luminance_threshold"]
                }
                
                self.display_results(motion_detected, detection_info)
                
        except Exception as e:
            self.logger.error(f"Error running detection test: {e}")
            messagebox.showerror("Error", f"Detection test failed: {e}")

    def display_results(self, detection_result, info):
        """Display detection test results"""
        self.results_text.delete(1.0, tk.END)
        
        result_text = f"Detection Result: {'OWL DETECTED' if detection_result else 'NO OWL DETECTED'}\n\n"
        result_text += "Detection Metrics:\n"
        
        if isinstance(info, dict):
            for key, value in info.items():
                if isinstance(value, (int, float)):
                    result_text += f"{key}: {value:.2f}\n"
                elif isinstance(value, list):
                    result_text += f"{key}: {len(value)} items\n"
                else:
                    result_text += f"{key}: {value}\n"
        
        self.results_text.insert(1.0, result_text)

    def trigger_test_alert(self, alert_type):
        """Trigger a direct test alert"""
        try:
            self.logger.info(f"Triggering test alert: {alert_type}")
            
            # Get camera name for this alert type
            camera_name = next(
                (name for name, type_ in CAMERA_MAPPINGS.items() 
                 if type_ == alert_type),
                "Test Camera"
            )
            
            # Create simulated detection result
            detection_result = {
                "status": alert_type,
                "pixel_change": 50.0,
                "luminance_change": 40.0,
                "snapshot_path": "",
                "lighting_condition": "day",
                "detection_info": {
                    "confidence": 0.8,
                    "is_test": True
                },
                "motion_detected": True
            }
            
            # Process test alert
            alert_sent = self.alert_manager.process_detection(camera_name, detection_result)
            
            # Display result
            result_text = f"Test Alert: {alert_type}\n"
            result_text += f"Alert Sent: {'Yes' if alert_sent else 'No (blocked by delay)'}"
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(1.0, result_text)
            
        except Exception as e:
            self.logger.error(f"Error triggering test alert: {e}")
            messagebox.showerror("Error", f"Failed to trigger alert: {e}")

    def log_message(self, message):
        """Log a message to both logger and results display"""
        self.logger.info(message)
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(1.0, message)