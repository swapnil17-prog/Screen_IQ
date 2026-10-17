"""
Outgoing email over SMTP.

With SMTP_HOST unset (local development, tests) nothing leaves the machine: the
message is written to the log instead, so the flow stays testable end to end.
"""

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailError(Exception):
    """Delivery failed; `message` is safe to show to a recruiter."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _send_smtp(msg: EmailMessage) -> None:
    host, port, timeout = settings.smtp_host, settings.smtp_port, settings.smtp_timeout_seconds
    if settings.smtp_security == "ssl":
        server: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=timeout, context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)
    with server:
        if settings.smtp_security == "starttls":
            server.starttls(context=ssl.create_default_context())
        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)


async def send_email(*, to: str, subject: str, text: str, html: str | None = None,
                     from_name: str | None = None) -> str:
    """Send one message and return the delivery mode used ("smtp" or "console")."""
    if settings.email_delivery == "console":
        logger.info("Email not sent (SMTP_HOST is not set) — to=%s subject=%r\n%s", to, subject, text)
        return "console"

    sender = settings.email_from or settings.smtp_username
    if not sender:
        raise EmailError("Email is not configured: set EMAIL_FROM or SMTP_USERNAME.")
    msg = EmailMessage()
    msg["From"] = formataddr((from_name or settings.app_name, sender))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    try:
        await asyncio.to_thread(_send_smtp, msg)
    except smtplib.SMTPAuthenticationError as e:
        raise EmailError("The mail server rejected the SMTP username or password.") from e
    except smtplib.SMTPRecipientsRefused as e:
        raise EmailError("The mail server rejected the candidate's email address.") from e
    except (smtplib.SMTPException, OSError) as e:
        logger.warning("SMTP delivery to %s failed: %s", to, e)
        raise EmailError("The mail server could not be reached or refused the message.") from e
    return "smtp"
