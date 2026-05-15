"""CLI entry point for the local email validator."""
import argparse
import asyncio
import sys
import time
from pathlib import Path

from .batch import read_csv_rows, validate_batch, validate_single, write_results_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Free local email validation: syntax, disposable, role, DNS/MX, and SMTP.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  email-validator leads.csv                    Validate all emails in a CSV
  email-validator --email test@example.com     Validate a single email
  email-validator leads.csv -o output.csv      Write to a specific output file
  email-validator leads.csv -w 20              Run with 20 concurrent workers
  email-validator leads.csv --no-smtp          DNS-only mode
        """,
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="CSV file with an email column (or use --email for single-email mode)",
    )
    parser.add_argument("--email", "-e", help="Validate a single email address")
    parser.add_argument(
        "--output",
        "-o",
        help="Output CSV path (default: <input>-validated.csv)",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=10,
        help="Concurrent workers (default: 10)",
    )
    parser.add_argument(
        "--no-smtp",
        action="store_true",
        help="Skip SMTP verification and stop at DNS/MX",
    )
    parser.add_argument(
        "--smtp-timeout",
        type=float,
        default=10.0,
        help="SMTP timeout per email in seconds (default: 10)",
    )
    parser.add_argument(
        "--dns-timeout",
        type=float,
        default=5.0,
        help="DNS timeout per domain in seconds (default: 5)",
    )
    parser.add_argument(
        "--email-column",
        help="Explicit CSV column name if auto-detection fails",
    )
    parser.add_argument(
        "--max-smtp-per-domain",
        type=int,
        default=2,
        help="Max concurrent SMTP checks per domain (default: 2)",
    )
    parser.add_argument(
        "--smtp-retries",
        type=int,
        default=2,
        help="Retries for temporary SMTP failures per email (default: 2)",
    )
    parser.add_argument(
        "--smtp-retry-backoff",
        type=float,
        default=1.0,
        help="Base backoff in seconds between SMTP retries (default: 1.0)",
    )
    parser.add_argument(
        "--smtp-min-interval",
        type=float,
        default=0.35,
        help="Minimum spacing in seconds between SMTP attempts to the same domain (default: 0.35)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.workers < 1:
        parser.error("--workers must be >= 1")

    if args.smtp_timeout <= 0 or args.dns_timeout <= 0:
        parser.error("--smtp-timeout and --dns-timeout must be > 0")
    if args.max_smtp_per_domain < 1:
        parser.error("--max-smtp-per-domain must be >= 1")
    if args.smtp_retries < 0:
        parser.error("--smtp-retries must be >= 0")
    if args.smtp_retry_backoff < 0 or args.smtp_min_interval < 0:
        parser.error("--smtp-retry-backoff and --smtp-min-interval must be >= 0")

    if args.email:
        print(f"Validating: {args.email}")
        result = asyncio.run(
            validate_single(
                args.email,
                do_smtp=not args.no_smtp,
                smtp_timeout=args.smtp_timeout,
                dns_timeout=args.dns_timeout,
            )
        )
        _print_single_result(result)
        return 0

    if not args.input:
        parser.error("Either provide a CSV file or use --email")

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        return 1

    print(f"Reading: {args.input}")
    email_rows = _load_rows(args.input, args.email_column)
    if not email_rows:
        print("Error: no non-empty emails found in the input file", file=sys.stderr)
        return 1

    print(f"Found {len(email_rows)} emails")
    print(f"SMTP: {'OFF' if args.no_smtp else 'ON'} | Workers: {args.workers}")

    start = time.time()

    def progress(completed: int, total: int, email: str, status: str) -> None:
        if total <= 0:
            return
        if completed % max(1, total // 20) != 0 and completed != total:
            return

        pct = completed / total * 100
        elapsed = time.time() - start
        rate = completed / elapsed if elapsed > 0 else 0
        remaining = (total - completed) / rate if rate > 0 else 0
        print(
            f"  [{completed}/{total}] {pct:.0f}% | "
            f"{rate:.1f}/s | ETA {remaining:.0f}s | "
            f"Last: {email[:50]} -> {status}"
        )

    print("\nValidating...")
    results = asyncio.run(
        validate_batch(
            email_rows,
            workers=args.workers,
            do_smtp=not args.no_smtp,
            smtp_timeout=args.smtp_timeout,
            dns_timeout=args.dns_timeout,
            progress_callback=progress,
            max_smtp_concurrency_per_domain=args.max_smtp_per_domain,
            smtp_retry_attempts=args.smtp_retries,
            smtp_retry_backoff_seconds=args.smtp_retry_backoff,
            smtp_min_interval_seconds=args.smtp_min_interval,
        )
    )

    elapsed = time.time() - start
    rate = len(email_rows) / elapsed if elapsed > 0 else 0
    print(f"\nDone in {elapsed:.1f}s ({rate:.1f} emails/s)")

    stats = {"valid": 0, "invalid": 0, "accept_all": 0, "unknown": 0}
    reasons: dict[str, int] = {}
    for result in results:
        stats[result.status] = stats.get(result.status, 0) + 1
        if result.failure_reason:
            reasons[result.failure_reason] = reasons.get(result.failure_reason, 0) + 1

    print("\nResults:")
    for status, count in sorted(stats.items()):
        pct = count / len(results) * 100
        print(f"  {status}: {count} ({pct:.1f}%)")
    if reasons:
        print("\nFailure reasons:")
        for reason, count in sorted(reasons.items()):
            print(f"  {reason}: {count}")

    output_path = args.output or f"{input_path.with_suffix('')}-validated.csv"
    write_results_csv(results, output_path)
    print(f"\nWritten to: {output_path}")
    return 0


def _load_rows(path: str, email_column: str | None):
    try:
        return read_csv_rows(path, email_column=email_column)
    except ValueError as exc:
        raise SystemExit(f"Error: {exc}\nUse --email-column to specify the column name manually.") from exc


def _print_single_result(result) -> None:
    print(f"\n{'=' * 50}")
    print(f"  Email:      {result.email}")
    print(f"  Status:     {result.status} (score: {result.score})")
    print(f"  Reason:     {result.failure_reason or 'n/a'}")
    print(f"  Syntax:     {'yes' if result.regexp else 'no'}")
    print(f"  Gibberish:  {'yes' if result.gibberish else 'no'}")
    print(f"  Disposable: {'yes' if result.disposable else 'no'}")
    print(f"  Webmail:    {'yes' if result.webmail else 'no'}")
    print(f"  Role-based: {'yes' if result.role_based else 'no'}")
    print(f"  MX:         {'yes' if result.mx_records else 'no'}")
    print(f"  SMTP:       {'yes' if result.smtp_check else 'no'} ({result.smtp_server or 'n/a'})")
    print(f"  Accept-all: {'yes' if result.accept_all else 'no'}")
    print(f"  Blocked:    {'yes' if result.block else 'no'}")
    if result.error:
        print(f"  Error:      {result.error}")
    print(f"{'=' * 50}")
