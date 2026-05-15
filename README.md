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

# Safer SMTP pacing for large same-domain lists
email-validator leads.csv --max-smtp-per-domain 2 --smtp-retries 2 --smtp-retry-backoff 1.0
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
- `failure_reason`
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

## VPS install

If you want real SMTP verification at scale, run this on a VPS where outbound port `25` is allowed.

### 1. Provision a Linux VPS

- Recommended: Ubuntu `22.04` or `24.04`
- Minimum practical size: `1 vCPU`, `1 GB RAM`
- Best results: use a provider that does not block outbound SMTP by default, or will remove the block on request

### 2. SSH into the box

```bash
ssh your-user@your-vps-ip
```

### 3. Install system packages

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
```

### 4. Clone the repo

```bash
git clone https://github.com/kokasexton/email-validator.git
cd email-validator
```

### 5. Create the virtualenv and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

### 6. Confirm outbound SMTP is actually possible

This matters more than anything else. If port `25` is blocked, full SMTP mode will mostly return `unknown`.

Quick check:

```bash
python3 - <<'PY'
import socket
sock = socket.socket()
sock.settimeout(5)
try:
    sock.connect(("gmail-smtp-in.l.google.com", 25))
    print("port 25 reachable")
except Exception as exc:
    print(f"port 25 blocked or unreachable: {exc}")
finally:
    sock.close()
PY
```

### 7. Upload your CSV and run the validator

```bash
scp leads.csv your-user@your-vps-ip:~/email-validator/
ssh your-user@your-vps-ip
cd ~/email-validator
source .venv/bin/activate
email-validator leads.csv -o validated.csv -w 20 --max-smtp-per-domain 2
```

### 8. Download the results

```bash
scp your-user@your-vps-ip:~/email-validator/validated.csv .
```

### 9. Optional: run long jobs with `tmux`

```bash
sudo apt install -y tmux
tmux new -s validator
cd ~/email-validator
source .venv/bin/activate
email-validator leads.csv -o validated.csv -w 20
```

Detach with `Ctrl+B`, then `D`.

### 10. Optional: install as a systemd service for recurring runs

Create `/etc/systemd/system/email-validator.service`:

```ini
[Unit]
Description=Email Validator Batch Run
After=network-online.target

[Service]
Type=oneshot
User=your-user
WorkingDirectory=/home/your-user/email-validator
ExecStart=/home/your-user/email-validator/.venv/bin/email-validator /home/your-user/email-validator/leads.csv -o /home/your-user/email-validator/validated.csv -w 20 --max-smtp-per-domain 2

[Install]
WantedBy=multi-user.target
```

Then run:

```bash
sudo systemctl daemon-reload
sudo systemctl start email-validator.service
sudo systemctl status email-validator.service
```

### VPS notes

- Start with `--max-smtp-per-domain 1` or `2` for cold domains to avoid rate-limit pain
- If you see many `smtp_greylisted` or `smtp_connection_failed` results, lower concurrency before you raise it
- If your provider blocks port `25`, this tool is still useful in `--no-smtp` mode, but you lose mailbox-level confirmation

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
