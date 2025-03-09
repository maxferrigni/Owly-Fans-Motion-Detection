import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os
from utilities.logging_utils import get_logger
from utilities.constants import get_base_image_path, BASE_IMAGE_FILENAMES

logger = get_logger()

class SimpleImageViewer(ttk.LabelFrame):
    """A simple panel to display images with improved error handling and base image support"""
    def __init__(self, parent, title="Image Viewer"):
        super().__init__(parent, text=title)
        
        # Keep reference to loaded images
        self.image_references = {}
        
        # Track last update time for change detection
        self.last_update_time = 0
        
        # Create the UI
        self.create_interface()
        
    def create_interface(self):
        """Create the image display interface"""
        self.frame = ttk.Frame(self)
        self.frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create image label
        self.image_label = ttk.Label(self.frame, text="No image loaded")
        self.image_label.pack(pady=5)
        
    def load_image(self, image_path, max_size=(200, 150)):
        """Load and display an image"""
        if not os.path.exists(image_path):
            self.image_label.config(text=f"Image not found:\n{os.path.basename(image_path)}", image="")
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
            
            # Update label
            self.image_label.config(image=photo, text="")
            
            # Keep reference to prevent garbage collection
            self.image_references[image_path] = photo
            
            logger.debug(f"Loaded image: {image_path}")
            return True
        except Exception as e:
            logger.error(f"Error loading image {image_path}: {e}")
            self.image_label.config(text=f"Error loading image", image="")
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
            logger.error(f"Error loading base image for {camera_name} ({lighting_condition}): {e}")
            self.image_label.config(text=f"Error loading base image", image="")
            return False
        
    def clear(self):
        """Clear the displayed image"""
        self.image_label.config(image="", text="No image loaded")
        
        # Clear references to allow garbage collection
        self.image_references.clear()

# Test code (only runs when script is executed directly)
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Image Viewer Test")
    
    # Create a test viewer
    viewer = SimpleImageViewer(root, "Test Viewer")
    viewer.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Create test buttons
    button_frame = ttk.Frame(root)
    button_frame.pack(pady=10)
    
    def load_test_image():
        # Try to load a test image
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select an image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png")]
        )
        if path:
            viewer.load_image(path, max_size=(300, 200))
    
    ttk.Button(
        button_frame,
        text="Load Image",
        command=load_test_image
    ).pack(side=tk.LEFT, padx=5)
    
    ttk.Button(
        button_frame,
        text="Clear",
        command=viewer.clear
    ).pack(side=tk.LEFT, padx=5)
    
    # Test base image loading
    def load_test_base():
        from utilities.constants import CAMERA_MAPPINGS
        camera_name = list(CAMERA_MAPPINGS.keys())[0]  # Get first camera
        viewer.load_base_image(camera_name, 'day', max_size=(300, 200))
    
    ttk.Button(
        button_frame,
        text="Test Base Image",
        command=load_test_base
    ).pack(side=tk.LEFT, padx=5)
    
    root.mainloop()