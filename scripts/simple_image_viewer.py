import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os
from utilities.logging_utils import get_logger

logger = get_logger()

class SimpleImageViewer(ttk.LabelFrame):
    """A simple panel to display images"""
    def __init__(self, parent, title="Image Viewer"):
        super().__init__(parent, text=title)
        
        # Keep reference to loaded images
        self.image_references = {}
        
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
            self.image_label.config(text="Image not found", image="")
            return False
            
        # Load the image
        try:
            img = Image.open(image_path)
            
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
    
    root.mainloop()