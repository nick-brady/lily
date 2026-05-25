"""Auth challenge dispatch.

`Messenger` is the interface; `ConsoleMessenger` is the dev implementation
used in PR 1. Real Resend (email) and Twilio (SMS) implementations land in
a follow-up.

The contract: given a verified-identifier (email or e164 phone), an OTP
code, and a magic-link URL, deliver the credentials so the user can verify.
For email, both the code and the link are useful. For SMS, only the code
is sent (links over SMS are jankier).
"""
from __future__ import annotations

import sys
from abc import ABC, abstractmethod

from models import AuthIdentifierKind


class Messenger(ABC):
    @abstractmethod
    def send_challenge(
        self,
        identifier: str,
        identifier_kind: AuthIdentifierKind,
        code: str,
        magic_link_url: str,
    ) -> None: ...


class ConsoleMessenger(Messenger):
    """Prints credentials to stdout. Dev only.

    We deliberately bypass the `logging` framework here — uvicorn's
    logging config swallows our custom logger and there's no value in
    fighting that for a dev-only utility. Plain `print` to stdout
    survives every configuration and shows up cleanly in
    `docker compose logs backend`.
    """

    def send_challenge(
        self,
        identifier: str,
        identifier_kind: AuthIdentifierKind,
        code: str,
        magic_link_url: str,
    ) -> None:
        banner = "=" * 72
        if identifier_kind is AuthIdentifierKind.email:
            body = (
                f"\n{banner}\n"
                f"  EMAIL MAGIC LINK for {identifier}\n"
                f"  Code: {code}\n"
                f"  Link: {magic_link_url}\n"
                f"{banner}"
            )
        else:
            body = (
                f"\n{banner}\n"
                f"  SMS OTP for {identifier}\n"
                f"  Code: {code}\n"
                f"{banner}"
            )
        print(body, flush=True, file=sys.stderr)
