import os
import json
from datetime import datetime, time
from PIL import Image, ImageChops, ImageDraw, ImageFont
import pyautogui
import time as sleep_time
import pytz
from alert_email import send_email_alert  # Import the email alert function
import sys  # For real-time stdout flushing

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
    "Upper Patio Camera": os.path.join(INPUT_BASE_PATH, "Upper_Patio_Camera_Base.jpg"),
    "Bindy Patio Camera": os.path.join(INPUT_BASE_PATH, "Bindy_Patio_Camera_Base.jpg"),
    "Wyze Internal Camera": os.path.join(INPUT_BASE_PATH, "Wyze_Internal_Camera_Base.jpg"),
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
last_alert_time = {camera: None for camera in CAMERA_CONFIGS.keys()}

# Check if the current time is within the allowed range
def is_within_allowed_hours():
    now = datetime.now(PACIFIC_TIME).time()
    return START_TIME <= now or now <= END_TIME

# Load base image and ensure it's in RGB mode
def load_base_image(camera_name):
    base_image_path = BASE_IMAGES.get(camera_name)
    if not base_image_path or not os.path.exists(base_image_path):
        raise FileNotFoundError(f"Base image for {camera_name} not found: {base_image_path}")
    image = Image.open(base_image_path)
    return image.convert("RGB")  # Ensure base image is in RGB mode

# Capture an image from the screen based on the ROI
def capture_real_image(roi):
    x, y, width, height = roi
    width = abs(width - x)
    height = abs(height - y)
    print(f"Capturing screenshot: x={x}, y={y}, width={width}, height={height}", flush=True)
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid ROI dimensions: {roi}")
    
    # Capture and convert to RGB
    screenshot = pyautogui.screenshot(region=(x, y, width, height))
    return screenshot.convert("RGB")

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
    # Ensure images match dimensions and mode
    if image1.size != image2.size or image1.mode != image2.mode:
        raise ValueError("Base and captured images do not match in size or mode.")
    
    diff = ImageChops.difference(image1, image2)
    diff_data = diff.getdata()
    total_pixels = len(diff_data)
    significant_pixels = 0
    total_luminance_change = 0

    for pixel1, pixel2 in zip(image1.getdata(), image2.getdata()):
        luminance1 = calculate_luminance(pixel1)
        luminance2 = calculate_luminance(pixel2)
        total_luminance_change += abs(luminance1 - luminance2)
        pixel_diff = sum(abs(a - b) for a, b in zip(pixel1, pixel2))
        if pixel_diff > 50:  # Arbitrary threshold for pixel difference
            significant_pixels += 1
    
    avg_luminance_change = total_luminance_change / total_pixels
    threshold_pixels = total_pixels * threshold_percentage
    motion_detected = significant_pixels > threshold_pixels
    return diff, motion_detected, significant_pixels, avg_luminance_change, total_pixels

# Generate a heatmap image with metrics
def create_heatmap_with_metrics(base_image, new_image, diff, significant_pixels, luminance_change, total_pixels, camera_name):
    diff = diff.convert("L")
    heatmap_image = new_image.copy()
    draw = ImageDraw.Draw(heatmap_image)
    for x in range(diff.width):
        for y in range(diff.height):
            if diff.getpixel((x, y)) > 50:  # Threshold for significant differences
                draw.point((x, y), fill="red")
    
    metrics_text = (
        f"Pixel Changes: {significant_pixels / total_pixels:.2%}\n"
        f"Avg Luminance Change: {luminance_change:.2f}"
    )
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font = ImageFont.truetype(font_path, size=14) if os.path.exists(font_path) else None
    draw.multiline_text((10, 10), metrics_text, fill="yellow", font=font)
    
    heatmap_path = os.path.join(DIFF_PATH, f"{camera_name}_heatmap.jpg")
    heatmap_image.save(heatmap_path)
    return heatmap_path

# Log motion event or status
def log_event(camera_name, status):
    daily_log_folder = os.path.join(LOG_PATH, "motion_logs")
    os.makedirs(daily_log_folder, exist_ok=True)
    
    date_str = datetime.now(PACIFIC_TIME).strftime("%Y-%m-%d")
    log_file = os.path.join(daily_log_folder, f"motion_log_{date_str}.txt")
    
    timestamp = datetime.now(PACIFIC_TIME).strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as log:
        log.write(f"{timestamp} | Camera: {camera_name} | Status: {status}\n")

# Main motion detection function
def motion_detection():
    print("Starting motion detection...", flush=True)
    while True:
        if not is_within_allowed_hours():
            print("Outside of allowed hours. Skipping motion detection...", flush=True)
            sleep_time.sleep(60)
            continue
        
        for camera_name, config in CAMERA_CONFIGS.items():
            try:
                if config["roi"] is None:
                    print(f"Skipping {camera_name}: No ROI Defined", flush=True)
                    log_event(camera_name, "No ROI Defined")
                    continue

                print(f"Checking {camera_name}...", flush=True)
                roi = config["roi"]
                threshold_percentage = config["threshold_percentage"]
                luminance_threshold = config["luminance_threshold"]
                alert_type = config["alert_type"]

                new_image = capture_real_image(roi)
                save_snapshot(new_image, camera_name, "new_snapshot.jpg")
                base_image = load_base_image(camera_name)

                diff, motion_detected, significant_pixels, avg_luminance_change, total_pixels = detect_motion(
                    base_image, new_image, threshold_percentage, luminance_threshold
                )

                create_heatmap_with_metrics(base_image, new_image, diff, significant_pixels, avg_luminance_change, total_pixels, camera_name)

                if motion_detected:
                    log_event(camera_name, alert_type)
                    send_email_alert(camera_name, alert_type)
                    print(f"{alert_type} ALERT for {camera_name}! Email sent.", flush=True)
                else:
                    log_event(camera_name, "No Owl")
                    print(f"No significant motion detected for {camera_name}.", flush=True)
            except Exception as e:
                print(f"Error processing {camera_name}: {e}", flush=True)

        sleep_time.sleep(20)

if __name__ == "__main__":
    motion_detection()