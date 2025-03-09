import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os
from utilities.logging_utils import get_logger
from utilities.constants import get_base_image_path

logger = get_logger()

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
            
            logger.debug(f"Loaded image: {image_path}")
            return True
        except Exception as e:
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
            logger.error(f"Error loading base image for {camera_name} ({lighting_condition}): {e}")
            return False
        
    def clear(self):
        """Clear the displayed image"""
        self.image_label.config(image="")
        
        # Clear references to allow garbage collection
        self.image_references.clear()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Simple Image Viewer Test")
    
    # Create a test viewer
    viewer = SimpleImageViewer(root, "Test Base Image")
    viewer.pack(padx=10, pady=10)
    
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
    
    root.mainloop()