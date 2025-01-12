import subprocess

# Path to the motion detection script
MOTION_DETECTION_SCRIPT = "/Users/maxferrigni/Insync/maxferrigni@gmail.com/Google Drive/01 - Owl Box/60 IT/20 Motion Detection/10 GIT/Owly-Fans-Motion-Detection/10 scripts/motion_detection.py"

def launch_motion_detection():
    try:
        # Launch the motion detection script
        subprocess.run(["python3", MOTION_DETECTION_SCRIPT], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running motion_detection.py: {e}")
    except FileNotFoundError:
        print("Python or the script could not be found. Check the path and Python installation.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    launch_motion_detection()
