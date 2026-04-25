from unittest.mock import MagicMock, patch

import pytest

from backend.services import gmail


@pytest.fixture
def mock_smtp_config():
    with patch("backend.services.gmail.config") as mock_config:
        mock_config.email_provider = "smtp"
        mock_config.smtp_host = "smtp.example.com"
        mock_config.smtp_port = 465
        mock_config.smtp_user = "test@example.com"
        mock_config.smtp_password = "password123"
        mock_config.smtp_from = "test@example.com"
        yield mock_config


@pytest.fixture
def mock_gmail_config():
    with patch("backend.services.gmail.config") as mock_config:
        mock_config.email_provider = "gmail"
        mock_config.gmail_client_secrets = "./gmail_client_secret.json"
        mock_config.gmail_token_path = "./gmail_token.json"
        yield mock_config


def test_send_via_smtp_success(mock_smtp_config):
    with patch("backend.services.gmail.smtplib.SMTP_SSL") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        gmail._send_via_smtp(
            "client@example.com",
            "Test Subject",
            "<p>Test HTML body</p>"
        )

        mock_smtp.assert_called_once_with(
            "smtp.example.com", 465, context=mock_smtp.call_args[1]["context"]
        )
        mock_server.login.assert_called_once_with("test@example.com", "password123")
        mock_server.send_message.assert_called_once()


def test_send_via_smtp_missing_config():
    with patch("backend.services.gmail.config") as mock_config:
        mock_config.smtp_host = ""
        mock_config.smtp_user = ""
        mock_config.smtp_password = ""
        mock_config.smtp_from = ""

        with pytest.raises(RuntimeError, match="SMTP not configured"):
            gmail._send_via_smtp("client@example.com", "Subject", "Body")


def test_send_email_uses_smtp_when_configured(mock_smtp_config):
    with patch("backend.services.gmail._send_via_smtp") as mock_send:
        result = gmail.send_email(
            "client@example.com",
            "Test Subject",
            "<p>Body</p>"
        )

        assert result == "smtp_sent"
        mock_send.assert_called_once_with(
            "client@example.com", "Test Subject", "<p>Body</p>"
        )


def test_send_email_uses_gmail_when_configured(mock_gmail_config):
    with patch("backend.services.gmail.create_draft") as mock_draft:
        mock_draft.return_value = "draft_123"

        result = gmail.send_email(
            "client@example.com",
            "Test Subject",
            "<p>Body</p>"
        )

        assert result == "draft_123"
        mock_draft.assert_called_once_with(
            "client@example.com", "Test Subject", "<p>Body</p>"
        )
