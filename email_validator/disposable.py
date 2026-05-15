"""Disposable email, role-based, and webmail detection."""
import os

# Load built-in disposable domains
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

DISPOSABLE_DOMAINS: set[str] = set()
ROLE_PREFIXES: set[str] = {
    "admin", "info", "support", "sales", "contact", "hello", "help",
    "marketing", "billing", "team", "jobs", "careers", "hr", "service",
    "office", "mail", "postmaster", "abuse", "noreply", "no-reply",
    "webmaster", "hostmaster", "root", "news", "press", "media",
    "accounts", "enquiries", "enquiry", "inquiries", "inquiry",
    "orders", "customerservice", "customer", "cs", "feedback",
    "donotreply", "do-not-reply", "mailer-daemon", "mailer",
}
WEBMAIL_DOMAINS: set[str] = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk",
    "hotmail.com", "hotmail.co.uk", "outlook.com", "live.com",
    "msn.com", "aol.com", "aim.com", "icloud.com", "me.com",
    "mac.com", "protonmail.com", "proton.me", "pm.me",
    "mail.com", "gmx.com", "yandex.com", "yandex.ru",
    "zoho.com", "fastmail.com", "fastmail.fm", "tutanota.com",
    "tuta.io", "hey.com", "duck.com", "inbox.com", "hushmail.com",
    "runbox.com", "mailfence.com", "startmail.com",
    "cock.li", "disroot.org", "riseup.net", "autistici.org",
}


def _load_disposable():
    """Load disposable domains from data file."""
    global DISPOSABLE_DOMAINS
    if DISPOSABLE_DOMAINS:
        return

    path = os.path.join(_DATA_DIR, "disposable_domains.txt")
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip().lower()
                if line and not line.startswith("#"):
                    DISPOSABLE_DOMAINS.add(line)

    # Also add a built-in quick list of the most common ones
    builtin = {
        "mailinator.com", "guerrillamail.com", "tempmail.com",
        "10minutemail.com", "yopmail.com", "throwaway.email",
        "sharklasers.com", "trashmail.com", "maildrop.cc",
        "harakirimail.com", "dispostable.com", "getnada.com",
        "tempmail.net", "fakeinbox.com", "temp-mail.org",
        "guerrillamail.org", "guerrillamail.net", "guerrillamail.biz",
        "mailcatch.com", "spamgourmet.com", "spam4.me",
        "moakt.com", "mytemp.email", "emailondeck.com",
        "tempinbox.com", "throwaway.email", "smailpro.com",
        "tempmail.ninja", "burnermail.io", "emailfake.com",
    }
    DISPOSABLE_DOMAINS.update(builtin)


def is_disposable(email: str) -> bool:
    """Check if the email domain is a known disposable provider."""
    _load_disposable()
    domain = email.rsplit("@", 1)[-1].lower()
    return domain in DISPOSABLE_DOMAINS


def is_role_based(email: str) -> bool:
    """Check if the email is a role-based address (admin@, info@, etc.)."""
    local = email.rsplit("@", 1)[0].lower()
    # Exact match
    if local in ROLE_PREFIXES:
        return True
    # Also check prefixed variants: info-uk@, admin.london@
    base = local.split("-")[0].split(".")[0].split("+")[0].split("_")[0]
    return base in ROLE_PREFIXES


def is_webmail(email: str) -> bool:
    """Check if the email domain is a consumer webmail provider."""
    domain = email.rsplit("@", 1)[-1].lower()
    return domain in WEBMAIL_DOMAINS
