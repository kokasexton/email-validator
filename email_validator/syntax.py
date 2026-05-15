"""Syntax validation: RFC-compliant regex + common pattern detection."""
import re

# RFC 5322 simplified — catches 99.9% of real-world emails
EMAIL_RE = re.compile(
    r"^(?:[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r'|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")'
    r"@(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)"
    r"$"
)

# Patterns that suggest gibberish
GIBBERISH_PATTERNS = [
    re.compile(r"^[a-z]{1,3}\d{4,}@", re.I),           # abc12345@
    re.compile(r"^test\d*@", re.I),                     # test123@
    re.compile(r"^[a-z]{1,2}\d{6,}@", re.I),           # ab123456@
    re.compile(r"^[a-z]{20,}@", re.I),                  # verylongrandomstring@
    re.compile(r"@[a-z0-9]{30,}\.", re.I),              # @verylongdomain.
    re.compile(r"^[a-z]+\.\d{3,}@", re.I),              # name.123456@
]


def validate_syntax(email: str) -> dict:
    """Check email syntax. Returns {valid, regexp, gibberish}."""
    if not email or "@" not in email:
        return {"valid": False, "regexp": False, "gibberish": True}

    is_valid = bool(EMAIL_RE.match(email))
    is_gibberish = any(p.search(email) for p in GIBBERISH_PATTERNS)

    # Additional sanity checks
    local, domain = email.rsplit("@", 1)
    if len(local) > 64 or len(domain) > 255:
        is_valid = False
    if ".." in email:
        is_valid = False
    if domain.startswith(".") or domain.endswith("."):
        is_valid = False

    return {
        "valid": is_valid,
        "regexp": is_valid,
        "gibberish": is_gibberish,
    }
