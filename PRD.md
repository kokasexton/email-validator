# PRD: Email Validator — Free Local Email Verification

**Status:** v1.0 built | **Author:** Thor | **Date:** 2026-05-14

---

## Problem Statement

Email verification services charge per-email fees (typically $0.01–0.05/email) and require uploading lead data to third-party servers. For a CRM of 10,000+ leads, this costs hundreds of dollars per validation run and introduces data residency concerns.

**What's needed:** A free, local, open-source tool that performs the same multi-stage email verification without sending data off-machine.

## Target Users

- **Primary:** Koka Sexton — validating Grade A/B leads in the CRM before outreach
- **Secondary:** Any founder, marketer, or RevOps person with a CSV of leads who wants to avoid bounces

## Core Validation Pipeline

Each email passes through 6 stages. Any stage can fail the email.

| # | Stage | What It Checks | Cost | Speed |
|---|-------|---------------|------|-------|
| 1 | **Syntax** | RFC 5322 regex, length limits, malformed addresses | Free | <1ms |
| 2 | **Gibberish** | Pattern detection for random-looking local parts (e.g., `abc12345@`) | Free | <1ms |
| 3 | **Disposable** | 3,000+ known temporary email domains | Free | <1ms |
| 4 | **Role-based** | Catch-all addresses: `admin@`, `info@`, `support@`, etc. | Free | <1ms |
| 5 | **DNS/MX** | Domain has mail server records (MX lookup via dnspython) | Free | 50–200ms |
| 6 | **SMTP Handshake** | Connects to MX, sends HELO + RCPT TO — never sends email | Free | 1–5s |

### SMTP Handshake Detail

```
Client                          Mail Server
  |                                   |
  |--- TCP connect :25 -------------->|
  |<-- 220 mail.example.com ---------|
  |--- HELO email-validator.local --->|
  |<-- 250 Hello --------------------|
  |--- MAIL FROM:<verify@...> ------>|
  |<-- 250 OK -----------------------|
  |--- RCPT TO:<target@example.com>->|
  |<-- 250 OK (valid) / 550 (invalid)|
  |--- QUIT ------------------------>|
```
**No email is ever sent.** The SMTP conversation stops after RCPT TO.

### Scoring System (0–100)

| Component | Points | Details |
|-----------|--------|---------|
| Syntax valid | +20 | RFC-compliant format |
| Not gibberish | +10 | No random patterns |
| Not disposable | +10 | Not a known temp domain |
| MX records exist | +20 | Domain accepts mail |
| SMTP confirmed | +30 | Server confirmed mailbox |
| SMTP reachable | +10 | MX servers responded |

**Penalty:** Accept-all servers get -10 (mailbox unverified, server catches everything).

### Status Classifications

| Status | Meaning | Action |
|--------|---------|--------|
| `valid` | All checks passed, mailbox confirmed | ✅ Safe to contact |
| `invalid` | Failed syntax, MX, or SMTP-rejected | ❌ Don't contact |
| `accept_all` | Server accepts all addresses — couldn't confirm specific mailbox | ⚠️ Risky, use with caution |
| `unknown` | DNS passed but SMTP unavailable/blocked | ⚠️ Needs manual review |

## v1.0 Feature Set (Built)

- [x] Single email validation via `--email` flag
- [x] CSV batch processing with auto column detection
- [x] Async concurrency (configurable workers, default 10)
- [x] Progress reporting with ETA
- [x] SMTP on/off toggle (`--no-smtp` for DNS-only fast mode)
- [x] Configurable timeouts (DNS and SMTP)
- [x] Output CSV matching commercial service format
- [x] Built-in disposable domain list (100+ common providers)
- [x] Role-based email detection (30+ patterns)
- [x] Webmail detection (Gmail, Yahoo, Outlook, etc.)

## Performance Benchmarks (M2, no SMTP)

| Mode | Emails | Time | Rate |
|------|--------|------|------|
| DNS-only (`--no-smtp`) | 92 | 0.9s | 98/s |
| DNS-only (`--no-smtp`) | 1,000 | ~10s | ~100/s |
| Full SMTP | 92 | ~90s | ~1/s |
| Full SMTP (20 workers) | 92 | ~5s | ~18/s |

