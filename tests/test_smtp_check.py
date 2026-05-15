import unittest
from unittest.mock import patch

from email_validator.smtp_check import verify_smtp_sync


class FakeSMTP:
    def __init__(self, timeout):
        self.timeout = timeout
        self.quit_calls = 0

    def connect(self, host, port):
        self.host = host
        self.port = port
        return (220, b"ready")

    def helo(self, name):
        return (250, b"hello")

    def ehlo(self, name):
        return (250, b"hello")

    def mailfrom(self, sender):
        return (250, b"ok")

    def rcpt(self, address):
        if address == "team@example.com":
            return (250, b"accepted")
        return (250, b"accepted")

    def quit(self):
        self.quit_calls += 1
        return (221, b"bye")


class RejectingSMTP(FakeSMTP):
    def rcpt(self, address):
        return (550, b"user unknown")


class TempFailureSMTP(FakeSMTP):
    def rcpt(self, address):
        return (451, b"try again later")


class SmtpVerificationTests(unittest.TestCase):
    @patch("email_validator.smtp_check.smtplib.SMTP", side_effect=FakeSMTP)
    def test_accept_all_probe_marks_result(self, mock_smtp_cls):
        result = verify_smtp_sync("team@example.com", ["mx.example.com"], timeout=3.0)

        self.assertTrue(result["smtp_check"])
        self.assertTrue(result["accept_all"])
        self.assertFalse(result["block"])

    @patch("email_validator.smtp_check.smtplib.SMTP", side_effect=RejectingSMTP)
    def test_rejected_mailbox_is_reported(self, mock_smtp_cls):
        result = verify_smtp_sync("team@example.com", ["mx.example.com"], timeout=3.0)

        self.assertTrue(result["smtp_check"])
        self.assertIn("Rejected: 550", result["error"])
        self.assertFalse(result["block"])

    @patch("email_validator.smtp_check.smtplib.SMTP", side_effect=TempFailureSMTP)
    def test_temporary_failures_fall_back_to_unknown(self, mock_smtp_cls):
        result = verify_smtp_sync("team@example.com", ["mx.example.com"], timeout=3.0)

        self.assertFalse(result["smtp_check"])
        self.assertTrue(result["temporary_failure"])
        self.assertTrue(result["block"])
