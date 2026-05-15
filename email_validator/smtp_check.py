"""SMTP handshake verification. Connects to MX, says HELO, checks RCPT TO."""
import asyncio
import secrets
import smtplib
import socket


def _decode_smtp_message(message) -> str:
    if isinstance(message, bytes):
        return message.decode(errors="replace")
    return str(message)


def _probe_accept_all(smtp: smtplib.SMTP, domain: str) -> bool:
    """Probe a guaranteed-random mailbox to detect catch-all domains."""
    probe_local = f"definitely-not-real-{secrets.token_hex(8)}"
    probe_address = f"{probe_local}@{domain}"
    code, _ = smtp.rcpt(probe_address)
    return code in (250, 251)


def verify_smtp_sync(email: str, mx_hosts: list[str], timeout: float = 10.0) -> dict:
    """
    Verify email via SMTP handshake.
    Returns {smtp_check, smtp_server, accept_all, block, error, temporary_failure}.
    """
    if not mx_hosts:
        return {
            "smtp_check": False,
            "smtp_server": "",
            "accept_all": False,
            "block": True,
            "temporary_failure": True,
            "error": "No MX hosts",
        }

    error = ""
    domain = email.rsplit("@", 1)[-1]
    for mx in mx_hosts:
        smtp = None
        try:
            # Connect with timeout
            smtp = smtplib.SMTP(timeout=timeout)
            smtp.connect(mx, 25)

            # HELO
            code, msg = smtp.helo("email-validator.local")
            if code >= 500:
                # Try EHLO
                code, msg = smtp.ehlo("email-validator.local")
            if code >= 500:
                smtp.quit()
                continue

            # MAIL FROM (use a generic return path)
            code, msg = smtp.mailfrom("verify@email-validator.local")
            if code >= 500:
                smtp.quit()
                continue

            # RCPT TO — this is the key check
            code, msg = smtp.rcpt(email)
            if code in (250, 251):
                accept_all = _probe_accept_all(smtp, domain)
                smtp.quit()
                return {
                    "smtp_check": True,
                    "smtp_server": mx,
                    "accept_all": accept_all,
                    "block": False,
                    "temporary_failure": False,
                    "error": "",
                }
            if code in (550, 551, 552, 553):
                smtp.quit()
                return {
                    "smtp_check": True,
                    "smtp_server": mx,
                    "accept_all": False,
                    "block": False,
                    "temporary_failure": False,
                    "error": f"Rejected: {code} {_decode_smtp_message(msg)}",
                }
            smtp.quit()

            if code in (450, 451, 452):
                # Temporary failure — try next MX
                error = f"Temp fail: {code} {_decode_smtp_message(msg)}"
                continue

            error = f"Unexpected: {code} {_decode_smtp_message(msg)}"
            continue

        except (socket.timeout, socket.error, ConnectionRefusedError, OSError) as e:
            error = str(e)
            continue
        except smtplib.SMTPException as e:
            error = str(e)
            continue
        except Exception as e:
            error = str(e)
            continue
        finally:
            if smtp is not None:
                try:
                    smtp.quit()
                except Exception:
                    pass

    # If we tried all MX hosts and none confirmed, but also none explicitly rejected...
    return {
        "smtp_check": False,
        "smtp_server": mx_hosts[0] if mx_hosts else "",
        "accept_all": False,
        "block": True,
        "temporary_failure": True,
        "error": f"All MX failed: {error}" if error else "All MX failed",
    }


async def verify_smtp(email: str, mx_hosts: list[str], timeout: float = 10.0) -> dict:
    """Async SMTP verification wrapper."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, verify_smtp_sync, email, mx_hosts, timeout)
