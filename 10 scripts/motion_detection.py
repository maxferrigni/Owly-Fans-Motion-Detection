import os
import json
from datetime import datetime, time
from PIL import Image, ImageChops, ImageDraw
import pyautogui
import time as sleep_time
import pytz
from alert_email import send_email_alert  # Import the email alert function

# Define Pacific Time Zone
PACIFIC_TIME = pytz.timezone("America/Los_Angeles")

# Define the allowed time range in Pacific Time
START_TIME = time(17, 0)  # 5:00 PM Pacific
END_TIME = time(5, 0)     # 5:00 AM Pacific (next day)

# Paths
INPUT_BASE_PATH = "/Users/maxferrigni/Insync/maxferrigni@gmail.com/Google Drive/01 - Owl Box/60 IT/20 Motion Detection/20 Input Files/60 Camera Base Images"
OUTPUT_PATH = "/Users/maxferrigni/Insync/maxferrigni@gmail.com/Google Drive/01 - Owl Box/60 IT/20 Motion Detection/30 Output Files"
SNAPSHOT_PATH = OUTPUT_PATH  # Redirect snapshots to the new output folder
LOG_PATH = os.path.join(OUTPUT_PATH, "logs")
DIFF_PATH = os.path.join(OUTPUT_PATH, "differences")

# Mapping of camera names to base image filenames
BASE_IMAGES = {
    "Upper Patio": os.path.join(INPUT_BASE_PATH, "10 Upper Patio Base.jpg"),
    "Bindy Patio": os.path.join(INPUT_BASE_PATH, "20 Bindy Patio Base.jpg"),
    "Wyze Camera": os.path.join(INPUT_BASE_PATH, "30 Wyze Camera Base.jpg"),
}

# Load camera configurations from the JSON file
def load_config():
    config_path = "./20 configs/config.json"
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, 'r') as f:
        return json.load(f)

# Load configuration settings
CAMERA_CONFIGS = load_config()

# Alert tracking to enforce 30-minute cooldown
last_alert_time = {"Owl In Box": None, "Owl On Box": None, "Owl In Area": None}

# Check if the current time is within the allowed range
def is_within_allowed_hours():
    now = datetime.now(PACIFIC_TIME).time()
    if START_TIME <= now or now <= END_TIME:
        return True
    return False

# Load base image
def load_base_image(camera_name):
    base_image_path = BASE_IMAGES.get(camera_name)
    if not base_image_path or not os.path.exists(base_image_path):
        raise FileNotFoundError(f"Base image for {camera_name} not found: {base_image_path}")
    return Image.open(base_image_path)

# Capture an image from the screen based on the ROI
def capture_real_image(roi):
    x, y, width, height = roi
    width = abs(width - x)
    height = abs(height - y)
    print(f"Capturing screenshot: x={x}, y={y}, width={width}, height={height}")
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid ROI dimensions: {roi}")
    return pyautogui.screenshot(region=(x, y, width, height))

# Save snapshot images
def save_snapshot(image, camera_name, snapshot_name):
    camera_folder = os.path.join(SNAPSHOT_PATH, camera_name)
    os.makedirs(camera_folder, exist_ok=True)
    if image.mode == "RGBA":
        image = image.convert("RGB")
    image_path = os.path.join(camera_folder, snapshot_name)
    image.save(image_path)
    return image_path

# Calculate luminance
def calculate_luminance(pixel):
    r, g, b = pixel[:3]
    return 0.2989 * r + 0.5870 * g + 0.1140 * b

# Detect motion
def detect_motion(image1, image2, threshold_percentage, luminance_threshold):
    diff = ImageChops.difference(image1, image2)
    diff_data = diff.getdata()
    total_pixels = len(diff_data)
    significant_pixels = 0
    significant_brightness_changes = 0
    for pixel1, pixel2 in zip(image1.getdata(), image2.getdata()):
        luminance1 = calculate_luminance(pixel1)
        luminance2 = calculate_luminance(pixel2)
        if luminance2 > luminance1 and abs(luminance1 - luminance2) > luminance_threshold:
            significant_brightness_changes += 1
        pixel_diff = sum(abs(a - b) for a, b in zip(pixel1, pixel2))
        if pixel_diff > 50:
            significant_pixels += 1
    threshold_pixels = total_pixels * threshold_percentage
    return diff, (significant_pixels > threshold_pixels) and (significant_brightness_changes > threshold_pixels)

# Highlight differences in the third image
def create_diff_image(image1, image2, luminance_threshold):
    diff = ImageChops.difference(image1, image2).convert("L")
    diff_image = image2.copy()
    draw = ImageDraw.Draw(diff_image)
    threshold = 30
    for x in range(diff.width):
        for y in range(diff.height):
            if diff.getpixel((x, y)) > threshold:
                draw.rectangle([x, y, x + 1, y + 1], fill="red")
    return diff_image

# Log motion event or status
def log_event(camera_name, status):
    # Ensure daily log folder exists
    daily_log_folder = os.path.join(LOG_PATH, "motion_logs")
    os.makedirs(daily_log_folder, exist_ok=True)
    
    # Create or append to the daily log file
    date_str = datetime.now(PACIFIC_TIME).strftime("%Y-%m-%d")
    log_file = os.path.join(daily_log_folder, f"motion_log_{date_str}.txt")
    
    # Append the status with timestamp
    timestamp = datetime.now(PACIFIC_TIME).strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as log:
        log.write(f"{timestamp} | Camera: {camera_name} | Status: {status}\n")

# Main motion detection function
def motion_detection():
    print("Starting motion detection...")
    while True:
        if not is_within_allowed_hours():
            print("Outside of allowed hours. Skipping motion detection...")
            sleep_time.sleep(60)
            continue
        
        # Iterate through each camera and log its status
        for camera_name, config in CAMERA_CONFIGS.items():
            if config["roi"] is None:
                print(f"Skipping {camera_name}...")
                log_event(camera_name, "No ROI Defined")
                continue
            
            print(f"Checking {camera_name}...")
            roi = config["roi"]
            threshold_percentage = config["threshold_percentage"]
            luminance_threshold = config["luminance_threshold"]
            alert_type = config["alert_type"]
            
            # Capture and save new image
            new_image = capture_real_image(roi)
            save_snapshot(new_image, camera_name, "new_snapshot.jpg")
            
            # Load base image
            base_image = load_base_image(camera_name)
            
            # Detect motion
            diff, motion_detected = detect_motion(base_image, new_image, threshold_percentage, luminance_threshold)
            
            if motion_detected:
                # Handle alert and logging
                diff_image = create_diff_image(base_image, new_image, luminance_threshold)
                composite_image_path = save_snapshot(diff_image, camera_name, "difference_image.jpg")
                log_event(camera_name, alert_type)
                send_email_alert(camera_name, alert_type)
                last_alert_time[alert_type] = datetime.now()
                print(f"{alert_type} ALERT! Email sent and difference image saved.")
            else:
                # Log "No Owl" if no motion detected
                log_event(camera_name, "No Owl")
                print(f"No significant motion detected for {camera_name}.")
        
        # Sleep for 1 minute before next check
        sleep_time.sleep(60)

if __name__ == "__main__":
    motion_detection()
