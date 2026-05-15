"""DNS check: MX record lookup for email domains."""
import asyncio
from functools import lru_cache

import dns.exception
import dns.resolver


@lru_cache(maxsize=2048)
def check_mx_sync(domain: str, timeout: float = 5.0) -> dict:
    """Synchronous MX check with RFC fallback to the domain itself.

    Returns:
        {
            "has_mx": bool,
            "mx_records": bool,
            "mx_hosts": list[str],
            "temporary_failure": bool,
            "implicit_mx": bool,
            "error": str,
        }
    """
    resolver = dns.resolver.Resolver()
    resolver.lifetime = timeout

    try:
        answers = resolver.resolve(domain, "MX")
        records = sorted(answers, key=lambda r: r.preference)
        return {
            "has_mx": True,
            "mx_records": True,
            "mx_hosts": [str(r.exchange).rstrip(".") for r in records],
            "temporary_failure": False,
            "implicit_mx": False,
            "error": "",
            "failure_reason": "",
        }
    except dns.resolver.NoAnswer:
        # RFC 5321 fallback: if no MX exists, the bare domain may still accept mail.
        for record_type in ("A", "AAAA"):
            try:
                resolver.resolve(domain, record_type)
                return {
                    "has_mx": True,
                    "mx_records": True,
                    "mx_hosts": [domain],
                    "temporary_failure": False,
                    "implicit_mx": True,
                    "error": "",
                    "failure_reason": "",
                }
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                continue
            except (dns.resolver.NoNameservers, dns.exception.Timeout) as exc:
                return {
                    "has_mx": False,
                    "mx_records": False,
                    "mx_hosts": [],
                    "temporary_failure": True,
                    "implicit_mx": False,
                    "error": str(exc),
                    "failure_reason": "dns_nameserver_failure"
                    if isinstance(exc, dns.resolver.NoNameservers)
                    else "dns_timeout",
                }

        return {
            "has_mx": False,
            "mx_records": False,
            "mx_hosts": [],
            "temporary_failure": False,
            "implicit_mx": False,
            "error": "No MX, A, or AAAA records found",
            "failure_reason": "no_dns_mail_route",
        }
    except dns.resolver.NXDOMAIN:
        return {
            "has_mx": False,
            "mx_records": False,
            "mx_hosts": [],
            "temporary_failure": False,
            "implicit_mx": False,
            "error": "Domain does not exist",
            "failure_reason": "domain_not_found",
        }
    except dns.resolver.NoNameservers as exc:
        return {
            "has_mx": False,
            "mx_records": False,
            "mx_hosts": [],
            "temporary_failure": True,
            "implicit_mx": False,
            "error": str(exc),
            "failure_reason": "dns_nameserver_failure",
        }
    except dns.exception.Timeout:
        return {
            "has_mx": False,
            "mx_records": False,
            "mx_hosts": [],
            "temporary_failure": True,
            "implicit_mx": False,
            "error": "DNS lookup timed out",
            "failure_reason": "dns_timeout",
        }
    except Exception as exc:
        return {
            "has_mx": False,
            "mx_records": False,
            "mx_hosts": [],
            "temporary_failure": True,
            "implicit_mx": False,
            "error": str(exc),
            "failure_reason": "dns_error",
        }


async def check_mx(domain: str, timeout: float = 5.0) -> dict:
    """Async MX check wrapper."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, check_mx_sync, domain, timeout)
