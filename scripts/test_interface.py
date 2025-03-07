# File: test_interface.py
# Purpose: Handle test mode functionality for the Owl Monitoring System with confidence metrics

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
from utilities.confidence_utils import reset_frame_history

class TestInterface:
    def __init__(self, parent_frame, logger, alert_manager):
        self.parent_frame = parent_frame
        self.logger = logger or get_logger()
        self.alert_manager = alert_manager
        
        # Track loaded images
        self.base_images = {}  # {camera_type: Image}
        self.test_images = {}  # {camera_type: Image}
        
        # Track test confidence settings
        self.confidence_threshold_var = tk.DoubleVar(value=60.0)
        self.consecutive_frames_var = tk.IntVar(value=2)
        
        # Create the test interface
        self.create_interface()
        
    def create_interface(self):
        """Create test mode interface elements"""
        # Create main sections
        self.create_image_testing_interface()
        self.create_confidence_settings_interface()
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

    def create_confidence_settings_interface(self):
        """Create interface for confidence threshold settings"""
        self.confidence_frame = ttk.LabelFrame(self.parent_frame, text="Confidence Settings")
        self.confidence_frame.pack(pady=5, fill="x")
        
        # Confidence threshold control
        confidence_frame = ttk.Frame(self.confidence_frame)
        confidence_frame.pack(pady=5, fill="x")
        
        ttk.Label(
            confidence_frame, 
            text="Confidence Threshold (%)"
        ).pack(side=tk.LEFT, padx=5)
        
        confidence_scale = ttk.Scale(
            confidence_frame,
            from_=0,
            to=100,
            variable=self.confidence_threshold_var,
            orient="horizontal"
        )
        confidence_scale.pack(side=tk.LEFT, fill="x", expand=True, padx=5)
        
        confidence_entry = ttk.Entry(confidence_frame, width=5)
        confidence_entry.pack(side=tk.LEFT, padx=5)
        confidence_entry.insert(0, str(self.confidence_threshold_var.get()))
        
        # Update functions for confidence threshold
        def update_confidence_entry(*args):
            value = self.confidence_threshold_var.get()
            confidence_entry.delete(0, tk.END)
            confidence_entry.insert(0, f"{value:.1f}")
            
        def update_confidence_scale(event):
            try:
                value = float(confidence_entry.get())
                if 0 <= value <= 100:
                    self.confidence_threshold_var.set(value)
            except ValueError:
                confidence_entry.delete(0, tk.END)
                confidence_entry.insert(0, f"{self.confidence_threshold_var.get():.1f}")
        
        # Bind updates
        self.confidence_threshold_var.trace_add("write", update_confidence_entry)
        confidence_entry.bind('<Return>', update_confidence_scale)
        confidence_entry.bind('<FocusOut>', update_confidence_scale)
        
        # Consecutive frames control
        frames_frame = ttk.Frame(self.confidence_frame)
        frames_frame.pack(pady=5, fill="x")
        
        ttk.Label(
            frames_frame, 
            text="Consecutive Frames"
        ).pack(side=tk.LEFT, padx=5)
        
        frames_spinbox = ttk.Spinbox(
            frames_frame,
            from_=1,
            to=10,
            textvariable=self.consecutive_frames_var,
            width=5
        )
        frames_spinbox.pack(side=tk.LEFT, padx=5)
        
        # Add guidance text
        guidance_frame = ttk.Frame(self.confidence_frame)
        guidance_frame.pack(pady=5, fill="x")
        
        guidance_text = (
            "Recommended confidence values:\n"
            "• Owl In Box: 70-80%\n"
            "• Owl On Box: 60-70%\n"
            "• Owl In Area: 50-60%"
        )
        
        ttk.Label(
            guidance_frame,
            text=guidance_text
        ).pack(padx=5, pady=2)
        
        # Reset button
        ttk.Button(
            frames_frame,
            text="Reset Frame History",
            command=self.reset_frame_history
        ).pack(side=tk.RIGHT, padx=5)

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
        """Create results display area with confidence metrics"""
        self.results_frame = ttk.LabelFrame(self.parent_frame, text="Test Results")
        self.results_frame.pack(pady=5, fill="both", expand=True)
        
        # Create progress bar indicators for confidence
        confidence_indicators_frame = ttk.Frame(self.results_frame)
        confidence_indicators_frame.pack(pady=5, fill="x")
        
        # Total confidence indicator
        ttk.Label(
            confidence_indicators_frame,
            text="Total Confidence:"
        ).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        
        self.total_confidence_var = tk.DoubleVar(value=0.0)
        self.total_confidence_bar = ttk.Progressbar(
            confidence_indicators_frame,
            orient="horizontal",
            length=200,
            mode="determinate",
            variable=self.total_confidence_var
        )
        self.total_confidence_bar.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        
        self.total_confidence_label = ttk.Label(
            confidence_indicators_frame,
            text="0.0%"
        )
        self.total_confidence_label.grid(row=0, column=2, padx=5, pady=2)
        
        # Threshold line
        self.threshold_indicator = ttk.Label(
            confidence_indicators_frame,
            text="Threshold: 60.0%"
        )
        self.threshold_indicator.grid(row=0, column=3, padx=5, pady=2)
        
        # Component confidence indicators
        components = [
            ("Shape Confidence", "shape_confidence_var", "shape_confidence_bar", "shape_confidence_label"),
            ("Motion Confidence", "motion_confidence_var", "motion_confidence_bar", "motion_confidence_label"),
            ("Temporal Confidence", "temporal_confidence_var", "temporal_confidence_bar", "temporal_confidence_label"),
            ("Camera Confidence", "camera_confidence_var", "camera_confidence_bar", "camera_confidence_label")
        ]
        
        # Create component indicators
        for i, (label_text, var_name, bar_name, label_name) in enumerate(components):
            ttk.Label(
                confidence_indicators_frame,
                text=label_text + ":"
            ).grid(row=i+1, column=0, sticky="w", padx=5, pady=2)
            
            # Create variable
            setattr(self, var_name, tk.DoubleVar(value=0.0))
            var = getattr(self, var_name)
            
            # Create progress bar
            bar = ttk.Progressbar(
                confidence_indicators_frame,
                orient="horizontal",
                length=200,
                mode="determinate",
                variable=var
            )
            bar.grid(row=i+1, column=1, sticky="ew", padx=5, pady=2)
            setattr(self, bar_name, bar)
            
            # Create value label
            label = ttk.Label(
                confidence_indicators_frame,
                text="0.0%"
            )
            label.grid(row=i+1, column=2, padx=5, pady=2)
            setattr(self, label_name, label)
        
        # Configure the grid to expand
        confidence_indicators_frame.columnconfigure(1, weight=1)
        
        # Consecutive frames indicator
        frames_frame = ttk.Frame(self.results_frame)
        frames_frame.pack(pady=5, fill="x")
        
        ttk.Label(
            frames_frame,
            text="Consecutive Frames:"
        ).pack(side=tk.LEFT, padx=5)
        
        self.consecutive_frames_label = ttk.Label(
            frames_frame,
            text="0"
        )
        self.consecutive_frames_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(
            frames_frame,
            text="Required:"
        ).pack(side=tk.LEFT, padx=5)
        
        self.frames_threshold_label = ttk.Label(
            frames_frame,
            text="2"
        )
        self.frames_threshold_label.pack(side=tk.LEFT, padx=5)
        
        # Detection result indicator
        self.detection_result_var = tk.StringVar(value="No Detection Run")
        self.detection_result_label = ttk.Label(
            self.results_frame,
            textvariable=self.detection_result_var,
            font=("Arial", 12, "bold")
        )
        self.detection_result_label.pack(pady=10)
        
        # Detailed results text area
        self.results_text = tk.Text(
            self.results_frame,
            height=12,
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
            
            # Update confidence threshold from config if available
            if "owl_confidence_threshold" in config[camera]:
                self.confidence_threshold_var.set(config[camera]["owl_confidence_threshold"])
                
            # Update consecutive frames threshold from config if available
            if "consecutive_frames_threshold" in config[camera]:
                self.consecutive_frames_var.set(config[camera]["consecutive_frames_threshold"])
                
            self.log_message(f"Selected {camera}\nROI: {roi}")
            
            # Update threshold indicator
            self.threshold_indicator.config(
                text=f"Threshold: {self.confidence_threshold_var.get():.1f}%"
            )
            
            # Update frames threshold label
            self.frames_threshold_label.config(
                text=str(self.consecutive_frames_var.get())
            )

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
        """Run owl detection test with loaded images using confidence metrics"""
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
            
            # Add or update confidence thresholds in config
            camera_config["owl_confidence_threshold"] = self.confidence_threshold_var.get()
            camera_config["consecutive_frames_threshold"] = self.consecutive_frames_var.get()
            
            # Update the threshold indicator
            self.threshold_indicator.config(
                text=f"Threshold: {self.confidence_threshold_var.get():.1f}%"
            )
            
            # Update the frames threshold label
            self.frames_threshold_label.config(
                text=str(self.consecutive_frames_var.get())
            )
            
            # Run the detection with confidence metrics
            is_present, info = detect_owl_in_box(
                self.test_images[camera],
                self.base_images[camera],
                camera_config,
                is_test=True,
                camera_name=camera
            )
            
            # Create confidence-enhanced comparison image
            create_comparison_image(
                self.base_images[camera],
                self.test_images[camera],
                camera_name=camera,
                threshold=camera_config["luminance_threshold"],
                config=camera_config,
                detection_info=info,
                is_test=True
            )
            
            # Display results with confidence metrics
            self.display_results(is_present, info)
                
        except Exception as e:
            self.logger.error(f"Error running detection test: {e}")
            messagebox.showerror("Error", f"Detection test failed: {e}")

    def display_results(self, detection_result, info):
        """Display detection test results with confidence information"""
        self.results_text.delete(1.0, tk.END)
        
        # Extract confidence metrics
        owl_confidence = info.get("owl_confidence", 0.0)
        consecutive_frames = info.get("consecutive_owl_frames", 0)
        confidence_factors = info.get("confidence_factors", {})
        
        # Update confidence indicators
        self.total_confidence_var.set(owl_confidence)
        self.total_confidence_label.config(text=f"{owl_confidence:.1f}%")
        
        self.shape_confidence_var.set(confidence_factors.get("shape_confidence", 0.0))
        self.shape_confidence_label.config(
            text=f"{confidence_factors.get('shape_confidence', 0.0):.1f}%"
        )
        
        self.motion_confidence_var.set(confidence_factors.get("motion_confidence", 0.0))
        self.motion_confidence_label.config(
            text=f"{confidence_factors.get('motion_confidence', 0.0):.1f}%"
        )
        
        self.temporal_confidence_var.set(confidence_factors.get("temporal_confidence", 0.0))
        self.temporal_confidence_label.config(
            text=f"{confidence_factors.get('temporal_confidence', 0.0):.1f}%"
        )
        
        self.camera_confidence_var.set(confidence_factors.get("camera_confidence", 0.0))
        self.camera_confidence_label.config(
            text=f"{confidence_factors.get('camera_confidence', 0.0):.1f}%"
        )
        
        # Update consecutive frames indicator
        self.consecutive_frames_label.config(text=str(consecutive_frames))
        
        # Color-code progress bars
        threshold = self.confidence_threshold_var.get()
        frames_threshold = self.consecutive_frames_var.get()
        
        # Set detection result with color
        if detection_result:
            result_text = "OWL DETECTED"
            self.detection_result_var.set(result_text)
            self.detection_result_label.config(foreground="green")
        else:
            result_text = "NO OWL DETECTED"
            self.detection_result_var.set(result_text)
            self.detection_result_label.config(foreground="red")
        
        # Prepare detection summary
        result_text = f"Detection Result: {'OWL DETECTED' if detection_result else 'NO OWL DETECTED'}\n"
        result_text += f"Owl Confidence: {owl_confidence:.1f}%\n"
        result_text += f"Consecutive Frames: {consecutive_frames}\n"
        
        # Check if confidence meets threshold
        if owl_confidence >= threshold and consecutive_frames >= frames_threshold:
            result_text += "Alert Status: WOULD TRIGGER ALERT\n"
        else:
            reasons = []
            if owl_confidence < threshold:
                reasons.append(f"confidence too low ({owl_confidence:.1f}% < {threshold}%)")
            if consecutive_frames < frames_threshold:
                reasons.append(f"not enough consecutive frames ({consecutive_frames} < {frames_threshold})")
                
            reason_text = " and ".join(reasons)
            result_text += f"Alert Status: WOULD NOT TRIGGER ALERT ({reason_text})\n"
            
        result_text += "\nDetection Metrics:\n"
        
        if isinstance(info, dict):
            # Display standard metrics
            for key, value in info.items():
                if key not in ["confidence_factors", "owl_confidence", "consecutive_owl_frames"]:
                    if isinstance(value, (int, float)):
                        result_text += f"{key}: {value:.2f}\n"
                    elif isinstance(value, list):
                        result_text += f"{key}: {len(value)} items\n"
                    elif not isinstance(value, dict):  # Skip nested dictionaries
                        result_text += f"{key}: {value}\n"
            
            # Display confidence factors
            result_text += "\nConfidence Breakdown:\n"
            for factor, value in confidence_factors.items():
                result_text += f"{factor.replace('_', ' ').title()}: {value:.1f}%\n"
        
        self.results_text.insert(1.0, result_text)

    def trigger_test_alert(self, alert_type):
        """Trigger a direct test alert with confidence metrics"""
        try:
            # Disable buttons during processing to prevent double clicks
            for btn in self.alert_buttons.values():
                btn.config(state=tk.DISABLED)
                
            # Show a "sending" message
            self.detection_result_var.set(f"SENDING {alert_type.upper()} ALERT...")
            self.detection_result_label.config(foreground="blue")
            
            # Update UI immediately
            self.parent_frame.update_idletasks()
            
            self.logger.info(f"Triggering test alert: {alert_type}")
            
            # Get camera name for this alert type
            camera_name = next(
                (name for name, type_ in CAMERA_MAPPINGS.items() 
                 if type_ == alert_type),
                "Test Camera"
            )
            
            # Get confidence thresholds
            confidence = self.confidence_threshold_var.get()
            frames = self.consecutive_frames_var.get()
            
            # Create simulated detection result with confidence metrics
            detection_result = {
                "camera": camera_name,
                "status": alert_type,
                "is_owl_present": True,
                "motion_detected": True,
                "pixel_change": 50.0,
                "luminance_change": 40.0,
                "snapshot_path": "",
                "lighting_condition": "day",
                "owl_confidence": confidence,  # Use UI value
                "consecutive_owl_frames": frames,  # Use UI value
                "threshold_used": confidence,  # Add threshold used
                "confidence_factors": {
                    "shape_confidence": confidence * 0.5,  # Mock values proportional to total
                    "motion_confidence": confidence * 0.3,
                    "temporal_confidence": confidence * 0.15,
                    "camera_confidence": confidence * 0.05
                }
            }
            
            # Process test alert - IMPORTANT: Set is_test=True to bypass confidence checks
            alert_sent = self.alert_manager.process_detection(
                camera_name,
                detection_result,
                is_test=True  # This is the critical change
            )
            
            # Display result
            result_text = f"Test Alert: {alert_type}\n"
            result_text += f"Confidence: {confidence:.1f}%\n"
            result_text += f"Consecutive Frames: {frames}\n"
            result_text += f"Alert Sent: {'Yes' if alert_sent else 'No (blocked by rules)'}"
            result_text += f"\n\nNote: Emails and SMS alerts are being sent in the background."
            result_text += f"\nCheck logs for delivery confirmation."
            
            # Update the detection result label
            if alert_sent:
                self.detection_result_var.set(f"TEST ALERT SENT: {alert_type}")
                self.detection_result_label.config(foreground="green")
            else:
                self.detection_result_var.set(f"TEST ALERT BLOCKED: {alert_type}")
                self.detection_result_label.config(foreground="red")
            
            # Update confidence indicators with mock values
            self.total_confidence_var.set(confidence)
            self.total_confidence_label.config(text=f"{confidence:.1f}%")
            
            self.shape_confidence_var.set(confidence * 0.5)
            self.shape_confidence_label.config(text=f"{confidence * 0.5:.1f}%")
            
            self.motion_confidence_var.set(confidence * 0.3)
            self.motion_confidence_label.config(text=f"{confidence * 0.3:.1f}%")
            
            self.temporal_confidence_var.set(confidence * 0.15)
            self.temporal_confidence_label.config(text=f"{confidence * 0.15:.1f}%")
            
            self.camera_confidence_var.set(confidence * 0.05)
            self.camera_confidence_label.config(text=f"{confidence * 0.05:.1f}%")
            
            # Update consecutive frames indicator
            self.consecutive_frames_label.config(text=str(frames))
            
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(1.0, result_text)
            
        except Exception as e:
            self.logger.error(f"Error triggering test alert: {e}")
            messagebox.showerror("Error", f"Failed to trigger alert: {e}")
        finally:
            # Re-enable buttons once processing is complete
            for btn in self.alert_buttons.values():
                btn.config(state=tk.NORMAL)

    def reset_frame_history(self):
        """Reset the frame history for testing multiple images"""
        try:
            reset_frame_history()
            self.logger.info("Frame history has been reset")
            messagebox.showinfo("Reset", "Frame history has been reset successfully")
        except Exception as e:
            self.logger.error(f"Error resetting frame history: {e}")
            messagebox.showerror("Error", f"Failed to reset frame history: {e}")

    def log_message(self, message):
        """Log a message to both logger and results display"""
        self.logger.info(message)
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(1.0, message)