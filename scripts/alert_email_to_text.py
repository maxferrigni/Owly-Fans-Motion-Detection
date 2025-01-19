# File: alert_email_to_text.py
# Purpose:
# This script converts email alerts to SMS text messages using email-to-SMS gateways.
# It provides a backup notification method when direct SMS sending is not available.
# Features:
# - Converts email content to SMS-friendly format
# - Supports multiple carrier gateways
# - Handles message length limitations
# - Implements rate limiting to prevent spam
# Typical Usage:
# The script is called by the alert system when direct SMS fails:
# `send_email_to_text("Upper Patio Camera", "Owl In Area", "3108088738")`
