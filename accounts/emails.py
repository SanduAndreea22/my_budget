import threading

import resend


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
            print("LOG: Email trimis cu succes prin Resend API!")
        except Exception as e:
            print(f"LOG EROARE RESEND: {e}")

    threading.Thread(target=_send).start()
