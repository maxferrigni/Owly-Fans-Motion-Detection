import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Email credentials
EMAIL_ADDRESS = "owlyfans01@gmail.com"
EMAIL_PASSWORD = "ctktpkxhwzesjzgr"  # Your Google App Password

# Absolute path to recipients file
RECIPIENTS_FILE = "/Users/maxferrigni/Insync/maxferrigni@gmail.com/Google Drive/01 - Owl Box/60 Motion Detection/20 configs/email_recipients.txt"

# Function to read email recipients from a file
def get_recipients(file_path):
    try:
        with open(file_path, "r") as file:
            recipients = [line.strip() for line in file if line.strip()]
        return recipients
    except Exception as e:
        print(f"Error reading recipients file: {e}")
        return []

# Function to send email alert based on camera name and alert type
def send_email_alert(camera_name, alert_type):
    # Determine the subject and body based on camera name and alert type
    if camera_name == "Upper Patio Camera" and alert_type == "Owl In Area":
        subject = "ALERT: Owl In The Area"
        body = f"Motion has been detected in the Upper Patio area. Please check the camera feed at <a href='http://www.owly-fans.com'>Owly-Fans.com</a>."
    else:
        subject = "ALERT: Unknown Event"
        body = f"Motion has been detected at {camera_name}. Please check the camera feed at <a href='http://www.owly-fans.com'>Owly-Fans.com</a>."

    recipients = get_recipients(RECIPIENTS_FILE)

    if recipients:
        for email in recipients:
            send_single_email(subject, body, email)
    else:
        print("No recipients found. Please update the email_recipients.txt file.")

# Function to send a single email to a recipient
def send_single_email(subject, body, to_email):
    try:
        # Set up the email server
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

        # Create the email
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_email
        msg["Subject"] = subject

        # HTML email body with clickable link
        html_body = f"""
        <html>
            <body>
                <p>{body}</p>
                <p>Check the camera feed at <a href="http://www.owly-fans.com">Owly-Fans.com</a>.</p>
            </body>
        </html>
        """
        msg.attach(MIMEText(html_body, "html"))

        # Send the email
        server.send_message(msg)
        print(f"Email alert sent successfully to {to_email}!")

        # Close the connection
        server.quit()

    except smtplib.SMTPAuthenticationError as e:
        print(f"Authentication error: {e}")
    except smtplib.SMTPConnectError as e:
        print(f"Connection error: {e}")
    except Exception as e:
        print(f"Failed to send email alert to {to_email}: {e}")
