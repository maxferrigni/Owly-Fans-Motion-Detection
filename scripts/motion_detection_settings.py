# File: motion_detection_settings.py
# Purpose: Simplified GUI controls for motion detection parameters
# 
# March 8, 2025 Update - Version 1.5.4
# - Completely redesigned UI with a simpler linear layout
# - Added scrollable container for all settings
# - Removed nested sections and subsections
# - Standardized all control elements
# - Enhanced error handling

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
        
        # Load current configuration
        self.config = self.load_config()
        
        # Track original values for changes
        self.original_values = {}
        
        # Store slider variables by camera and parameter
        self.slider_vars = {}
        
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
                
            # Log success messages
            self.logger.info("Configuration saved successfully")
            messagebox.showinfo("Success", "Settings saved successfully")
            
            return True
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")
            messagebox.showerror("Error", f"Failed to save configuration: {e}")
            return False

    def create_settings_interface(self):
        """Create simplified settings interface with a scrollable container"""
        try:
            # Create main controls container
            self.main_frame = ttk.Frame(self.parent_frame)
            self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Add title
            title_label = ttk.Label(
                self.main_frame,
                text="Motion Detection Settings",
                font=("Arial", 12, "bold")
            )
            title_label.pack(pady=(0, 10))
            
            # Introduction text
            intro_text = (
                "Adjust the settings below to fine-tune motion detection for each camera. "
                "Changes will take effect the next time motion detection is started."
            )
            
            intro_label = ttk.Label(
                self.main_frame,
                text=intro_text,
                wraplength=500,
                justify="left"
            )
            intro_label.pack(fill="x", pady=(0, 10))
            
            # Create one section per camera
            for camera_name in sorted(self.config.keys()):
                self.create_camera_section(camera_name)
            
            # Add save and reset buttons at the bottom
            self.create_action_buttons()
            
        except Exception as e:
            self.logger.error(f"Error creating settings interface: {e}")
            error_label = ttk.Label(
                self.parent_frame,
                text=f"Error creating settings: {str(e)}",
                foreground="red",
                wraplength=500
            )
            error_label.pack(pady=20)

    def create_camera_section(self, camera_name):
        """Create a section for each camera's settings"""
        try:
            # Get alert type for this camera
            alert_type = CAMERA_MAPPINGS.get(camera_name, "Unknown")
            
            # Create camera section with header
            camera_frame = ttk.LabelFrame(
                self.main_frame, 
                text=f"{camera_name} ({alert_type})"
            )
            camera_frame.pack(fill="x", pady=10, padx=5, anchor="nw")
            
            # Initialize variables for this camera
            self.slider_vars[camera_name] = {}
            
            # Get camera configuration
            camera_config = self.config.get(camera_name, {})
            
            # Store original values
            self.original_values[camera_name] = {}
            for key, value in camera_config.items():
                if isinstance(value, dict):
                    self.original_values[camera_name][key] = {}
                    for subkey, subvalue in value.items():
                        self.original_values[camera_name][key][subkey] = subvalue
                else:
                    self.original_values[camera_name][key] = value
            
            # Create linear layout of settings
            settings_list = ttk.Frame(camera_frame)
            settings_list.pack(fill="x", padx=10, pady=5)
            
            # Add main settings
            self.add_slider(
                settings_list, camera_name,
                "threshold_percentage", "Motion Threshold %",
                0.01, 0.5, camera_config.get("threshold_percentage", 0.05),
                0.01, "Higher values require more motion to trigger detection"
            )
            
            self.add_slider(
                settings_list, camera_name,
                "luminance_threshold", "Luminance Threshold",
                5, 100, camera_config.get("luminance_threshold", 40),
                1, "Higher values require brighter changes to trigger detection"
            )
            
            self.add_slider(
                settings_list, camera_name,
                "owl_confidence_threshold", "Owl Confidence %",
                30.0, 95.0, camera_config.get("owl_confidence_threshold", 60.0),
                5.0, "Higher values reduce false alarms but may miss actual owls"
            )
            
            self.add_slider(
                settings_list, camera_name,
                "consecutive_frames_threshold", "Consecutive Frames",
                1, 5, camera_config.get("consecutive_frames_threshold", 2),
                1, "Number of consecutive frames with detection before alert", True
            )
            
            # Get motion detection parameters
            motion_params = camera_config.get("motion_detection", {})
            
            # Add separator
            ttk.Separator(settings_list, orient="horizontal").pack(fill="x", pady=10)
            
            # Label for advanced settings
            ttk.Label(
                settings_list,
                text="Shape Detection Parameters:",
                font=("Arial", 10, "italic")
            ).pack(anchor="w", pady=(0, 5))
            
            # Add motion detection parameters
            self.add_slider(
                settings_list, camera_name,
                "motion_detection.min_circularity", "Circularity",
                0.1, 1.0, motion_params.get("min_circularity", 0.5),
                0.1, "How circular the detected shape must be (0.0-1.0)"
            )
            
            self.add_slider(
                settings_list, camera_name,
                "motion_detection.min_aspect_ratio", "Min Aspect Ratio",
                0.1, 2.0, motion_params.get("min_aspect_ratio", 0.5),
                0.1, "Minimum width/height ratio of detected shapes"
            )
            
            self.add_slider(
                settings_list, camera_name,
                "motion_detection.max_aspect_ratio", "Max Aspect Ratio",
                1.0, 3.0, motion_params.get("max_aspect_ratio", 2.0),
                0.1, "Maximum width/height ratio of detected shapes"
            )
            
            self.add_slider(
                settings_list, camera_name,
                "motion_detection.min_area_ratio", "Min Area Ratio",
                0.01, 0.5, motion_params.get("min_area_ratio", 0.2),
                0.01, "Minimum size relative to frame"
            )
            
            self.add_slider(
                settings_list, camera_name,
                "motion_detection.brightness_threshold", "Brightness",
                5, 100, motion_params.get("brightness_threshold", 35),
                5, "Minimum brightness difference to detect motion"
            )
            
        except Exception as e:
            self.logger.error(f"Error creating camera section {camera_name}: {e}")
            # Continue with other cameras even if one fails

    def add_slider(self, parent, camera_name, param_name, label_text, 
                  min_val, max_val, default_val, resolution, 
                  tooltip_text=None, is_integer=False):
        """Add a slider control with standardized layout"""
        try:
            # Create frame for this setting
            frame = ttk.Frame(parent)
            frame.pack(fill="x", pady=5, anchor="w")
            
            # First row: Label and value display
            row1 = ttk.Frame(frame)
            row1.pack(fill="x")
            
            # Setting label with fixed width for alignment
            label = ttk.Label(row1, text=label_text, width=20, anchor="w")
            label.pack(side=tk.LEFT)
            
            # Value display
            value_var = tk.StringVar()
            if is_integer:
                value_var.set(f"{int(default_val)}")
            else:
                value_var.set(f"{default_val:.2f}")
                
            value_label = ttk.Label(row1, textvariable=value_var, width=8)
            value_label.pack(side=tk.LEFT)
            
            # Second row: Slider
            row2 = ttk.Frame(frame)
            row2.pack(fill="x", pady=(0, 5))
            
            # Create slider variable
            slider_var = tk.DoubleVar(value=default_val)
            
            # Store in dictionary for later access
            param_parts = param_name.split('.')
            if len(param_parts) > 1:
                # Nested parameter (e.g., motion_detection.min_circularity)
                category, param = param_parts
                if category not in self.slider_vars[camera_name]:
                    self.slider_vars[camera_name][category] = {}
                self.slider_vars[camera_name][category][param] = slider_var
            else:
                # Top-level parameter
                self.slider_vars[camera_name][param_name] = slider_var
            
            # Create and configure slider
            slider = ttk.Scale(
                row2,
                from_=min_val,
                to=max_val,
                variable=slider_var,
                orient="horizontal",
                length=300
            )
            slider.pack(fill="x", padx=(20, 5))
            
            # Update function for slider and value display
            def update_value(*args):
                new_value = slider_var.get()
                if is_integer:
                    new_value = int(new_value)
                    value_var.set(f"{new_value}")
                else:
                    value_var.set(f"{new_value:.2f}")
                
                # Update configuration
                self.update_config_value(camera_name, param_name, new_value)
            
            # Bind to value changes
            slider_var.trace_add("write", update_value)
            
            # Add tooltip if provided
            if tooltip_text:
                ttk.Label(
                    frame, 
                    text=tooltip_text,
                    font=("Arial", 8),
                    foreground="gray"
                ).pack(padx=(20, 0), anchor="w")
                
        except Exception as e:
            self.logger.error(f"Error adding slider for {camera_name}.{param_name}: {e}")
            # Create an error label instead of the control
            error_label = ttk.Label(
                parent,
                text=f"Error creating {label_text} control: {str(e)}",
                foreground="red"
            )
            error_label.pack(fill="x", pady=5)

    def update_config_value(self, camera_name, param_name, value):
        """Update the configuration with a new parameter value"""
        try:
            # Handle nested parameters
            param_parts = param_name.split('.')
            if len(param_parts) > 1:
                # Nested parameter (e.g., motion_detection.min_circularity)
                category, param = param_parts
                
                # Ensure the category exists in the config
                if category not in self.config[camera_name]:
                    self.config[camera_name][category] = {}
                    
                # Update the value
                self.config[camera_name][category][param] = value
            else:
                # Top-level parameter
                self.config[camera_name][param_name] = value
                
        except Exception as e:
            self.logger.error(f"Error updating config for {camera_name}.{param_name}: {e}")

    def create_action_buttons(self):
        """Create save and reset buttons"""
        try:
            buttons_frame = ttk.Frame(self.main_frame)
            buttons_frame.pack(fill="x", pady=15)
            
            # Save button
            save_button = ttk.Button(
                buttons_frame,
                text="Save All Changes",
                command=self.save_config,
                width=20
            )
            save_button.pack(side=tk.LEFT, padx=5)
            
            # Reset button
            reset_button = ttk.Button(
                buttons_frame,
                text="Reset to Default",
                command=self.reset_to_default,
                width=20
            )
            reset_button.pack(side=tk.LEFT, padx=5)
            
        except Exception as e:
            self.logger.error(f"Error creating action buttons: {e}")

    def reset_to_default(self):
        """Reset all parameters to their original values"""
        try:
            # Confirm with user
            confirm = messagebox.askyesno(
                "Confirm Reset",
                "Are you sure you want to reset all settings to their original values?"
            )
            
            if not confirm:
                return
                
            # Reset each parameter
            for camera_name, camera_values in self.original_values.items():
                for param_name, value in camera_values.items():
                    if isinstance(value, dict):
                        # Nested parameters (e.g., motion_detection)
                        for subparam, subvalue in value.items():
                            # Update slider if it exists
                            if camera_name in self.slider_vars and param_name in self.slider_vars[camera_name]:
                                if subparam in self.slider_vars[camera_name][param_name]:
                                    self.slider_vars[camera_name][param_name][subparam].set(subvalue)
                            
                            # Always update config
                            if camera_name in self.config and param_name in self.config[camera_name]:
                                self.config[camera_name][param_name][subparam] = subvalue
                    else:
                        # Top-level parameters
                        # Update slider if it exists
                        if camera_name in self.slider_vars and param_name in self.slider_vars[camera_name]:
                            self.slider_vars[camera_name][param_name].set(value)
                        
                        # Always update config
                        if camera_name in self.config:
                            self.config[camera_name][param_name] = value
            
            self.logger.info("Settings reset to original values")
            messagebox.showinfo("Reset", "Settings have been reset to original values")
            
        except Exception as e:
            self.logger.error(f"Error resetting settings: {e}")
            messagebox.showerror("Error", f"Failed to reset settings: {e}")

    def apply_to_running_system(self):
        """Apply settings to running system - kept for backwards compatibility"""
        try:
            # First save the configuration
            if self.save_config():
                # Try to communicate with the running system
                try:
                    # Import motion_workflow here to avoid circular imports
                    from motion_workflow import update_thresholds
                    
                    # Extract confidence thresholds
                    thresholds = {}
                    for camera_name, camera_vars in self.slider_vars.items():
                        if "owl_confidence_threshold" in camera_vars:
                            thresholds[camera_name] = camera_vars["owl_confidence_threshold"].get()
                    
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
            messagebox.showerror("Error", f"Failed to apply settings: {e}")


if __name__ == "__main__":
    # Test the interface
    root = tk.Tk()
    root.title("Motion Detection Settings Test")
    root.geometry("800x600")
    
    # Create scrollable container
    canvas = tk.Canvas(root)
    scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    # Create settings interface
    app = MotionDetectionSettings(scrollable_frame)
    
    # Configure scrolling with the mouse wheel
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    root.mainloop()