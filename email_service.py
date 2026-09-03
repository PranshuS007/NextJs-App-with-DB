import smtplib
from email.message import EmailMessage

from config.settings import settings


def queue_email(cur, email, subject, body, user_id=None):
    cur.execute(
        """
        INSERT INTO email_notifications (user_id, email, subject, body)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (user_id, email, subject, body),
    )
    return cur.fetchone()["id"]


def send_email_now(email, subject, body):
    if not settings.smtp_host or not settings.email_from:
        return False, "SMTP is not configured."

    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
    return True, None


def queue_and_send(cur, email, subject, body, user_id=None):
    notification_id = queue_email(cur, email, subject, body, user_id)
    try:
        sent, error = send_email_now(email, subject, body)
    except Exception as exc:
        sent, error = False, str(exc)
    if sent:
        cur.execute("UPDATE email_notifications SET status = 'sent', sent_at = NOW() WHERE id = %s", (notification_id,))
    else:
        cur.execute("UPDATE email_notifications SET status = 'pending', error = %s WHERE id = %s", (error, notification_id))
