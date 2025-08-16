
import smtplib
from email.mime.text import MIMEText

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "your_email@gmail.com"
SENDER_PASSWORD = "your_app_password"
RECIPIENT_EMAIL = "recipient@example.com"

def send_email(finding):
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
    except Exception as e:
        print(f"[Email] Failed to send: {e}")
