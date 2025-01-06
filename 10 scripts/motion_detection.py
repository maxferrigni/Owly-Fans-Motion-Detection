import os
import json
from datetime import datetime, timedelta, time
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

# Load camera configurations from the JSON file
def load_config():
    config_path = "./20 configs/config.json"  # Correct path since "20 configs" is in the same folder
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, 'r') as f:
        return json.load(f)

# Paths
SNAPSHOT_PATH = "./40 snapshots/"
LOG_PATH = "./30 logs/"
DIFF_PATH = "./30 logs/differences/"

# Load configuration settings
CAMERA_CONFIGS = load_config()

# Alert tracking to enforce 30-minute cooldown
last_alert_time = {"Owl In Box": None, "Owl On Box": None, "Owl In Area": None}

# Check if the current time is within the allowed range
def is_within_allowed_hours():
    now = datetime.now(PACIFIC_TIME).time()  # Use Pacific Time for comparison
    if START_TIME <= now or now <= END_TIME:  # Handles overnight range
        return True
    return False

# Capture an image from the screen based on the ROI
def capture_real_image(roi):
    """
    Captures a screenshot of the specified region of interest (ROI).
    Handles multiple monitors with negative x and y values.
    ROI is defined as [x, y, width, height].
    """
    x, y, width, height = roi

    # Compute effective width and height
    width = abs(width - x)
    height = abs(height - y)

    # Log the computed dimensions for debugging
    print(f"Capturing screenshot: x={x}, y={y}, width={width}, height={height}")

    # Validate width and height
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid ROI dimensions: {roi}")

    # Capture the screenshot
    screenshot = pyautogui.screenshot(region=(x, y, width, height))
    return screenshot

# Function to save snapshot images
def save_snapshot(image, camera_name, snapshot_name):
    camera_folder = os.path.join(SNAPSHOT_PATH, camera_name)
    os.makedirs(camera_folder, exist_ok=True)

    if image.mode == "RGBA":
        image = image.convert("RGB")

    image_path = os.path.join(camera_folder, snapshot_name)
    image.save(image_path)
    return image_path

# Function to calculate luminance of a pixel
def calculate_luminance(pixel):
    if len(pixel) == 4:  # RGBA
        r, g, b, a = pixel
    else:  # RGB
        r, g, b = pixel

    luminance = 0.2989 * r + 0.5870 * g + 0.1140 * b
    return luminance

# Compare images with RGB handling, considering both pixel difference and brightness change
def detect_motion(image1, image2, threshold_percentage, luminance_threshold):
    diff = ImageChops.difference(image1, image2)
    diff_data = diff.getdata()

    total_pixels = len(diff_data)
    significant_pixels = 0
    significant_brightness_changes = 0

    for pixel1, pixel2 in zip(image1.getdata(), image2.getdata()):
        if isinstance(pixel1, tuple) and isinstance(pixel2, tuple):
            luminance1 = calculate_luminance(pixel1)
            luminance2 = calculate_luminance(pixel2)

            if luminance2 > luminance1 and abs(luminance1 - luminance2) > luminance_threshold:
                significant_brightness_changes += 1

            pixel_diff = sum(abs(a - b) for a, b in zip(pixel1, pixel2))
            if pixel_diff > 50:  # Adjust this value to make it more sensitive
                significant_pixels += 1

    threshold_pixels = total_pixels * threshold_percentage

    return diff, (significant_pixels > threshold_pixels) and (significant_brightness_changes > threshold_pixels)

# Highlight the differences in the third image
def create_diff_image(image1, image2, luminance_threshold):
    diff = ImageChops.difference(image1, image2)
    diff = diff.convert("L")

    diff_image = image2.copy()
    draw = ImageDraw.Draw(diff_image)

    threshold = 30

    for x in range(diff.width):
        for y in range(diff.height):
            if diff.getpixel((x, y)) > threshold:
                draw.rectangle([x, y, x + 1, y + 1], fill="red")

    return diff_image

# Log motion event
def log_event(camera_name, event_type, composite_image_path=None):
    log_folder = os.path.join(LOG_PATH, camera_name)
    os.makedirs(log_folder, exist_ok=True)
    log_file = os.path.join(log_folder, "motion_log.txt")
    with open(log_file, "a") as log:
        log.write(f"{datetime.now()} - {event_type}")
        if composite_image_path:
            log.write(f" | Difference Image: {composite_image_path}")
        log.write("\n")

# Main motion detection function
def motion_detection():
    print("Starting motion detection...")

    while True:
        if not is_within_allowed_hours():
            print("Outside of allowed hours. Skipping motion detection...")
            sleep_time.sleep(60)  # Sleep for 1 minute before checking again
            continue

        for camera_name, config in CAMERA_CONFIGS.items():
            if config["roi"] is None:
                print(f"Skipping {camera_name}...")
                continue

            print(f"Checking {camera_name}...")
            roi = config["roi"]
            threshold_percentage = config["threshold_percentage"]
            luminance_threshold = config["luminance_threshold"]
            alert_type = config["alert_type"]
            interval_seconds = config["interval_seconds"]

            image1 = capture_real_image(roi)
            save_snapshot(image1, camera_name, "snapshot1.jpg")
            sleep_time.sleep(interval_seconds)
            image2 = capture_real_image(roi)
            save_snapshot(image2, camera_name, "snapshot2.jpg")

            diff, motion_detected = detect_motion(image1, image2, threshold_percentage, luminance_threshold)

            if motion_detected:
                diff_image = create_diff_image(image1, image2, luminance_threshold)
                composite_image_path = save_composite_image(image1, image2, diff_image, camera_name)
                log_event(camera_name, alert_type, composite_image_path)
                send_email_alert(camera_name, alert_type)
                last_alert_time[alert_type] = datetime.now()
                print(f"{alert_type} ALERT! Email sent and composite image saved.")
            else:
                print(f"No significant motion detected for {camera_name}. No comparison image saved.")

if __name__ == "__main__":
    motion_detection()
