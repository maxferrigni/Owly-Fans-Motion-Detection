# File: alert_text.py
# Purpose:
# This script handles SMS text message alerts for the owl monitoring system.
# It reads recipient phone numbers from a file and sends alerts based on motion detection events.
# Features:
# - Reads recipients from text_recipients.txt
# - Sends SMS alerts for owl detection events
# - Supports different alert types based on camera events
# - Implements rate limiting to prevent spam
# Typical Usage:
# The script is called by the main monitoring system when motion is detected:
# `send_text_alert("Upper Patio Camera", "Owl In Area")`