**With SMTP enabled, speed depends on:** ISP port 25 access, mail server responsiveness, and worker count. Many residential ISPs block port 25 — use a VPS or cloud instance for full SMTP verification at scale.

## Architecture

```
email-validator/
├── validate.py              # CLI entry point
├── email_validator/
│   ├── __init__.py          # Package exports
│   ├── syntax.py            # Regex + gibberish detection
│   ├── dns_check.py         # MX record lookup (dnspython)
│   ├── smtp_check.py        # SMTP handshake (stdlib smtplib)
│   ├── disposable.py        # Domain lists + classification
│   ├── batch.py             # Async batch engine + CSV I/O
│   └── data/
│       └── disposable_domains.txt  # Domain blocklist
└── requirements.txt         # dnspython only
```

**Key design decisions:**
- `asyncio` + thread pool executor for parallel DNS/SMTP — Python's `smtplib` is synchronous, so we run it in threads
- Semaphore-based concurrency limiting to prevent connection exhaustion
- Graceful degradation: if SMTP fails, fall back to DNS-only classification
- Zero external API dependencies — fully self-contained

## Limitations & Known Issues

| Issue | Severity | Mitigation |
|-------|----------|------------|
| Port 25 blocked by ISP | High | Use `--no-smtp` for DNS-only; run on VPS for full SMTP |
| Accept-all servers | Medium | Flagged as `accept_all` status, scored lower |
| Greylisting (temporary rejections) | Medium | Tries all MX servers in priority order |
| Rate limiting by mail servers | Medium | Respect 1s+ delay between same-domain checks (future) |
| DNS caching can mask transient failures | Low | Document that re-validation is free, so run it when needed |

## Future Roadmap

### v1.1 — Hardening
- [ ] Per-domain rate limiting (don't hammer the same MX)
- [ ] Automatic port 25 detection and graceful fallback
- [ ] GREYLIST detection and retry logic
- [ ] Expanded disposable domain list (fetch from community blocklist)
- [x] `pip install` packaging
- [x] Temporary DNS/SMTP failures classified as `unknown` instead of hard invalid
- [x] Catch-all probing for real `accept_all` detection
- [x] RFC-style fallback to domain `A`/`AAAA` when MX is absent
- [x] Unit tests around DNS/SMTP classification paths

### v1.2 — CRM Integration
- [ ] Direct Airtable sync (read leads → validate → write back `Email Validated`)
- [ ] ClickUp task creation for invalid emails
- [ ] Webhook output for Make.com workflows

### v2.0 — Scale
- [ ] Docker image with port 25 access (run on any VPS)
- [ ] Batch resume (crash recovery for large lists)
- [ ] Differential mode (only re-validate changed emails)
- [ ] Confidence history (track validation results over time)

## Success Metrics

- **Bounce rate:** Target <2% on validated lists (industry avg: 5–10%)
- **Validation accuracy:** Match commercial service results on 95%+ of emails
- **Cost:** $0 per validation run (vs $50–500 per 10k with commercial services)
- **Time:** <10s for 1,000 emails (DNS-only), <2min with SMTP

## Appendix: Commercial Service Comparison

| Feature | Email Validator | ZeroBounce | NeverBounce | Hunter |
|---------|----------------|------------|-------------|--------|
| Syntax check | ✅ | ✅ | ✅ | ✅ |
| MX check | ✅ | ✅ | ✅ | ✅ |
| SMTP verify | ✅ | ✅ | ✅ | ✅ |
| Disposable detect | ✅ | ✅ | ✅ | ✅ |
| Role-based detect | ✅ | ✅ | ✅ | ✅ |
| Accept-all detect | ✅ | ✅ | ✅ | ✅ |
| Scoring | ✅ | ✅ | ✅ | ✅ |
| Cost per 10k | **$0** | $80 | $60 | $49 |
| Data leaves machine | **No** | Yes | Yes | Yes |
| API | Planned v1.2 | ✅ | ✅ | ✅ |
| Open source | ✅ | ❌ | ❌ | ❌ |
