"""Batch processing with concurrency and rate limiting."""
import asyncio
import csv
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

from .syntax import validate_syntax
from .dns_check import check_mx
from .smtp_check import verify_smtp
from .disposable import is_disposable, is_role_based, is_webmail


@dataclass
class EmailInput:
    email: str
    source_row: dict[str, str] = field(default_factory=dict)
    row_number: int = 0


@dataclass
class ValidationResult:
    email: str
    status: str = "unknown"
    failure_reason: str = ""
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
    source_row: dict[str, str] = field(default_factory=dict)
    row_number: int = 0

    def to_csv_row(self) -> dict:
        return {
            **self.source_row,
            "email": self.email,
            "status": self.status,
            "failure_reason": self.failure_reason,
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
    source_row: dict[str, str] | None = None,
    row_number: int = 0,
    smtp_verifier: Callable[[str, list[str], float], Any] | None = None,
) -> ValidationResult:
    """Run all validation stages on a single email."""
    normalized_email = email.strip()
    result = ValidationResult(
        email=normalized_email,
        source_row=dict(source_row or {}),
        row_number=row_number,
    )

    # Stage 1: Syntax
    syntax = validate_syntax(normalized_email)
    result.regexp = syntax["regexp"]
    result.gibberish = syntax["gibberish"]

    if not syntax["valid"]:
        result.status = "invalid"
        result.failure_reason = "syntax_invalid"
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
    result.failure_reason = mx_result.get("failure_reason", "")
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
            verifier = smtp_verifier or verify_smtp
            smtp_result = await verifier(
                normalized_email, mx_result["mx_hosts"], timeout=smtp_timeout
            )
        except Exception as e:
            result.error = f"SMTP error: {e}"
            result.block = True
            result.failure_reason = "smtp_error"
            result.status = "unknown"
            result.compute_score()
            return result

        result.smtp_server = smtp_result["smtp_server"]
        result.smtp_check = smtp_result["smtp_check"]
        result.block = smtp_result["block"]
        result.error = smtp_result.get("error", "")
        result.failure_reason = smtp_result.get("failure_reason", "")

        if smtp_result["smtp_check"] and not smtp_result.get("error"):
            result.accept_all = smtp_result["accept_all"]
            result.status = "accept_all" if result.accept_all else "valid"
            if result.accept_all:
                result.failure_reason = "accept_all_domain"
            else:
                result.failure_reason = ""
        elif smtp_result.get("error", "").startswith("Rejected:"):
            result.status = "invalid"
        elif smtp_result["block"]:
            result.status = "unknown"
    else:
        # No SMTP — mark as unknown if MX exists
        result.status = "unknown"
        result.failure_reason = "smtp_disabled"

    result.compute_score()
    return result


class DomainThrottle:
    """Coordinate SMTP pacing and retries for the same domain."""

    def __init__(
        self,
        max_concurrency_per_domain: int = 2,
        min_interval_seconds: float = 0.35,
        retry_attempts: int = 2,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        self._sem = defaultdict(lambda: asyncio.Semaphore(max_concurrency_per_domain))
        self._locks = defaultdict(asyncio.Lock)
        self._next_allowed_at: dict[str, float] = defaultdict(float)
        self._min_interval_seconds = min_interval_seconds
        self._retry_attempts = retry_attempts
        self._retry_backoff_seconds = retry_backoff_seconds

    async def verify(self, email: str, mx_hosts: list[str], timeout: float) -> dict:
        domain = email.rsplit("@", 1)[-1].lower()
        async with self._sem[domain]:
            attempts = 0
            while True:
                await self._wait_turn(domain)
                result = await verify_smtp(email, mx_hosts, timeout=timeout)
                if not result.get("temporary_failure"):
                    return result
                if attempts >= self._retry_attempts:
                    return result
                attempts += 1
                await asyncio.sleep(self._retry_backoff_seconds * attempts)

    async def _wait_turn(self, domain: str) -> None:
        async with self._locks[domain]:
            now = time.monotonic()
            delay = self._next_allowed_at[domain] - now
            if delay > 0:
                await asyncio.sleep(delay)
                now = time.monotonic()
            self._next_allowed_at[domain] = now + self._min_interval_seconds


async def validate_batch(
    emails: list[str] | list[EmailInput],
    workers: int = 10,
    do_smtp: bool = True,
    smtp_timeout: float = 10.0,
    dns_timeout: float = 5.0,
    progress_callback=None,
    max_smtp_concurrency_per_domain: int = 2,
    smtp_retry_attempts: int = 2,
    smtp_retry_backoff_seconds: float = 1.0,
    smtp_min_interval_seconds: float = 0.35,
) -> list[ValidationResult]:
    """Validate a batch of emails with concurrency."""
    if workers < 1:
        raise ValueError("workers must be >= 1")

    semaphore = asyncio.Semaphore(workers)
    throttle = DomainThrottle(
        max_concurrency_per_domain=max_smtp_concurrency_per_domain,
        min_interval_seconds=smtp_min_interval_seconds,
        retry_attempts=smtp_retry_attempts,
        retry_backoff_seconds=smtp_retry_backoff_seconds,
    )
    email_inputs = [
        item if isinstance(item, EmailInput) else EmailInput(email=item)
        for item in emails
    ]
    total = len(email_inputs)
    completed = 0

    async def worker(item: EmailInput) -> ValidationResult:
        nonlocal completed
        async with semaphore:
            result = await validate_single(
                item.email,
                do_smtp=do_smtp,
                smtp_timeout=smtp_timeout,
                dns_timeout=dns_timeout,
                source_row=item.source_row,
                row_number=item.row_number,
                smtp_verifier=throttle.verify if do_smtp else None,
            )
        completed += 1
        if progress_callback:
            progress_callback(completed, total, item.email, result.status)
        return result

    tasks = [worker(item) for item in email_inputs]
    return await asyncio.gather(*tasks)


def detect_email_column(fieldnames: list[str]) -> str:
    """Find the most likely email column name from a CSV header row."""
    aliases = {
        "email",
        "business email",
        "business_email",
        "e-mail",
        "email address",
    }
    for col in fieldnames:
        if col.lower().strip() in aliases:
            return col
    raise ValueError(f"No email column found. Available columns: {fieldnames}")


def read_emails_from_csv(path: str) -> list[str]:
    """Backward-compatible email extraction helper."""
    return [row.email for row in read_csv_rows(path)]


def read_csv_rows(path: str, email_column: str | None = None) -> list[EmailInput]:
    """Read source rows and preserve original columns for output merging."""
    rows: list[EmailInput] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV has no headers")

        email_col = email_column or detect_email_column(reader.fieldnames)

        for row_number, row in enumerate(reader, start=2):
            email = row.get(email_col, "").strip()
            if email:
                rows.append(
                    EmailInput(
                        email=email,
                        source_row={key: value or "" for key, value in row.items()},
                        row_number=row_number,
                    )
                )

    return rows


def write_results_csv(results: list[ValidationResult], path: str):
    """Write validation results to CSV, preserving source columns when available."""
    original_fieldnames: list[str] = []
    seen = set()
    for result in results:
        for key in result.source_row:
            if key not in seen:
                seen.add(key)
                original_fieldnames.append(key)

    validation_fieldnames = [
        "email",
        "status",
        "failure_reason",
        "regexp",
        "gibberish",
        "disposable",
        "webmail",
        "mx_records",
        "smtp_server",
        "smtp_check",
        "accept_all",
        "block",
        "score",
        "role_based",
    ]
    fieldnames = original_fieldnames + [
        field for field in validation_fieldnames if field not in original_fieldnames
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(r.to_csv_row())
