
from .email_notifier import send_email
from .telegram_notifier import send_telegram
from .sms_notifier import send_sms

def notify_all(finding):
    send_email(finding)
    send_telegram(finding)
    send_sms(finding)
