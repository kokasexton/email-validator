import unittest
from unittest.mock import AsyncMock, patch

from email_validator.batch import read_csv_rows, read_emails_from_csv, validate_batch, validate_single


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
            "failure_reason": "dns_timeout",
        }

        result = await validate_single("team@example.com", do_smtp=False)

        self.assertEqual(result.status, "unknown")
        self.assertTrue(result.block)
        self.assertIn("timed out", result.error)
        self.assertEqual(result.failure_reason, "dns_timeout")

    @patch("email_validator.batch.check_mx", new_callable=AsyncMock)
    async def test_missing_domain_returns_invalid(self, mock_check_mx):
        mock_check_mx.return_value = {
            "mx_records": False,
            "mx_hosts": [],
            "temporary_failure": False,
            "error": "Domain does not exist",
            "failure_reason": "domain_not_found",
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
        self.assertEqual(result.failure_reason, "smtp_disabled")

    async def test_batch_retries_temporary_smtp_failures(self):
        calls = []

        async def fake_verify(email, mx_hosts, timeout):
            calls.append((email, tuple(mx_hosts), timeout))
            if len(calls) == 1:
                return {
                    "smtp_check": False,
                    "smtp_server": "mx.example.com",
                    "accept_all": False,
                    "block": True,
                    "temporary_failure": True,
                    "error": "All MX failed: Temp fail: 451 try again later",
                    "failure_reason": "smtp_greylisted",
                }
            return {
                "smtp_check": True,
                "smtp_server": "mx.example.com",
                "accept_all": False,
                "block": False,
                "temporary_failure": False,
                "error": "",
                "failure_reason": "",
            }

        with patch("email_validator.batch.check_mx", new_callable=AsyncMock) as mock_check_mx:
            with patch("email_validator.batch.verify_smtp", new_callable=AsyncMock, side_effect=fake_verify):
                mock_check_mx.return_value = {
                    "mx_records": True,
                    "mx_hosts": ["mx.example.com"],
                    "temporary_failure": False,
                    "error": "",
                    "failure_reason": "",
                }
                results = await validate_batch(
                    ["team@example.com"],
                    smtp_retry_attempts=1,
                    smtp_retry_backoff_seconds=0,
                    smtp_min_interval_seconds=0,
                )

        self.assertEqual(results[0].status, "valid")
        self.assertEqual(len(calls), 2)


class CsvReaderTests(unittest.TestCase):
    def test_business_email_alias_is_supported(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "leads.csv"
            path.write_text("business_email,name\nfounder@example.com,Founder\n", encoding="utf-8")

            emails = read_emails_from_csv(str(path))

        self.assertEqual(emails, ["founder@example.com"])

    def test_source_rows_are_preserved_for_output_merging(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "leads.csv"
            path.write_text(
                "name,business_email,company\nJane,founder@example.com,Acme\n",
                encoding="utf-8",
            )

            rows = read_csv_rows(str(path))

        self.assertEqual(rows[0].email, "founder@example.com")
        self.assertEqual(rows[0].source_row["name"], "Jane")
        self.assertEqual(rows[0].source_row["company"], "Acme")
