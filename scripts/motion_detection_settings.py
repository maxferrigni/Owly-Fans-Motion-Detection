# File: motion_detection_settings.py
# Purpose: GUI controls for motion detection parameters
# 
# March 19, 2025 Update - Version 1.4.6
# - Added day/night settings toggle functionality
# - Removed outdated confidence threshold guidance
# - Improved UI layout for better space utilization

import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
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
        
        # Current lighting mode for settings (day or night)
        self.lighting_mode = tk.StringVar(value="day")
        
        # Track original values for changes
        self.original_values = {}
        
        # Create interface elements
        self.create_settings_interface()
        
    def load_config(self):
        """Load current configuration from config.json"""
        try:
            config_path = os.path.join(CONFIGS_DIR, "config.json")
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            messagebox.showerror("Error", f"Failed to load configuration: {e}")
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
            messagebox.showerror("Error", f"Failed to save configuration: {e}")

    def create_settings_interface(self):
        """Create the settings interface with tabbed layout"""
        # Create notebook for tabbed interface
        self.notebook = ttk.Notebook(self.settings_frame)
        self.notebook.pack(fill="x", padx=5, pady=5)
        
        # Create lighting mode selector
        mode_frame = ttk.Frame(self.settings_frame)
        mode_frame.pack(fill="x", padx=5, pady=(0, 5))
        
        ttk.Label(
            mode_frame, 
            text="Edit Settings For:",
            font=("Arial", 10, "bold")
        ).pack(side=tk.LEFT, padx=5)
        
        # Create day/night mode toggle with radio buttons
        day_radio = ttk.Radiobutton(
            mode_frame,
            text="Day Settings",
            variable=self.lighting_mode,
            value="day",
            command=self.update_settings_view
        )
        day_radio.pack(side=tk.LEFT, padx=10)
        
        night_radio = ttk.Radiobutton(
            mode_frame,
            text="Night Settings",
            variable=self.lighting_mode,
            value="night",
            command=self.update_settings_view
        )
        night_radio.pack(side=tk.LEFT, padx=10)
        
        # Create tab for each camera type
        self.camera_tabs = {}
        for camera, alert_type in CAMERA_MAPPINGS.items():
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=alert_type)
            self.camera_tabs[camera] = tab
            self.create_camera_settings(tab, camera)
            
        # Create control buttons
        self.create_control_buttons()
        
    def update_settings_view(self):
        """Update settings view based on selected lighting mode (day/night)"""
        # Get current lighting mode
        lighting_mode = self.lighting_mode.get()
        self.logger.info(f"Switching to {lighting_mode} settings view")
        
        # Refresh all camera settings tabs
        for camera, tab in self.camera_tabs.items():
            # Clear existing widgets
            for widget in tab.winfo_children():
                widget.destroy()
                
            # Recreate settings
            self.create_camera_settings(tab, camera)
            
    def create_camera_settings(self, tab, camera):
        """Create settings controls for a specific camera"""
        # Create frame for sliders
        settings_frame = ttk.Frame(tab)
        settings_frame.pack(fill="x", padx=5, pady=5)
        
        # Get current lighting mode
        lighting_mode = self.lighting_mode.get()
        
        # Get appropriate settings based on lighting mode
        settings_key = f"{lighting_mode}_settings"
        
        # Get current settings
        camera_config = self.config.get(camera, {})
        
        # Handle legacy configuration
        if settings_key not in camera_config:
            # If no day/night settings exist, migrate from legacy config
            self.migrate_legacy_config(camera)
            camera_config = self.config.get(camera, {})
            
        # Get the lighting-specific settings
        lighting_settings = camera_config.get(settings_key, {})
        
        # Add mode indicator to frame title
        mode_text = "Day" if lighting_mode == "day" else "Night"
        settings_label = ttk.Label(
            settings_frame, 
            text=f"{mode_text} Settings for {camera}",
            font=("Arial", 10, "bold")
        )
        settings_label.pack(anchor="w", pady=(0, 10))
        
        # Store original values
        if camera not in self.original_values:
            self.original_values[camera] = {}
        
        if settings_key not in self.original_values[camera]:
            self.original_values[camera][settings_key] = {}
        
        # Create main parameter controls
        self.create_parameter_control(
            settings_frame, camera,
            "threshold_percentage", "Threshold %",
            0.01, 1.0, lighting_settings.get("threshold_percentage", 0.05),
            0.01,
            is_lighting_param=True
        )
        
        self.create_parameter_control(
            settings_frame, camera,
            "luminance_threshold", "Luminance",
            1, 100, lighting_settings.get("luminance_threshold", 40),
            1,
            is_lighting_param=True
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
            0.0, 100.0, lighting_settings.get("owl_confidence_threshold", default_confidence),
            1.0,
            is_lighting_param=True
        )
        
        self.create_parameter_control(
            confidence_frame, camera,
            "consecutive_frames_threshold", "Consecutive Frames",
            1, 10, camera_config.get("consecutive_frames_threshold", 2),
            1,
            is_integer=True
        )

        # Create motion detection parameter controls
        motion_frame = ttk.LabelFrame(tab, text="Motion Detection Parameters")
        motion_frame.pack(fill="x", padx=5, pady=5)
        
        motion_params = lighting_settings.get("motion_detection", {})
        
        self.create_parameter_control(
            motion_frame, camera,
            "min_circularity", "Min Circularity",
            0.1, 1.0, motion_params.get("min_circularity", 0.5),
            0.1,
            is_motion_param=True,
            is_lighting_param=True
        )
        
        self.create_parameter_control(
            motion_frame, camera,
            "min_aspect_ratio", "Min Aspect Ratio",
            0.1, 2.0, motion_params.get("min_aspect_ratio", 0.5),
            0.1,
            is_motion_param=True,
            is_lighting_param=True
        )
        
        self.create_parameter_control(
            motion_frame, camera,
            "max_aspect_ratio", "Max Aspect Ratio",
            1.0, 3.0, motion_params.get("max_aspect_ratio", 2.0),
            0.1,
            is_motion_param=True,
            is_lighting_param=True
        )
        
        self.create_parameter_control(
            motion_frame, camera,
            "min_area_ratio", "Min Area Ratio",
            0.01, 1.0, motion_params.get("min_area_ratio", 0.2),
            0.01,
            is_motion_param=True,
            is_lighting_param=True
        )
        
        self.create_parameter_control(
            motion_frame, camera,
            "brightness_threshold", "Brightness",
            1, 100, motion_params.get("brightness_threshold", 35),
            1,
            is_motion_param=True,
            is_lighting_param=True
        )

    def migrate_legacy_config(self, camera):
        """
        Migrate legacy configuration to day/night settings format.
        This is called when day/night settings don't exist.
        
        Args:
            camera (str): Name of the camera to migrate settings for
        """
        try:
            camera_config = self.config.get(camera, {})
            
            # Skip if day and night settings already exist
            if "day_settings" in camera_config and "night_settings" in camera_config:
                return
                
            # Create day settings from existing config
            day_settings = {}
            night_settings = {}
            
            # List of parameters to migrate
            params_to_migrate = [
                "threshold_percentage",
                "luminance_threshold", 
                "owl_confidence_threshold",
                "lighting_thresholds",
                "motion_detection"
            ]
            
            # Copy existing parameters to day settings
            for param in params_to_migrate:
                if param in camera_config:
                    day_settings[param] = camera_config[param]
                    
            # Create night settings with slightly adjusted values
            night_settings = json.loads(json.dumps(day_settings))  # Deep copy
            
            # Adjust night settings for better infrared detection
            if "threshold_percentage" in night_settings:
                night_settings["threshold_percentage"] = min(night_settings["threshold_percentage"] * 1.5, 1.0)
                
            if "luminance_threshold" in night_settings:
                night_settings["luminance_threshold"] = max(night_settings["luminance_threshold"] * 0.8, 5)
                
            if "owl_confidence_threshold" in night_settings:
                night_settings["owl_confidence_threshold"] = min(night_settings["owl_confidence_threshold"] * 1.1, 95.0)
                
            if "motion_detection" in night_settings:
                # Adjust motion detection parameters for night
                if "min_circularity" in night_settings["motion_detection"]:
                    night_settings["motion_detection"]["min_circularity"] = min(
                        night_settings["motion_detection"]["min_circularity"] + 0.1, 
                        0.9
                    )
                    
                if "min_area_ratio" in night_settings["motion_detection"]:
                    night_settings["motion_detection"]["min_area_ratio"] = min(
                        night_settings["motion_detection"]["min_area_ratio"] * 1.2, 
                        0.5
                    )
                    
                if "brightness_threshold" in night_settings["motion_detection"]:
                    night_settings["motion_detection"]["brightness_threshold"] = max(
                        night_settings["motion_detection"]["brightness_threshold"] * 0.7, 
                        10
                    )
            
            # Set the day and night settings in the config
            camera_config["day_settings"] = day_settings
            camera_config["night_settings"] = night_settings
            
            # Update the config
            self.config[camera] = camera_config
            
            self.logger.info(f"Migrated legacy configuration to day/night settings for {camera}")
            
        except Exception as e:
            self.logger.error(f"Error migrating legacy config for {camera}: {e}")

    def create_parameter_control(self, parent, camera, param_name, label_text, 
                               min_val, max_val, default_val, resolution,
                               is_motion_param=False, is_integer=False, is_lighting_param=False):
        """Create a labeled scale control for a parameter"""
        frame = ttk.Frame(parent)
        frame.pack(fill="x", padx=5, pady=2)
        
        # Create label
        ttk.Label(frame, text=label_text).pack(side=tk.LEFT)
        
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
        
        # Create value entry
        entry = ttk.Entry(frame, width=8)
        entry.pack(side=tk.LEFT)
        entry.insert(0, str(int(default_val) if is_integer else default_val))
        
        # Get current lighting mode
        lighting_mode = self.lighting_mode.get()
        settings_key = f"{lighting_mode}_settings"
        
        # Store original value in appropriate place
        if camera not in self.original_values:
            self.original_values[camera] = {}
            
        if settings_key not in self.original_values[camera]:
            self.original_values[camera][settings_key] = {}
            
        if is_motion_param:
            if "motion_detection" not in self.original_values[camera][settings_key]:
                self.original_values[camera][settings_key]["motion_detection"] = {}
            self.original_values[camera][settings_key]["motion_detection"][param_name] = default_val
        else:
            self.original_values[camera][settings_key][param_name] = default_val
        
        # Update functions
        def update_entry(*args):
            value = var.get()
            if is_integer:
                value = int(value)
            entry.delete(0, tk.END)
            entry.insert(0, f"{value}")
            self.update_config(camera, param_name, value, is_motion_param, is_lighting_param)
            
        def update_scale(event):
            try:
                value = float(entry.get())
                if is_integer:
                    value = int(value)
                if min_val <= value <= max_val:
                    var.set(value)
                    self.update_config(camera, param_name, value, is_motion_param, is_lighting_param)
            except ValueError:
                entry.delete(0, tk.END)
                entry.insert(0, f"{int(var.get()) if is_integer else var.get():.2f}")
        
        # Bind updates
        var.trace_add("write", update_entry)
        entry.bind('<Return>', update_scale)
        entry.bind('<FocusOut>', update_scale)

    def update_config(self, camera, param_name, value, is_motion_param, is_lighting_param=False):
        """Update configuration with new parameter value"""
        try:
            # Get lighting settings key if using day/night settings
            lighting_mode = self.lighting_mode.get()
            settings_key = f"{lighting_mode}_settings"
            
            if is_lighting_param:
                # Make sure the camera and settings key exist
                if camera not in self.config:
                    self.config[camera] = {}
                if settings_key not in self.config[camera]:
                    self.config[camera][settings_key] = {}
                    
                if is_motion_param:
                    if "motion_detection" not in self.config[camera][settings_key]:
                        self.config[camera][settings_key]["motion_detection"] = {}
                    self.config[camera][settings_key]["motion_detection"][param_name] = value
                else:
                    self.config[camera][settings_key][param_name] = value
            else:
                # Non-lighting parameters go at the root level
                if camera not in self.config:
                    self.config[camera] = {}
                    
                if is_motion_param:
                    if "motion_detection" not in self.config[camera]:
                        self.config[camera]["motion_detection"] = {}
                    self.config[camera]["motion_detection"][param_name] = value
                else:
                    self.config[camera][param_name] = value
                    
        except Exception as e:
            self.logger.error(f"Error updating config: {e}")

    def create_control_buttons(self):
        """Create save and reset buttons"""
        button_frame = ttk.Frame(self.settings_frame)
        button_frame.pack(fill="x", padx=5, pady=5)
        
        # Save button
        ttk.Button(
            button_frame,
            text="Save Changes",
            command=self.save_config
        ).pack(side=tk.LEFT, padx=5)
        
        # Reset button
        ttk.Button(
            button_frame,
            text="Reset to Default",
            command=self.reset_to_default
        ).pack(side=tk.LEFT, padx=5)
        
        # Apply to running system button
        ttk.Button(
            button_frame,
            text="Apply Now",
            command=self.apply_to_running_system
        ).pack(side=tk.LEFT, padx=5)

    def reset_to_default(self):
        """Reset all parameters to their original values"""
        try:
            # Get current lighting mode
            lighting_mode = self.lighting_mode.get()
            settings_key = f"{lighting_mode}_settings"
            
            # Check if we have original values for the current lighting mode
            for camera, values in self.original_values.items():
                if settings_key in values:
                    # Reset lighting-specific settings
                    if settings_key not in self.config[camera]:
                        self.config[camera][settings_key] = {}
                        
                    for param, value in values[settings_key].items():
                        if param == "motion_detection":
                            if "motion_detection" not in self.config[camera][settings_key]:
                                self.config[camera][settings_key]["motion_detection"] = {}
                                
                            for motion_param, motion_value in value.items():
                                self.config[camera][settings_key]["motion_detection"][motion_param] = motion_value
                        else:
                            self.config[camera][settings_key][param] = value
            
            # Reload interface for current lighting mode
            self.notebook.destroy()
            self.create_settings_interface()
            
            self.logger.info(f"Settings reset to original values for {lighting_mode} mode")
            messagebox.showinfo("Reset", f"Settings have been reset to original values for {lighting_mode} mode")
            
        except Exception as e:
            self.logger.error(f"Error resetting settings: {e}")
            messagebox.showerror("Error", f"Failed to reset settings: {e}")
            
    def apply_to_running_system(self):
        """Apply current settings to the running system without restarting"""
        try:
            # First save the configuration
            self.save_config()
            
            # Try to communicate with the running system
            try:
                # Import motion_workflow here to avoid circular imports
                from scripts.motion_workflow import update_thresholds
                
                # Extract confidence thresholds for current lighting mode
                lighting_mode = self.lighting_mode.get()
                settings_key = f"{lighting_mode}_settings"
                
                thresholds = {}
                for camera, config in self.config.items():
                    if settings_key in config and "owl_confidence_threshold" in config[settings_key]:
                        thresholds[camera] = config[settings_key]["owl_confidence_threshold"]
                
                # Update running system
                result = update_thresholds(self.config, thresholds)
                
                if result:
                    self.logger.info(f"Settings applied to running system for {lighting_mode} mode")
                    messagebox.showinfo("Success", f"Settings applied to running system for {lighting_mode} mode")
                else:
                    messagebox.showwarning("Warning", "Could not apply all settings to running system")
                    
            except ImportError:
                # If motion_workflow isn't available, inform the user
                self.logger.warning("Could not import motion_workflow module")
                messagebox.showinfo("Info", "Changes will take effect after restarting motion detection")
                
        except Exception as e:
            self.logger.error(f"Error applying settings: {e}")
            messagebox.showerror("Error", f"Failed to apply settings: {e}")

    def get_confidence_thresholds(self):
        """Get all configured confidence thresholds for the current lighting mode"""
        try:
            # Get current lighting mode
            lighting_mode = self.lighting_mode.get()
            settings_key = f"{lighting_mode}_settings"
            
            thresholds = {}
            for camera, config in self.config.items():
                if settings_key in config and "owl_confidence_threshold" in config[settings_key]:
                    thresholds[camera] = config[settings_key]["owl_confidence_threshold"]
            return thresholds
        except Exception as e:
            self.logger.error(f"Error getting confidence thresholds: {e}")
            return {}

if __name__ == "__main__":
    # Test the interface
    root = tk.Tk()
    root.title("Motion Detection Settings Test")
    
    app = MotionDetectionSettings(root)
    
    root.mainloop()