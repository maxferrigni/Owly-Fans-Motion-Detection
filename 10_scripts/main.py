import os
import json
from datetime import datetime, time, timedelta
from PIL import Image, ImageChops, ImageDraw, ImageFont
import pyautogui
import time as sleep_time
import pytz
import pandas as pd
import csv
from git import Repo
from alert_email import send_email_alert
import sys
import argparse

# Define Pacific Time Zone
PACIFIC_TIME = pytz.timezone("America/Los_Angeles")

# Base Directory
BASE_DIR = "/Users/maxferrigni/Insync/maxferrigni@gmail.com/Google Drive/01 - Owl Box/60_IT/20_Motion_Detection/30_OutPut_Files"

# Paths
INPUT_BASE_PATH = os.path.join(BASE_DIR, "base_images")
SNAPSHOT_PATH = os.path.join(BASE_DIR, "snapshots")
LOG_PATH = os.path.join(BASE_DIR, "logs")
DIFF_PATH = os.path.join(BASE_DIR, "differences")
ALERTS_PATH = os.path.join(BASE_DIR, "alerts")
CONFIGS_DIR = "/Users/maxferrigni/Insync/maxferrigni@gmail.com/Google Drive/01 - Owl Box/60_IT/20_Motion_Detection/10_GIT/Owly-Fans-Motion-Detection/20_configs"

# Local and Repository Log Paths
LOCAL_LOG_PATH = os.path.join(LOG_PATH, "local_owl_log.csv")
REPO_PATH = "/path/to/git/repo"  # Replace with your Git repo path
REPO_LOG_PATH = os.path.join(REPO_PATH, "30_Logs/repository_owl_log.csv")

# Ensure directories exist
for folder in [INPUT_BASE_PATH, SNAPSHOT_PATH, LOG_PATH, DIFF_PATH, ALERTS_PATH]:
    os.makedirs(folder, exist_ok=True)

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Motion Detection Script")
parser.add_argument("--darkness", action="store_true", help="Run the script during darkness only")
parser.add_argument("--all", action="store_true", help="Run the script at all times")
args = parser.parse_args()

# Determine mode
RUN_IN_DARKNESS_ONLY = args.darkness

# Load camera configurations
def load_config():
    config_path = os.path.join(CONFIGS_DIR, "config.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, 'r') as f:
        return json.load(f)

CAMERA_CONFIGS = load_config()

# Load sunrise/sunset data
SUNRISE_SUNSET_FILE = os.path.join(CONFIGS_DIR, "LA_Sunrise_Sunset.txt")
sunrise_sunset_data = pd.read_csv(SUNRISE_SUNSET_FILE, delimiter='\t')
sunrise_sunset_data['Date'] = pd.to_datetime(sunrise_sunset_data['Date']).dt.date

def get_darkness_times():
    today = datetime.now(PACIFIC_TIME).date()
    row = sunrise_sunset_data[sunrise_sunset_data['Date'] == today]

    if row.empty:
        raise ValueError(f"No sunrise/sunset data available for {today}")

    sunrise_time = datetime.strptime(row.iloc[0]['Sunrise'], '%H:%M').time()
    sunset_time = datetime.strptime(row.iloc[0]['Sunset'], '%H:%M').time()

    darkness_start = (datetime.combine(datetime.today(), sunrise_time) - timedelta(minutes=40)).time()
    darkness_end = (datetime.combine(datetime.today(), sunset_time) + timedelta(minutes=40)).time()

    return darkness_start, darkness_end

def is_within_allowed_hours():
    now = datetime.now(PACIFIC_TIME).time()
    darkness_start, darkness_end = get_darkness_times()
    return darkness_end <= now or now <= darkness_start

# Append log entry to local file
def append_to_local_log(camera_name, status, pixel_change=None, luminance_change=None):
    now = datetime.now(PACIFIC_TIME)
    row = [
        now.strftime("%Y-%m-%d %H:%M:%S"),
        camera_name,
        status,
        pixel_change or "",
        luminance_change or ""
    ]

    if not os.path.exists(LOCAL_LOG_PATH):
        with open(LOCAL_LOG_PATH, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "CameraName", "Status", "PixelChange", "LuminanceChange"])

    with open(LOCAL_LOG_PATH, "a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(row)

# Log event to daily file
def log_event(camera_name, status, pixel_change=None, luminance_change=None):
    daily_log_folder = os.path.join(LOG_PATH, "motion_logs")
    os.makedirs(daily_log_folder, exist_ok=True)

    date_str = datetime.now(PACIFIC_TIME).strftime("%Y-%m-%d")
    log_file = os.path.join(daily_log_folder, f"motion_log_{date_str}.txt")

    timestamp = datetime.now(PACIFIC_TIME).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{timestamp}|{camera_name}|{status}|{pixel_change or ''}|{luminance_change or ''}\n"

    with open(log_file, "a") as log:
        log.write(entry)

# Merge local log with repository log
def merge_logs():
    if not os.path.exists(LOCAL_LOG_PATH):
        print(f"Local log file not found: {LOCAL_LOG_PATH}")
        return

    if not os.path.exists(REPO_LOG_PATH):
        with open(REPO_LOG_PATH, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "CameraName", "Status", "PixelChange", "LuminanceChange"])

    with open(REPO_LOG_PATH, "a", newline="") as repo_file, open(LOCAL_LOG_PATH, "r") as local_file:
        repo_writer = csv.writer(repo_file)
        local_reader = csv.reader(local_file)
        next(local_reader)  # Skip header
        for row in local_reader:
            repo_writer.writerow(row)

