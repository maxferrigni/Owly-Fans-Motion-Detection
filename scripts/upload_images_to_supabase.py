# File: upload_images_to_supabase.py
# Purpose: Handle uploading motion detection images to Supabase Storage

import os
import datetime
import mimetypes
import supabase
from dotenv import load_dotenv

# Import utilities
from utilities.logging_utils import get_logger
from utilities.constants import SNAPSHOTS_DIR

# Initialize logger
logger = get_logger()

# Load environment variables
load_dotenv()

# Retrieve Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")

# Validate credentials
if not all([SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET]):
    error_msg = "Supabase credentials are missing. Check the .env file."
    logger.error(error_msg)
    raise ValueError(error_msg)

# Initialize Supabase client
try:
    supabase_client = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase storage client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {e}")
    raise

def upload_image_to_supabase(local_image_path, detection_type):
    """
    Upload a motion detection image to Supabase Storage.
    
    Args:
        local_image_path (str): Path to the image stored locally
        detection_type (str): Type of detection ("owl_in_box", "owl_on_box", "owl_in_area")
    
    Returns:
        str or None: Public URL of the uploaded image or None if failed
    """
    try:
        if not os.path.exists(local_image_path):
            logger.error(f"Image file not found: {local_image_path}")
            return None

        # Generate unique filename using timestamp
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"{detection_type}_{timestamp}.jpg"
        storage_path = f"{detection_type}/{filename}"

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(local_image_path)
        if not mime_type:
            mime_type = "image/jpeg"
        
        logger.info(f"Uploading {detection_type} image: {filename}")
        logger.debug(f"Local path: {local_image_path}")
        logger.debug(f"Storage path: {storage_path}")

        # Upload image to Supabase Storage
        with open(local_image_path, "rb") as file:
            response = supabase_client.storage.from_(SUPABASE_BUCKET).upload(
                path=storage_path,
                file=file,
                file_options={"content-type": mime_type}
            )

        # Generate and return public URL
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{storage_path}"
        logger.info(f"Image successfully uploaded: {public_url}")
        
        # Clean up local file if upload successful
        try:
            os.remove(local_image_path)
            logger.debug(f"Cleaned up local file: {local_image_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up local file {local_image_path}: {e}")

        return public_url

    except Exception as e:
        logger.error(f"Error uploading image to Supabase: {e}")
        return None

def upload_pending_images():
    """
    Upload any pending images in the snapshots directory to Supabase.
    """
    try:
        logger.info("Checking for pending images...")
        for detection_type in ["owl_in_box", "owl_on_box", "owl_in_area"]:
            snapshot_dir = os.path.join(SNAPSHOTS_DIR, detection_type)
            if not os.path.exists(snapshot_dir):
                continue

            for filename in os.listdir(snapshot_dir):
                if filename.endswith(('.jpg', '.jpeg', '.png')):
                    local_path = os.path.join(snapshot_dir, filename)
                    logger.info(f"Found pending image: {local_path}")
                    upload_image_to_supabase(local_path, detection_type)

    except Exception as e:
        logger.error(f"Error processing pending images: {e}")

# Example usage and testing
if __name__ == "__main__":
    try:
        logger.info("Starting image upload test...")
        
        # Test image upload
        test_image_path = os.path.join(SNAPSHOTS_DIR, "owl_in_box", "test_image.jpg")
        if os.path.exists(test_image_path):
            uploaded_url = upload_image_to_supabase(test_image_path, "owl_in_box")
            if uploaded_url:
                logger.info("Test upload successful")
            else:
                logger.error("Test upload failed")
        else:
            logger.warning(f"Test image not found: {test_image_path}")

        # Check for any pending uploads
        upload_pending_images()
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise