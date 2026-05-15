"""Batch processing with concurrency and rate limiting."""
import asyncio
import csv
from dataclasses import dataclass

from .syntax import validate_syntax
from .dns_check import check_mx
from .smtp_check import verify_smtp
from .disposable import is_disposable, is_role_based, is_webmail


@dataclass
class ValidationResult:
    email: str
    status: str = "unknown"
    regexp: bool = False
    gibberish: bool = False
    disposable: bool = False
    webmail: bool = False
    mx_records: bool = False
    smtp_server: str = ""
    smtp_check: bool = False
    accept_all: bool = False
    block: bool = False
    score: int = 0
    error: str = ""
    role_based: bool = False

    def to_csv_row(self) -> dict:
        return {
            "email": self.email,
            "status": self.status,
            "regexp": str(self.regexp).lower(),
            "gibberish": str(self.gibberish).lower(),
            "disposable": str(self.disposable).lower(),
            "webmail": str(self.webmail).lower(),
            "mx_records": str(self.mx_records).lower(),
            "smtp_server": self.smtp_server,
            "smtp_check": str(self.smtp_check).lower(),
            "accept_all": str(self.accept_all).lower(),
            "block": str(self.block).lower(),
            "score": str(self.score),
            "role_based": str(self.role_based).lower(),
        }

    def compute_score(self):
        """Compute 0-100 confidence score."""
        score = 0
        if self.regexp:
            score += 20
        if not self.gibberish:
            score += 10
        if not self.disposable:
            score += 10
        if self.mx_records:
            score += 20
        if self.smtp_check:
            score += 30
            if self.accept_all:
                score -= 10  # Penalty for accept_all
        if not self.block and self.mx_records:
            score += 10
        self.score = max(0, min(100, score))


async def validate_single(
    email: str,
    do_smtp: bool = True,
    smtp_timeout: float = 10.0,
    dns_timeout: float = 5.0,
) -> ValidationResult:
    """Run all validation stages on a single email."""
    normalized_email = email.strip()
    result = ValidationResult(email=normalized_email)

    # Stage 1: Syntax
    syntax = validate_syntax(normalized_email)
    result.regexp = syntax["regexp"]
    result.gibberish = syntax["gibberish"]

    if not syntax["valid"]:
        result.status = "invalid"
        result.compute_score()
        return result

    # Stage 2: Disposable & role & webmail
    result.disposable = is_disposable(normalized_email)
    result.role_based = is_role_based(normalized_email)
    result.webmail = is_webmail(normalized_email)

    # Stage 3: DNS/MX
    domain = normalized_email.rsplit("@", 1)[-1]
    mx_result = await check_mx(domain, timeout=dns_timeout)

    result.mx_records = mx_result["mx_records"]
    result.block = mx_result.get("temporary_failure", False)
    result.error = mx_result.get("error", "")
    if not mx_result["mx_records"]:
        if mx_result.get("temporary_failure"):
            result.status = "unknown"
        else:
            result.status = "invalid"
        result.compute_score()
        return result

    # Stage 4: SMTP (optional)
    if do_smtp and mx_result["mx_hosts"]:
        try:
            smtp_result = await verify_smtp(
                normalized_email, mx_result["mx_hosts"], timeout=smtp_timeout
            )
        except Exception as e:
            result.error = f"SMTP error: {e}"
            result.block = True
            result.compute_score()
            return result

        result.smtp_server = smtp_result["smtp_server"]
        result.smtp_check = smtp_result["smtp_check"]
        result.block = smtp_result["block"]
        result.error = smtp_result.get("error", "")

        if smtp_result["smtp_check"] and not smtp_result.get("error"):
            result.accept_all = smtp_result["accept_all"]
            result.status = "accept_all" if result.accept_all else "valid"
        elif smtp_result.get("error", "").startswith("Rejected:"):
            result.status = "invalid"
        elif smtp_result["block"]:
            result.status = "unknown"
    else:
        # No SMTP — mark as unknown if MX exists
        result.status = "unknown"

    result.compute_score()
    return result


async def validate_batch(
    emails: list[str],
    workers: int = 10,
    do_smtp: bool = True,
    smtp_timeout: float = 10.0,
    dns_timeout: float = 5.0,
    progress_callback=None,
) -> list[ValidationResult]:
    """Validate a batch of emails with concurrency."""
    if workers < 1:
        raise ValueError("workers must be >= 1")

    semaphore = asyncio.Semaphore(workers)
    total = len(emails)
    completed = 0

    async def worker(email: str) -> ValidationResult:
        nonlocal completed
        async with semaphore:
            result = await validate_single(
                email,
                do_smtp=do_smtp,
                smtp_timeout=smtp_timeout,
                dns_timeout=dns_timeout,
            )
        completed += 1
        if progress_callback:
            progress_callback(completed, total, email, result.status)
        return result

    tasks = [worker(email) for email in emails]
    return await asyncio.gather(*tasks)


def read_emails_from_csv(path: str) -> list[str]:
    """Extract email addresses from a CSV file.
    Looks for columns: 'email', 'Business Email', 'Email', 'business_email'.
    """
    emails = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV has no headers")

        # Find the email column
        email_col = None
        aliases = {
            "email",
            "business email",
            "business_email",
            "e-mail",
            "email address",
        }
        for col in reader.fieldnames:
            if col.lower().strip() in aliases:
                email_col = col
                break

        if email_col is None:
            raise ValueError(
                f"No email column found. Available columns: {reader.fieldnames}"
            )

        for row in reader:
            email = row.get(email_col, "").strip()
            if email:
                emails.append(email)

    return emails


def write_results_csv(results: list[ValidationResult], path: str):
    """Write validation results to CSV."""
    fieldnames = [
        "email", "status", "regexp", "gibberish", "disposable", "webmail",
        "mx_records", "smtp_server", "smtp_check", "accept_all", "block",
        "score", "role_based",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(r.to_csv_row())
