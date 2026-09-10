import logging
import threading

import resend

logger = logging.getLogger(__name__)


def send_email_async(to, subject, html_message):
    """Fire-and-forget send through Resend. Best-effort: a failure here is
    logged, never raised, so it can't block the request that triggered it
    (registration, password reset, ...)."""

    def _send():
        try:
            resend.Emails.send({
                "from": "onboarding@resend.dev",
                "to": to,
                "subject": subject,
                "html": html_message,
            })
            logger.info("Email sent successfully via Resend API (subject=%r)", subject)
        except Exception:
            logger.exception("Failed to send email via Resend API (subject=%r)", subject)

    threading.Thread(target=_send).start()
