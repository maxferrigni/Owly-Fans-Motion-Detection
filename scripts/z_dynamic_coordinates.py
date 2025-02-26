# File: dynamic_coordinates.py
# Purpose:
# This script helps users define Regions of Interest (ROI) by tracking mouse coordinates in real-time.
# It displays the current x,y coordinates of the mouse cursor, making it easier to configure ROIs
# for the owl monitoring system.
# Features:
# - Real-time display of mouse x,y coordinates
# - Continuous update of position
# - Clean exit with Ctrl+C
# Typical Usage:
# Run this script before configuring ROIs to determine the correct coordinates:
# `python dynamic_coordinates.py`
# Then use the displayed coordinates to update config.json

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
