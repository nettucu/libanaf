"""Email notifications for sync failures.

Uses the stdlib ``smtplib`` so no additional dependencies are required.
Errors during sending are logged but never propagate — a notification
failure must not mask the original sync failure.
"""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage

logger = logging.getLogger(__name__)

_FROM_ADDR = "libanaf@localhost"


def send_email(
    subject: str,
    body: str,
    to: str,
    smtp_host: str = "localhost",
    smtp_port: int = 25,
    smtp_user: str | None = None,
    smtp_password: str | None = None,
) -> None:
    """Send a plain-text notification email via SMTP.

    When *smtp_user* and *smtp_password* are both provided the connection is
    upgraded with STARTTLS before authentication (required for Gmail on port 587).
    Without credentials the message is sent over a plain unauthenticated
    connection, suitable for a local relay on port 25.

    Args:
        subject: Email subject line.
        body: Plain-text email body.
        to: Recipient address.
        smtp_host: SMTP server hostname. Defaults to ``"localhost"``.
        smtp_port: SMTP server port. Defaults to 25.
        smtp_user: SMTP login username; triggers STARTTLS when set.
        smtp_password: SMTP login password.
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_user if smtp_user else _FROM_ADDR
    msg["To"] = to
    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
            if smtp_user and smtp_password:
                smtp.starttls()
                smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)
        logger.info(f"Notification sent to {to}: {subject!r}")
    except Exception as exc:
        logger.error(f"Failed to send notification email to {to}: {exc}")


def send_token_expired_alert(
    to: str,
    error: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str | None = None,
    smtp_password: str | None = None,
) -> None:
    """Send an alert that the ANAF refresh token has expired.

    Args:
        to: Recipient email address.
        error: String representation of the underlying OAuth2 error.
        smtp_host: SMTP server hostname.
        smtp_port: SMTP server port.
        smtp_user: Optional SMTP login username.
        smtp_password: Optional SMTP login password.
    """
    body = (
        f"LibANAF sync failed at {datetime.now().isoformat(timespec='seconds')} because the ANAF\n"
        "OAuth2 refresh token is no longer valid. A hard re-authorization is required.\n\n"
        f"Underlying error: {error}\n\n"
        "To fix this, run:\n\n"
        "    libanaf auth\n\n"
        "and follow the browser-based login flow.\n"
    )
    send_email(
        subject="[libanaf] ANAF token expired — manual re-auth required",
        body=body,
        to=to,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
    )


def send_network_failure_alert(
    to: str,
    error: str,
    failure_count: int,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str | None = None,
    smtp_password: str | None = None,
) -> None:
    """Send an alert that repeated network failures have hit the configured threshold.

    Args:
        to: Recipient email address.
        error: String representation of the most recent error.
        failure_count: Current consecutive failure count.
        smtp_host: SMTP server hostname.
        smtp_port: SMTP server port.
        smtp_user: Optional SMTP login username.
        smtp_password: Optional SMTP login password.
    """
    body = (
        f"LibANAF sync has failed {failure_count} consecutive time(s) as of\n"
        f"{datetime.now().isoformat(timespec='seconds')}.\n\n"
        f"Most recent error: {error}\n\n"
        "This may indicate a network outage or ANAF API unavailability.\n"
        "No action is needed if ANAF is temporarily down; the next successful\n"
        "sync will automatically reset the failure counter.\n"
    )
    send_email(
        subject=f"[libanaf] {failure_count} consecutive sync failure(s) — network/API error",
        body=body,
        to=to,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
    )