# Push changes to GitHub
def push_to_git():
    repo = Repo(REPO_PATH)
    repo.git.add(update=True)
    repo.index.commit(f"Update logs on {datetime.now(PACIFIC_TIME).strftime('%Y-%m-%d %H:%M:%S')}")
    repo.remote(name="origin").push()
    print("Changes pushed to GitHub")

# Detect motion
def detect_motion(base_image, new_image, threshold_percentage, luminance_threshold):
    diff = ImageChops.difference(base_image, new_image).convert("L")
    total_pixels = diff.size[0] * diff.size[1]
    significant_pixels = sum(1 for pixel in diff.getdata() if pixel > luminance_threshold)
    avg_luminance_change = sum(diff.getdata()) / total_pixels
    threshold_pixels = total_pixels * threshold_percentage
    return diff, significant_pixels > threshold_pixels, significant_pixels, avg_luminance_change, total_pixels

# Load base image
def load_base_image(camera_name):
    base_image_path = os.path.join(INPUT_BASE_PATH, f"{camera_name}_base.jpg")
    if not os.path.exists(base_image_path):
        raise FileNotFoundError(f"Base image not found for {camera_name}")
    return Image.open(base_image_path).convert("RGB")

# Capture real image
def capture_real_image(roi):
    x, y, width, height = roi
    region = (x, y, width, height)
    screenshot = pyautogui.screenshot(region=region)
    return screenshot.convert("RGB")

# Save snapshot
def save_snapshot(image, camera_name, snapshot_name):
    snapshot_folder = os.path.join(SNAPSHOT_PATH, camera_name)
    os.makedirs(snapshot_folder, exist_ok=True)
    snapshot_path = os.path.join(snapshot_folder, snapshot_name)
    image.save(snapshot_path)
    return snapshot_path

# Generate combined output
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

# Main motion detection loop
def motion_detection():
    print("Starting motion detection...")

    while True:
        if RUN_IN_DARKNESS_ONLY and not is_within_allowed_hours():
            print("Outside of allowed hours. Waiting...")
            sleep_time.sleep(60)
            continue

        for camera_name, config in CAMERA_CONFIGS.items():
            try:
                if not config.get("roi"):
                    print(f"Skipping {camera_name}: No ROI defined")
                    continue

                base_image = load_base_image(camera_name)
                new_image = capture_real_image(config["roi"])

                diff, motion_detected, significant_pixels, avg_luminance_change, total_pixels = detect_motion(
                    base_image, new_image, config["threshold_percentage"], config["luminance_threshold"]
                )

                snapshot_name = f"{datetime.now(PACIFIC_TIME).strftime('%Y%m%d%H%M%S')}.jpg"
                save_snapshot(new_image, camera_name, snapshot_name)

                if motion_detected:
                    append_to_local_log(camera_name, "Motion Detected", f"{significant_pixels / total_pixels:.2%}", f"{avg_luminance_change:.2f}")
                    log_event(camera_name, "Motion Detected", f"{significant_pixels / total_pixels:.2%}", f"{avg_luminance_change:.2f}")
                else:
                    append_to_local_log(camera_name, "No Motion", f"{significant_pixels / total_pixels:.2%}", f"{avg_luminance_change:.2f}")
                    log_event(camera_name, "No Motion", f"{significant_pixels / total_pixels:.2%}", f"{avg_luminance_change:.2f}")

            except Exception as e:
                print(f"Error processing {camera_name}: {e}")

        sleep_time.sleep(20)

# Scheduled daily task
def scheduled_push():
    merge_logs()
    push_to_git()

if __name__ == "__main__":
    motion_detection()
