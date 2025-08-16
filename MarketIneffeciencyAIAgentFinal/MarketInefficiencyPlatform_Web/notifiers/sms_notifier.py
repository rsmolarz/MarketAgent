
def send_sms(finding):
    try:
        print(f"[SMS] To +1234567890: {finding['title']} — {finding['description']}")
    except Exception as e:
        print(f"[SMS] Failed to send: {e}")
