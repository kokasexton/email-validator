import unittest
from unittest.mock import AsyncMock, patch

from email_validator.batch import read_emails_from_csv, validate_single


class ValidateSingleTests(unittest.IsolatedAsyncioTestCase):
    @patch("email_validator.batch.verify_smtp", new_callable=AsyncMock)
    @patch("email_validator.batch.check_mx", new_callable=AsyncMock)
    async def test_accept_all_status_is_exposed(self, mock_check_mx, mock_verify_smtp):
        mock_check_mx.return_value = {
            "mx_records": True,
            "mx_hosts": ["mx.example.com"],
            "temporary_failure": False,
            "error": "",
        }
        mock_verify_smtp.return_value = {
            "smtp_check": True,
            "smtp_server": "mx.example.com",
            "accept_all": True,
            "block": False,
            "temporary_failure": False,
            "error": "",
        }

        result = await validate_single("team@example.com")

        self.assertEqual(result.status, "accept_all")
        self.assertTrue(result.smtp_check)
        self.assertTrue(result.accept_all)

    @patch("email_validator.batch.check_mx", new_callable=AsyncMock)
    async def test_dns_temporary_failure_returns_unknown(self, mock_check_mx):
        mock_check_mx.return_value = {
            "mx_records": False,
            "mx_hosts": [],
            "temporary_failure": True,
            "error": "DNS lookup timed out",
        }

        result = await validate_single("team@example.com", do_smtp=False)

        self.assertEqual(result.status, "unknown")
        self.assertTrue(result.block)
        self.assertIn("timed out", result.error)

    @patch("email_validator.batch.check_mx", new_callable=AsyncMock)
    async def test_missing_domain_returns_invalid(self, mock_check_mx):
        mock_check_mx.return_value = {
            "mx_records": False,
            "mx_hosts": [],
            "temporary_failure": False,
            "error": "Domain does not exist",
        }

        result = await validate_single("team@example.com", do_smtp=False)

        self.assertEqual(result.status, "invalid")
        self.assertFalse(result.mx_records)

    @patch("email_validator.batch.check_mx", new_callable=AsyncMock)
    async def test_input_is_trimmed_before_validation(self, mock_check_mx):
        mock_check_mx.return_value = {
            "mx_records": True,
            "mx_hosts": ["mx.example.com"],
            "temporary_failure": False,
            "error": "",
        }

        result = await validate_single("  team@example.com  ", do_smtp=False)

        self.assertEqual(result.email, "team@example.com")
        self.assertEqual(result.status, "unknown")


class CsvReaderTests(unittest.TestCase):
    def test_business_email_alias_is_supported(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "leads.csv"
            path.write_text("business_email,name\nfounder@example.com,Founder\n", encoding="utf-8")

            emails = read_emails_from_csv(str(path))

        self.assertEqual(emails, ["founder@example.com"])
