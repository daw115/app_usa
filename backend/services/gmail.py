from __future__ import annotations

import base64
import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from backend.config import config

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
]


def _get_credentials() -> Credentials:
    creds: Credentials | None = None
    if os.path.exists(config.gmail_token_path):
        creds = Credentials.from_authorized_user_file(config.gmail_token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(config.gmail_client_secrets):
                raise RuntimeError(
                    f"Missing Gmail client secrets at {config.gmail_client_secrets}. "
                    "Pobierz z Google Cloud Console (OAuth 2.0 client, desktop app)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(config.gmail_client_secrets, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(config.gmail_token_path, "w") as f:
            f.write(creds.to_json())
    return creds


def _build_raw(to: str, subject: str, html_body: str, sender: str = "me") -> str:
    msg = MIMEMultipart("alternative")
    msg["to"] = to
    msg["from"] = sender
    msg["subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")


def _send_via_smtp(to: str, subject: str, html_body: str) -> None:
    """Send email via SMTP (e.g., ATT Mail)"""
    if not all([config.smtp_host, config.smtp_user, config.smtp_password, config.smtp_from]):
        raise RuntimeError(
            "SMTP not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM in .env"
        )

    msg = MIMEMultipart("alternative")
    msg["From"] = config.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, context=context) as server:
        server.login(config.smtp_user, config.smtp_password)
        server.send_message(msg)
        log.info("Email sent via SMTP to %s", to)


def create_draft(to: str, subject: str, html_body: str) -> str:
    """Create Gmail draft via OAuth"""
    creds = _get_credentials()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    raw = _build_raw(to, subject, html_body)
    draft = service.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()
    log.info("Gmail draft created id=%s", draft.get("id"))
    return draft["id"]


def send_email(to: str, subject: str, html_body: str) -> str:
    """Send email using configured provider (Gmail OAuth or SMTP)"""
    if config.email_provider == "smtp":
        _send_via_smtp(to, subject, html_body)
        return "smtp_sent"
    else:
        return create_draft(to, subject, html_body)
