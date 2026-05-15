"""
Email Validator — free local email verification.
Syntax → MX → SMTP → disposable → role-based → score.
"""
from .batch import ValidationResult, validate_batch, validate_single
from .dns_check import check_mx
from .smtp_check import verify_smtp
from .disposable import is_disposable, is_role_based, is_webmail
from .syntax import validate_syntax

__version__ = "1.1.0"
__all__ = [
    "ValidationResult",
    "validate_batch",
    "validate_single",
    "validate_syntax",
    "check_mx",
    "verify_smtp",
    "is_disposable",
    "is_role_based",
    "is_webmail",
]
