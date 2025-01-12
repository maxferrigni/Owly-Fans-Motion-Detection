import os
import json
from datetime import datetime, time, timedelta
from PIL import Image, ImageChops, ImageDraw, ImageFont
import pyautogui
import time as sleep_time
import pytz
import pandas as pd
from alert_email import send_email_alert  # Import the email alert function
import sys  # For real-time stdout flushing

# Define Pacific Time Zone
PACIFIC_TIME = pytz.timezone("America/Los_Angeles")

# Paths
INPUT_BASE_PATH = "/path/to/base/images"
OUTPUT_PATH = "/path/to/output/files"
SNAPSHOT_PATH = OUTPUT_PATH
LOG_PATH = os.path.join(OUTPUT_PATH, "logs")
DIFF_PATH = os.path.join(OUTPUT_PATH, "differences")
ALERTS_PATH = os.path.join(OUTPUT_PATH, "alerts")

# Alert subfolders for each camera
ALERT_SUBFOLDERS = {
    "Upper Patio Camera": os.path.join(ALERTS_PATH, "Upper_Patio"),
    "Bindy Patio Camera": os.path.join(ALERTS_PATH, "Bindy_Patio"),
    "Wyze Internal Camera": os.path.join(ALERTS_PATH, "Wyze_Internal"),
}

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

# Load the sunrise/sunset data
SUNRISE_SUNSET_FILE = os.path.join("./20 configs", "LA_Sunrise_Sunset.txt")
sunrise_sunset_data = pd.read_csv(SUNRISE_SUNSET_FILE, delimiter='\t')

# Convert Date column to datetime and normalize to date
sunrise_sunset_data['Date'] = pd.to_datetime(sunrise_sunset_data['Date']).dt.date

# Debugging: Ensure the Date column is processed correctly
print("Debug: Processed Date Column:\n", sunrise_sunset_data['Date'].head())

def get_darkness_times():
    today = datetime.now(PACIFIC_TIME).date()
    print("Debug: Today's Date:", today)

    row = sunrise_sunset_data[sunrise_sunset_data['Date'] == today]

    if row.empty:
        print("Debug: No matching row found. Full dataset:\n", sunrise_sunset_data)
        raise ValueError(f"No sunrise/sunset data available for {today}")

    sunrise_time = datetime.strptime(row.iloc[0]['Sunrise'], '%H:%M').time()
    sunset_time = datetime.strptime(row.iloc[0]['Sunset'], '%H:%M').time()

    darkness_start = (datetime.combine(datetime.today(), sunrise_time) - timedelta(minutes=40)).time()
    darkness_end = (datetime.combine(datetime.today(), sunset_time) + timedelta(minutes=40)).time()

    print(f"Debug: Darkness Start: {darkness_start}, Darkness End: {darkness_end}")
    return darkness_start, darkness_end

def is_within_allowed_hours():
    now = datetime.now(PACIFIC_TIME).time()
    darkness_start, darkness_end = get_darkness_times()
    return darkness_end <= now or now <= darkness_start

def update_base_images():
    print("Updating base images for all cameras...", flush=True)
    for camera_name, config in CAMERA_CONFIGS.items():
        try:
            if config["roi"] is None:
                print(f"Skipping {camera_name}: No ROI defined", flush=True)
                continue
            new_base_image = capture_real_image(config["roi"])
            base_image_path = BASE_IMAGES[camera_name]
            os.makedirs(os.path.dirname(base_image_path), exist_ok=True)
            new_base_image.save(base_image_path)
            print(f"Updated base image for {camera_name} at {base_image_path}", flush=True)
        except Exception as e:
            print(f"Error updating base image for {camera_name}: {e}", flush=True)

def load_base_image(camera_name):
    base_image_path = BASE_IMAGES.get(camera_name)
    if not base_image_path or not os.path.exists(base_image_path):
        raise FileNotFoundError(f"Base image for {camera_name} not found: {base_image_path}")
    image = Image.open(base_image_path)
    return image.convert("RGB")

def capture_real_image(roi):
    x, y, width, height = roi
    width = abs(width - x)
    height = abs(height - y)
    print(f"Capturing screenshot: x={x}, y={y}, width={width}, height={height}", flush=True)
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid ROI dimensions: {roi}")
    screenshot = pyautogui.screenshot(region=(x, y, width, height))
    return screenshot.convert("RGB")

