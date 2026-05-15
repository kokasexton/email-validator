#!/usr/bin/env python3
"""Backward-compatible script entry point."""
from email_validator.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
