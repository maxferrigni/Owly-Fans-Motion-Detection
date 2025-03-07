# File: motion_detection_settings.py
# Purpose: GUI controls for motion detection parameters
# 
# March 7, 2025 Update - Version 1.4.2
# - Fixed excessive digits in settings display
# - Improved layout to save vertical space
# - Added error handling to settings operations
# - Fixed update propagation between controls

import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import traceback
from utilities.constants import CONFIGS_DIR, CAMERA_MAPPINGS
from utilities.logging_utils import get_logger

class MotionDetectionSettings:
    def __init__(self, parent_frame, logger=None):
        self.parent_frame = parent_frame
        self.logger = logger or get_logger()
        
        # Create main settings frame
        self.settings_frame = ttk.LabelFrame(
            self.parent_frame,
            text="Motion Detection Settings"
        )
        self.settings_frame.pack(pady=5, padx=5, fill="x")
        
        # Load current configuration
        self.config = self.load_config()
        
        # Track original values for changes
        self.original_values = {}
        
        # Create interface elements
        self.create_settings_interface()
        
    def load_config(self):
        """Load current configuration from config.json"""
        try:
            config_path = os.path.join(CONFIGS_DIR, "config.json")
            if not os.path.exists(config_path):
                raise FileNotFoundError(f"Configuration file not found: {config_path}")
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            self.show_error("Error", f"Failed to load configuration: {e}")
            return {}
            
    def save_config(self):
        """Save current configuration to config.json"""
        try:
            config_path = os.path.join(CONFIGS_DIR, "config.json")
            with open(config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            self.logger.info("Configuration saved successfully")
            messagebox.showinfo("Success", "Settings saved successfully")
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")
            self.show_error("Error", f"Failed to save configuration: {e}")

    def create_settings_interface(self):
        """Create the settings interface with tabbed layout"""
        # Create notebook for tabbed interface
        self.notebook = ttk.Notebook(self.settings_frame)
        self.notebook.pack(fill="x", padx=5, pady=5)
        
        # Create tab for each camera type
        self.camera_tabs = {}
        for camera, alert_type in CAMERA_MAPPINGS.items():
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=alert_type)
            self.camera_tabs[camera] = tab
            self.create_camera_settings(tab, camera)
            
        # Create control buttons
        self.create_control_buttons()
        
    def create_camera_settings(self, tab, camera):
        """Create settings controls for a specific camera"""
        # Create frame for sliders
        settings_frame = ttk.Frame(tab)
        settings_frame.pack(fill="x", padx=5, pady=5)
        
        # Get current settings
        camera_config = self.config.get(camera, {})
        
        # Store original values
        self.original_values[camera] = {}
        
        # Create main parameter controls
        self.create_parameter_control(
            settings_frame, camera,
            "threshold_percentage", "Threshold %",
            0.01, 1.0, camera_config.get("threshold_percentage", 0.05),
            0.01
        )
        
        self.create_parameter_control(
            settings_frame, camera,
            "luminance_threshold", "Luminance",
            1, 100, camera_config.get("luminance_threshold", 40),
            1
        )
        
        # Create confidence threshold controls
        confidence_frame = ttk.LabelFrame(tab, text="Confidence Thresholds")
        confidence_frame.pack(fill="x", padx=5, pady=5)
        
        # Get default confidence threshold based on camera type
        default_confidence = 60.0
        if CAMERA_MAPPINGS.get(camera) == "Owl In Box":
            default_confidence = 75.0
        elif CAMERA_MAPPINGS.get(camera) == "Owl On Box":
            default_confidence = 65.0
        elif CAMERA_MAPPINGS.get(camera) == "Owl In Area":
            default_confidence = 55.0
            
        self.create_parameter_control(
            confidence_frame, camera,
            "owl_confidence_threshold", "Owl Confidence %",
            0.0, 100.0, camera_config.get("owl_confidence_threshold", default_confidence),
            1.0
        )
        
        self.create_parameter_control(
            confidence_frame, camera,
            "consecutive_frames_threshold", "Consecutive Frames",
            1, 10, camera_config.get("consecutive_frames_threshold", 2),
            1,
            is_integer=True
        )
        
        # Create confidence description frame
        confidence_desc_frame = ttk.Frame(confidence_frame)
        confidence_desc_frame.pack(fill="x", padx=5, pady=5)
        
        confidence_desc_text = (
            f"Recommended confidence values:\n"
            f"• Owl In Box: 70-80%\n"
            f"• Owl On Box: 60-70%\n"
            f"• Owl In Area: 50-60%\n"
            f"Higher values = fewer false positives but may miss detections.\n"
            f"Lower values = more detections but may have more false positives."
        )
        
        ttk.Label(
            confidence_desc_frame, 
            text=confidence_desc_text,
            wraplength=400
        ).pack(padx=5, pady=5)
        
        # Create motion detection parameter controls
        motion_frame = ttk.LabelFrame(tab, text="Motion Detection Parameters")
        motion_frame.pack(fill="x", padx=5, pady=5)
        
        motion_params = camera_config.get("motion_detection", {})
        
        self.create_parameter_control(
            motion_frame, camera,
            "min_circularity", "Min Circularity",
            0.1, 1.0, motion_params.get("min_circularity", 0.5),
            0.1,
            is_motion_param=True
        )
        
        self.create_parameter_control(
            motion_frame, camera,
            "min_aspect_ratio", "Min Aspect Ratio",
            0.1, 2.0, motion_params.get("min_aspect_ratio", 0.5),
            0.1,
            is_motion_param=True
        )
        
        self.create_parameter_control(
            motion_frame, camera,
            "max_aspect_ratio", "Max Aspect Ratio",
            1.0, 3.0, motion_params.get("max_aspect_ratio", 2.0),
            0.1,
            is_motion_param=True
        )
        
        self.create_parameter_control(
            motion_frame, camera,
            "min_area_ratio", "Min Area Ratio",
            0.01, 1.0, motion_params.get("min_area_ratio", 0.2),
            0.01,
            is_motion_param=True
        )
        
        self.create_parameter_control(
            motion_frame, camera,
            "brightness_threshold", "Brightness",
            1, 100, motion_params.get("brightness_threshold", 35),
            1,
            is_motion_param=True
        )

    def create_parameter_control(self, parent, camera, param_name, label_text, 
                               min_val, max_val, default_val, resolution,
                               is_motion_param=False, is_integer=False):
        """Create a labeled scale control for a parameter"""
        try:
            frame = ttk.Frame(parent)
            frame.pack(fill="x", padx=5, pady=2)
            
            # Create label
            ttk.Label(frame, text=label_text, width=15, anchor="w").pack(side=tk.LEFT)
            
            # Create scale
            var = tk.DoubleVar(value=default_val)
            scale = ttk.Scale(
                frame,
                from_=min_val,
                to=max_val,
                variable=var,
                orient="horizontal"
            )
            scale.pack(side=tk.LEFT, fill="x", expand=True, padx=5)
            
            # Create value entry with limited width
            entry = ttk.Entry(frame, width=8)
            entry.pack(side=tk.LEFT)
            
            # Format value appropriately for initial display
            if is_integer:
                entry.insert(0, str(int(default_val)))
            else:
                # Format with appropriate decimal places
                if resolution < 0.1:
                    # For small resolutions (like 0.01), use 2 decimal places
                    entry.insert(0, f"{default_val:.2f}")
                else:
                    # For larger resolutions, use 1 decimal place
                    entry.insert(0, f"{default_val:.1f}")
            
            # Store original value
            if is_motion_param:
                if "motion_detection" not in self.original_values[camera]:
                    self.original_values[camera]["motion_detection"] = {}
                self.original_values[camera]["motion_detection"][param_name] = default_val
            else:
                self.original_values[camera][param_name] = default_val
            
            # Update functions
            def update_entry(*args):
                try:
                    value = var.get()
                    if is_integer:
                        value = int(value)
                        entry.delete(0, tk.END)
                        entry.insert(0, f"{value}")
                    else:
                        entry.delete(0, tk.END)
                        # Format with appropriate decimal places
                        if resolution < 0.1:
                            entry.insert(0, f"{value:.2f}")
                        else:
                            entry.insert(0, f"{value:.1f}")
                    self.update_config(camera, param_name, value, is_motion_param)
                except Exception as e:
                    self.logger.error(f"Error updating entry: {e}")
                    self.show_error("Settings Error", f"Error updating value: {e}")
                
            def update_scale(event):
                try:
                    raw_value = entry.get()
                    # Remove any non-numeric characters except decimal point
                    clean_value = ''.join(c for c in raw_value if c.isdigit() or c == '.')
                    
                    # Convert to appropriate type
                    if is_integer:
                        try:
                            value = int(float(clean_value))
                        except ValueError:
                            value = int(default_val)
                    else:
                        try:
                            value = float(clean_value)
                        except ValueError:
                            value = default_val
                    
                    # Enforce boundaries
                    value = max(min_val, min(max_val, value))
                    
                    # Update scale
                    var.set(value)
                    
                    # Update entry with properly formatted value
                    entry.delete(0, tk.END)
                    if is_integer:
                        entry.insert(0, f"{value}")
                    else:
                        # Format with appropriate decimal places
                        if resolution < 0.1:
                            entry.insert(0, f"{value:.2f}")
                        else:
                            entry.insert(0, f"{value:.1f}")
                            
                    # Update config
                    self.update_config(camera, param_name, value, is_motion_param)
                except Exception as e:
                    self.logger.error(f"Error updating scale: {e}")
                    # Reset to default on error
                    var.set(default_val)
                    entry.delete(0, tk.END)
                    if is_integer:
                        entry.insert(0, f"{int(default_val)}")
                    else:
                        if resolution < 0.1:
                            entry.insert(0, f"{default_val:.2f}")
                        else:
                            entry.insert(0, f"{default_val:.1f}")
            
            # Bind updates
            var.trace_add("write", update_entry)
            entry.bind('<Return>', update_scale)
            entry.bind('<FocusOut>', update_scale)
        except Exception as e:
            self.logger.error(f"Error creating parameter control: {e}")
            self.show_error("Settings Error", f"Failed to create parameter control: {e}")

    def update_config(self, camera, param_name, value, is_motion_param):
        """Update configuration with new parameter value"""
        try:
            if is_motion_param:
                if "motion_detection" not in self.config[camera]:
                    self.config[camera]["motion_detection"] = {}
                self.config[camera]["motion_detection"][param_name] = value
            else:
                self.config[camera][param_name] = value
        except Exception as e:
            self.logger.error(f"Error updating config: {e}")
            self.show_error("Settings Error", f"Failed to update configuration: {e}")

    def create_control_buttons(self):
        """Create save and reset buttons"""
        button_frame = ttk.Frame(self.settings_frame)
        button_frame.pack(fill="x", padx=5, pady=5)
        
        # Save button
        ttk.Button(
            button_frame,
            text="Save Changes",
            command=self.save_config_with_error_handling
        ).pack(side=tk.LEFT, padx=5)
        
        # Reset button
        ttk.Button(
            button_frame,
            text="Reset to Default",
            command=self.reset_to_default_with_error_handling
        ).pack(side=tk.LEFT, padx=5)
        
        # Apply to running system button
        ttk.Button(
            button_frame,
            text="Apply Now",
            command=self.apply_to_running_system_with_error_handling
        ).pack(side=tk.LEFT, padx=5)

    def save_config_with_error_handling(self):
        """Save config with error handling"""
        try:
            self.save_config()
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")
            self.logger.error(traceback.format_exc())
            self.show_error("Error", f"Failed to save configuration: {e}")

    def reset_to_default_with_error_handling(self):
        """Reset all parameters to their original values with error handling"""
        try:
            self.reset_to_default()
        except Exception as e:
            self.logger.error(f"Error resetting to default: {e}")
            self.logger.error(traceback.format_exc())
            self.show_error("Error", f"Failed to reset settings: {e}")

    def apply_to_running_system_with_error_handling(self):
        """Apply settings to running system with error handling"""
        try:
            self.apply_to_running_system()
        except Exception as e:
            self.logger.error(f"Error applying to running system: {e}")
            self.logger.error(traceback.format_exc())
            self.show_error("Error", f"Failed to apply settings: {e}")

    def reset_to_default(self):
        """Reset all parameters to their original values"""
        try:
            for camera, values in self.original_values.items():
                for param, value in values.items():
                    if param == "motion_detection":
                        for motion_param, motion_value in value.items():
                            self.config[camera]["motion_detection"][motion_param] = motion_value
                    else:
                        self.config[camera][param] = value
            
            # Reload interface
            self.notebook.destroy()
            self.create_settings_interface()
            
            self.logger.info("Settings reset to original values")
            messagebox.showinfo("Reset", "Settings have been reset to original values")
            
        except Exception as e:
            self.logger.error(f"Error resetting settings: {e}")
            raise
            
    def apply_to_running_system(self):
        """Apply current settings to the running system without restarting"""
        try:
            # First save the configuration
            self.save_config()
            
            # Try to communicate with the running system
            try:
                # Import motion_workflow here to avoid circular imports
                from scripts.motion_workflow import update_thresholds
                
                # Extract confidence thresholds
                thresholds = {}
                for camera, config in self.config.items():
                    if "owl_confidence_threshold" in config:
                        thresholds[camera] = config["owl_confidence_threshold"]
                
                # Update running system
                result = update_thresholds(self.config, thresholds)
                
                if result:
                    self.logger.info("Settings applied to running system")
                    messagebox.showinfo("Success", "Settings applied to running system")
                else:
                    messagebox.showwarning("Warning", "Could not apply all settings to running system")
                    
            except ImportError:
                # If motion_workflow isn't available, inform the user
                self.logger.warning("Could not import motion_workflow module")
                messagebox.showinfo("Info", "Changes will take effect after restarting motion detection")
                
        except Exception as e:
            self.logger.error(f"Error applying settings: {e}")
            raise

    def get_confidence_thresholds(self):
        """Get all configured confidence thresholds"""
        try:
            thresholds = {}
            for camera, config in self.config.items():
                if "owl_confidence_threshold" in config:
                    thresholds[camera] = config["owl_confidence_threshold"]
            return thresholds
        except Exception as e:
            self.logger.error(f"Error getting confidence thresholds: {e}")
            return {}
            
    def show_error(self, title, message):
        """Show error message box and log the error"""
        self.logger.error(message)
        messagebox.showerror(title, message)

if __name__ == "__main__":
    # Test the interface
    root = tk.Tk()
    root.title("Motion Detection Settings Test")
    
    app = MotionDetectionSettings(root)
    
    root.mainloop()