def save_snapshot(image, camera_name, snapshot_name):
    camera_folder = os.path.join(SNAPSHOT_PATH, camera_name)
    os.makedirs(camera_folder, exist_ok=True)
    if image.mode == "RGBA":
        image = image.convert("RGB")
    image_path = os.path.join(camera_folder, snapshot_name)
    image.save(image_path)
    return image_path

def log_event(camera_name, status, pixel_change=None, luminance_change=None):
    daily_log_folder = os.path.join(LOG_PATH, "motion_logs")
    os.makedirs(daily_log_folder, exist_ok=True)

    date_str = datetime.now(PACIFIC_TIME).strftime("%Y-%m-%d")
    log_file = os.path.join(daily_log_folder, f"motion_log_{date_str}.txt")

    timestamp = datetime.now(PACIFIC_TIME).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{timestamp}|{camera_name}|{status}|{pixel_change or ''}|{luminance_change or ''}\n"

    with open(log_file, "a") as log:
        log.write(entry)

def detect_motion(base_image, new_image, threshold_percentage, luminance_threshold):
    diff = ImageChops.difference(base_image, new_image).convert("L")
    total_pixels = diff.size[0] * diff.size[1]
    significant_pixels = sum(1 for pixel in diff.getdata() if pixel > luminance_threshold)
    avg_luminance_change = sum(diff.getdata()) / total_pixels
    threshold_pixels = total_pixels * threshold_percentage
    motion_detected = significant_pixels > threshold_pixels
    return diff, motion_detected, significant_pixels, avg_luminance_change, total_pixels

def create_combined_output(base_image, snapshot_image, diff_image, metrics_text, camera_name):
    os.makedirs(DIFF_PATH, exist_ok=True)

    heatmap = snapshot_image.copy()
    draw = ImageDraw.Draw(heatmap)
    for x in range(diff_image.width):
        for y in range(diff_image.height):
            if diff_image.getpixel((x, y)) > 50:
                draw.point((x, y), fill="red")

    width, height = base_image.size
    combined_width = width * 3
    combined_image = Image.new("RGB", (combined_width, height))
    combined_image.paste(base_image, (0, 0))
    combined_image.paste(snapshot_image, (width, 0))
    combined_image.paste(heatmap, (width * 2, 0))

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font = ImageFont.truetype(font_path, size=14) if os.path.exists(font_path) else None
    draw = ImageDraw.Draw(combined_image)
    draw.multiline_text((width * 2 + 10, 10), metrics_text, fill="yellow", font=font)

    combined_path = os.path.join(DIFF_PATH, f"{camera_name}_combined.jpg")
    combined_image.save(combined_path)
    return combined_image, combined_path

def motion_detection():
    print("Starting motion detection...", flush=True)
    base_images_updated = False

    while True:
        if not is_within_allowed_hours():
            print("Outside of allowed hours. Waiting...", flush=True)
            sleep_time.sleep(60)
            base_images_updated = False  # Reset for the next night
            continue

        if not base_images_updated:
            update_base_images()
            base_images_updated = True

        for camera_name, config in CAMERA_CONFIGS.items():
            try:
                if config["roi"] is None:
                    print(f"Skipping {camera_name}: No ROI Defined", flush=True)
                    continue

                base_image = load_base_image(camera_name)
                new_image = capture_real_image(config["roi"])
                save_snapshot(new_image, camera_name, "new_snapshot.jpg")

                diff, motion_detected, significant_pixels, avg_luminance_change, total_pixels = detect_motion(
                    base_image, new_image, config["threshold_percentage"], config["luminance_threshold"]
                )

                metrics_text = (
                    f"Pixel Changes: {significant_pixels / total_pixels:.2%}\n"
                    f"Avg Luminance Change: {avg_luminance_change:.2f}\n"
                    f"Threshold: {config['threshold_percentage'] * 100:.2f}% pixels, "
                    f"Luminance > {config['luminance_threshold']}"
                )
                combined_image, _ = create_combined_output(base_image, new_image, diff, metrics_text, camera_name)

                if motion_detected:
                    print(f"Motion detected for {camera_name}!", flush=True)
                    save_alert_image(combined_image, camera_name)
                    log_event(camera_name, "Motion Detected", f"{significant_pixels / total_pixels:.2%}", f"{avg_luminance_change:.2f}")
                else:
                    log_event(camera_name, "No Motion", f"{significant_pixels / total_pixels:.2%}", f"{avg_luminance_change:.2f}")

            except Exception as e:
                print(f"Error processing {camera_name}: {e}", flush=True)

        sleep_time.sleep(20)

if __name__ == "__main__":
    motion_detection()
