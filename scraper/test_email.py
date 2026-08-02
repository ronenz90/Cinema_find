"""
Sends a single test email using the same Gmail SMTP secrets as the real
scraper, to verify the credentials work without needing a real watch or
showtime change. Run via .github/workflows/test-email.yml.
"""

import os
import smtplib
from email.mime.text import MIMEText


def main() -> None:
    sender = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ.get("TEST_RECIPIENT") or os.environ["ALERT_RECIPIENT_EMAIL"]

    msg = MIMEText(
        "זהו מייל בדיקה מ-Cinema Watcher. אם קיבלת את זה, ה-Gmail secrets מוגדרים נכון.",
        "plain",
        "utf-8",
    )
    msg["Subject"] = "Cinema Watcher - מייל בדיקה"
    msg["From"] = sender
    msg["To"] = recipient

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)

    print(f"Test email sent to {recipient}")


if __name__ == "__main__":
    main()
