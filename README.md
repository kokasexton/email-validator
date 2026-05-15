# Email Validator

Local email verification that keeps lead data on your machine and covers the practical pipeline most paid tools use:

`Syntax -> Gibberish -> Disposable -> Role -> DNS/MX -> SMTP handshake`

It supports two operating modes:

- `DNS-only`: very fast, no port 25 dependency, returns `unknown` for DNS-valid addresses because the mailbox was not confirmed
- `Full SMTP`: slower, attempts mailbox verification and catch-all detection without sending mail

## What changed in this hardening pass

- Added a proper package entrypoint: `email-validator`
- Added DNS fallback to the bare domain when no MX record exists
- Distinguished temporary DNS/SMTP failures from permanent invalid domains
- Implemented actual catch-all probing for `accept_all`
- Removed an unused dependency
- Added network-free unit tests around the critical branches

## Quick Start

### Option 1: run directly from the repo

```bash
cd ~/projects/email-validator
source .venv/bin/activate
pip install -r requirements.txt
python validate.py leads.csv -o validated.csv -w 20
```

### Option 2: install the CLI

```bash
cd ~/projects/email-validator
source .venv/bin/activate
pip install -e .
email-validator leads.csv -o validated.csv -w 20
```

## Usage

```bash
# Single email
python validate.py --email test@example.com

# Single email via installed CLI
email-validator --email test@example.com

# CSV file (auto-detects: email, business_email, Business Email, Email, e-mail)
email-validator leads.csv

# Specify output file
email-validator leads.csv -o validated.csv

# Higher concurrency
email-validator leads.csv -w 20

# DNS-only mode
email-validator leads.csv --no-smtp

# Custom timeouts
email-validator leads.csv --dns-timeout 3 --smtp-timeout 8
```

## Input expectations

- CSV input must include a header row
- Supported email column aliases:
  - `email`
  - `business_email`
  - `Business Email`
  - `Email`
  - `e-mail`
  - `email address`
- Use `--email-column` if your file uses a non-standard header

## Status meanings

| Status | Meaning | Action |
|---|---|---|
| `valid` | Mailbox accepted by the server | Safe to use |
| `invalid` | Syntax failed, domain is invalid, or mailbox was explicitly rejected | Drop or fix |
| `accept_all` | Server accepted the target and also accepted a random fake mailbox | Treat as risky |
| `unknown` | DNS or SMTP could not confirm deliverability | Retry later or use a host with port 25 access |

## Reliability notes

### DNS

- If a domain has no MX record, the validator now falls back to the domain's `A` or `AAAA` record per SMTP convention
- Timeouts and nameserver failures are treated as temporary verification failures, not automatic invalids
- MX lookups are cached in-process to avoid repeating the same DNS work across large lists

### SMTP

- SMTP mode only performs a handshake and `RCPT TO`; it never sends a message body
- Catch-all detection is now real: after a mailbox is accepted, the tool probes a guaranteed-random mailbox on the same domain
- If your ISP blocks outbound port 25, expect many `unknown` results in SMTP mode

## Output columns

The output CSV includes:

- `email`
- `status`
- `regexp`
- `gibberish`
- `disposable`
- `webmail`
- `mx_records`
- `smtp_server`
- `smtp_check`
- `accept_all`
- `block`
- `score`
- `role_based`

## Development

### Run tests

```bash
cd ~/projects/email-validator
source .venv/bin/activate
python -m unittest discover -s tests -v
```

### Project layout

```text
email-validator/
├── validate.py
├── pyproject.toml
├── email_validator/
│   ├── cli.py
│   ├── batch.py
│   ├── dns_check.py
│   ├── smtp_check.py
│   ├── syntax.py
│   ├── disposable.py
│   └── data/
└── tests/
```

## Practical guidance

- Use `--no-smtp` when you want speed, cheap list triage, or you are running on a laptop/network that blocks port 25
- Use full SMTP on a VPS when the final mailbox-level decision matters
- Do not blast massive batches against a single domain with very high worker counts; concurrency is configurable, but mailbox hosts still rate-limit
