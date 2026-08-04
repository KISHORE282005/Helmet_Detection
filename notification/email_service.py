import logging
import smtplib
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path
from email.encoders import encode_base64

logger = logging.getLogger(__name__)

STATUS_SENT = "SENT"
STATUS_FAILED = "FAILED"
STATUS_SKIPPED = "SKIPPED"


class EmailService:
    """SMTP email sender with attach-and-retry support.

    Completely independent of the AI detection module. Returns a delivery
    result tuple (status, retry_count, remarks) so callers can persist it
    in the EMAIL_LOG table without caring about SMTP details.
    """

    def __init__(self, config):
        self.config = config

    def send(self, to_address, subject, body, attachment_path=None):
        """Send an email, retrying per config. Never raises.

        Returns (status, retry_count, remarks) where status is one of
        SENT / FAILED / SKIPPED.
        """
        cfg = self.config
        if not getattr(cfg, "EMAIL_ENABLED", True):
            logger.info(f"Email disabled; skipped notification to {to_address}")
            return STATUS_SKIPPED, 0, "EMAIL_ENABLED=False"

        if not to_address:
            return STATUS_FAILED, 0, "no recipient address"

        max_retries = int(getattr(cfg, "EMAIL_MAX_RETRIES", 1))
        last_error = None

        for attempt in range(max_retries + 1):
            retry_count = attempt
            try:
                self._send_once(to_address, subject, body, attachment_path)
                logger.info(
                    f"Email sent to {to_address} (retries: {retry_count})"
                    + (f", attachment: {Path(attachment_path).name}" if attachment_path else "")
                )
                return STATUS_SENT, retry_count, "OK"
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    f"Email send attempt {attempt + 1}/{max_retries + 1} failed for "
                    f"{to_address}: {last_error}"
                )

        return STATUS_FAILED, retry_count, last_error or "unknown error"

    def _send_once(self, to_address, subject, body, attachment_path=None):
        cfg = self.config
        msg = MIMEMultipart()
        msg["From"] = cfg.EMAIL_FROM
        msg["To"] = to_address
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()
        msg.attach(MIMEText(body, "plain", "utf-8"))

        if attachment_path and Path(attachment_path).exists():
            with open(attachment_path, "rb") as handle:
                part = MIMEBase("image", "jpeg")
                part.set_payload(handle.read())
            encode_base64(part)
            filename = Path(attachment_path).name
            part.add_header("Content-Disposition", f"attachment; filename={filename}")
            msg.attach(part)

        if cfg.EMAIL_SMTP_USE_TLS:
            server = smtplib.SMTP(cfg.EMAIL_SMTP_HOST, cfg.EMAIL_SMTP_PORT, timeout=cfg.EMAIL_TIMEOUT)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP(cfg.EMAIL_SMTP_HOST, cfg.EMAIL_SMTP_PORT, timeout=cfg.EMAIL_TIMEOUT)

        try:
            if cfg.EMAIL_SMTP_USERNAME:
                server.login(cfg.EMAIL_SMTP_USERNAME, cfg.EMAIL_SMTP_PASSWORD)
            server.sendmail(cfg.EMAIL_FROM, [to_address], msg.as_string())
        finally:
            server.quit()
