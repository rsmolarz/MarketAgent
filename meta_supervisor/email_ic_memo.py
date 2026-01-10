import os
from pathlib import Path
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

MEMO = Path("meta_supervisor/reports/ic_weekly.md")

def send_ic_memo():
    if not MEMO.exists():
        return False

    api_key = os.environ.get("SENDGRID_API_KEY")
    to_list = [x.strip() for x in os.environ.get("META_EMAIL_TO","").split(",") if x.strip()]
    from_email = os.environ.get("EMAIL_FROM", "rsmolarz@medmoneyshow.com")

    if not api_key or not to_list:
        return False

    subject = os.environ.get("IC_MEMO_SUBJECT", "[IC Weekly] MarketAgents Memo")
    text = MEMO.read_text(encoding="utf-8")
    html = "<pre style='font-family:ui-monospace,Menlo,Consolas,monospace;white-space:pre-wrap'>" + text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;") + "</pre>"

    sg = SendGridAPIClient(api_key)
    for r in to_list:
        msg = Mail(
            from_email=Email(from_email),
            to_emails=To(r),
            subject=subject,
            plain_text_content=Content("text/plain", text),
            html_content=Content("text/html", html),
        )
        sg.send(msg)
    return True

if __name__ == "__main__":
    send_ic_memo()
