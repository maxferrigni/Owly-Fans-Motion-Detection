import subprocess
import os

# Path to the motion detection script
MOTION_DETECTION_SCRIPT = "/path/to/motion_detection.py"  # Replace with your actual script path

def launch_motion_detection():
    try:
        # Launch the motion detection script
        subprocess.run(["python3", MOTION_DETECTION_SCRIPT], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running motion_detection.py: {e}")
    except FileNotFoundError:
        print("Python or the script could not be found. Check the path and Python installation.")

if __name__ == "__main__":
    launch_motion_detection()
