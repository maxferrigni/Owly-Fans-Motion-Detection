# File: upload_images_to_supabase.py
# Purpose:
# This script handles uploading motion detection images to Supabase Storage.
# It ensures images are stored in the correct Supabase bucket before logging and alerting.
# Features:
# - Connects to Supabase using environment variables for security.
# - Uploads images to the appropriate folder in the `owl_detections` bucket.
# - Returns a public URL for each uploaded image.
# - Ensures that images are available before alerts are triggered.
# Typical Usage:
# This script should be called whenever an owl is detected and an image needs to be stored.
# Example:
# `python upload_images_to_supabase.py`

import os
import datetime
import mimetypes
import supabase
from dotenv import load_dotenv

# Load environment variables (for security, API keys should be stored in .env file)
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials are missing. Ensure SUPABASE_URL and SUPABASE_KEY are set.")

# Initialize Supabase client
supabase_client = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)

# Define the main storage bucket
SUPABASE_BUCKET = "owl_detections"

def upload_image_to_supabase(local_image_path, detection_type):
    """
    Uploads a motion detection image to Supabase Storage.
    :param local_image_path: Path to the image stored locally.
    :param detection_type: Type of detection ("owl_in_box", "owl_on_box", "owl_in_area").
    :return: Public URL of the uploaded image.
    """
    if not os.path.exists(local_image_path):
        raise FileNotFoundError(f"Image file not found: {local_image_path}")

    # Generate a unique filename using timestamp
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = f"{detection_type}_{timestamp}.jpg"
    
    # Define the storage path in Supabase
    storage_path = f"{detection_type}/{filename}"

    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(local_image_path)
    if not mime_type:
        mime_type = "image/jpeg"  # Default to JPEG

    try:
        # Upload the image to Supabase Storage
        with open(local_image_path, "rb") as file:
            response = supabase_client.storage.from_(SUPABASE_BUCKET).upload(
                path=storage_path,
                file=file,
                file_options={"content-type": mime_type}
            )

        # Generate public URL
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{storage_path}"
        print(f"Image successfully uploaded: {public_url}")
        return public_url

    except Exception as e:
        print(f"Error uploading image to Supabase: {e}")
        return None

# Example usage for testing
if __name__ == "__main__":
    sample_image_path = "./snapshots/owl_test.jpg"  # Replace with actual image path
    detection_category = "owl_in_box"  # Example category
    uploaded_url = upload_image_to_supabase(sample_image_path, detection_category)
    
    if uploaded_url:
        print(f"Image uploaded successfully: {uploaded_url}")
    else:
        print("Failed to upload image.")
