import unittest
from unittest.mock import patch

import dns.exception
import dns.resolver

from email_validator import dns_check


class FakeMXRecord:
    def __init__(self, preference, exchange):
        self.preference = preference
        self.exchange = exchange


class ResolverFallbackTests(unittest.TestCase):
    def tearDown(self):
        dns_check.check_mx_sync.cache_clear()

    @patch("email_validator.dns_check.dns.resolver.Resolver")
    def test_no_mx_falls_back_to_domain_a_record(self, mock_resolver_cls):
        resolver = mock_resolver_cls.return_value

        def resolve(name, record_type):
            if record_type == "MX":
                raise dns.resolver.NoAnswer()
            if record_type == "A":
                return ["203.0.113.10"]
            raise AssertionError(f"Unexpected record type: {record_type}")

        resolver.resolve.side_effect = resolve

        result = dns_check.check_mx_sync("example.com", timeout=5.0)

        self.assertTrue(result["mx_records"])
        self.assertTrue(result["implicit_mx"])
        self.assertEqual(result["mx_hosts"], ["example.com"])

    @patch("email_validator.dns_check.dns.resolver.Resolver")
    def test_timeout_is_marked_temporary(self, mock_resolver_cls):
        resolver = mock_resolver_cls.return_value
        resolver.resolve.side_effect = dns.exception.Timeout()

        result = dns_check.check_mx_sync("example.com", timeout=5.0)

        self.assertFalse(result["mx_records"])
        self.assertTrue(result["temporary_failure"])
        self.assertIn("timed out", result["error"].lower())
        self.assertEqual(result["failure_reason"], "dns_timeout")

    @patch("email_validator.dns_check.dns.resolver.Resolver")
    def test_mx_records_are_sorted_by_preference(self, mock_resolver_cls):
        resolver = mock_resolver_cls.return_value
        resolver.resolve.return_value = [
            FakeMXRecord(20, "mx2.example.com."),
            FakeMXRecord(10, "mx1.example.com."),
        ]

        result = dns_check.check_mx_sync("example.com", timeout=5.0)

        self.assertEqual(result["mx_hosts"], ["mx1.example.com", "mx2.example.com"])
