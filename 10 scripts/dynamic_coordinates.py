import pyautogui
import time
import sys

try:
    print("Move your mouse to the desired region. Coordinates will update dynamically.")
    print("Press Ctrl+C to stop.\n")

    while True:
        x, y = pyautogui.position()  # Get the current mouse position
        # Print coordinates on the same line
        sys.stdout.write(f"\rMouse Position: x={x}, y={y}   ")
        sys.stdout.flush()
        time.sleep(0.1)  # Refresh every 0.1 seconds
except KeyboardInterrupt:
    print("\nExited coordinate capture.")
