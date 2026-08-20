from __future__ import annotations
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

def send_email_alert(subject: str, message: str):
    """
    Sends an email alert to the agency using SMTP.
    Falls back to logging if SMTP is not configured.
    """
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = os.environ.get("SMTP_PORT", "587")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    email_from = os.environ.get("ALERT_EMAIL_FROM", "alerts@ezrankings.com")
    email_to = os.environ.get("ALERT_EMAIL_TO")

    if not smtp_host:
        logger.warning(f"SMTP_HOST not configured. Fallback alert logging:\nSubject: {subject}\nMessage: {message}")
        return

    if not email_to:
        logger.warning(f"ALERT_EMAIL_TO not configured. Fallback alert logging:\nSubject: {subject}\nMessage: {message}")
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = email_from
        msg["To"] = email_to
        msg["Subject"] = subject

        msg.attach(MIMEText(message, "plain"))

        server = smtplib.SMTP(smtp_host, int(smtp_port))
        server.starttls()
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
            
        server.send_message(msg)
        server.quit()
        logger.info(f"Successfully sent email alert: '{subject}' to {email_to}")
    except Exception as e:
        logger.error(f"Failed to send email alert. Error: {e}\nFallback alert logging:\nSubject: {subject}\nMessage: {message}")
