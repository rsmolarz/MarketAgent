
import os
import smtplib
from email.mime.text import MIMEText

SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")

def send_email(finding):
    # Check if required environment variables are set
    if not SENDER_EMAIL or not SENDER_PASSWORD or not RECIPIENT_EMAIL:
        print("[Email] Missing required environment variables: SENDER_EMAIL, SENDER_PASSWORD, or RECIPIENT_EMAIL")
        return False
    
    try:
        msg = MIMEText(f"{finding['title']}

{finding['description']}")
        msg['Subject'] = f"🚨 {finding['severity'].upper()} Alert from {finding['agent']}"
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECIPIENT_EMAIL

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        print("[Email] Alert sent.")
        return True
    except Exception as e:
        print(f"[Email] Failed to send: {e}")
        return False
