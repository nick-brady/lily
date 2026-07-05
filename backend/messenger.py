"""Auth challenge + invitation dispatch.

`Messenger` is the interface. `ConsoleMessenger` prints credentials to the
backend log (the dev default); `ResendMessenger` (email) and
`TwilioMessenger` (SMS) are the real providers, each gated on its own env
vars — see `get_messenger()`. Channels fall back independently, so a
partly-configured environment still works and zero config keeps today's
console behavior.

Two contracts:
- `send_challenge`: given a verified identifier (email or e164 phone), an
  OTP code, and a magic-link URL, deliver the credentials so the user can
  verify. For email, both the code and the link are useful. For SMS, only
  the code is sent (links over SMS are jankier).
- `send_invitation`: given an identifier and an already-built invite URL,
  tell someone they've been invited to a birth page. Unlike the OTP flow,
  SMS carries the link too — there's no code to fall back on, the link is
  the whole point.
"""
from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod

import httpx

from models import AuthIdentifierKind

_REQUEST_TIMEOUT = 10.0

_RESEND_URL = "https://api.resend.com/emails"
# Resend's sandbox sender — works before a domain is verified, so a fresh
# deploy can send real email with just an API key.
_RESEND_DEFAULT_FROM = "Arrival Story <onboarding@resend.dev>"

_TWILIO_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


class ChallengeDeliveryError(Exception):
    """The provider couldn't deliver the message — worth a 503, not a 500."""


class Messenger(ABC):
    @abstractmethod
    def send_challenge(
        self,
        identifier: str,
        identifier_kind: AuthIdentifierKind,
        code: str,
        magic_link_url: str,
    ) -> None: ...

    @abstractmethod
    def send_invitation(
        self,
        identifier: str,
        identifier_kind: AuthIdentifierKind,
        *,
        inviter_name: str,
        birth_name: str,
        role_label: str,
        invite_url: str,
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

    def send_invitation(
        self,
        identifier: str,
        identifier_kind: AuthIdentifierKind,
        *,
        inviter_name: str,
        birth_name: str,
        role_label: str,
        invite_url: str,
    ) -> None:
        banner = "=" * 72
        channel = "EMAIL" if identifier_kind is AuthIdentifierKind.email else "SMS"
        body = (
            f"\n{banner}\n"
            f"  {channel} INVITE for {identifier}\n"
            f"  {inviter_name} invited you as a {role_label} to {birth_name}'s page\n"
            f"  Link: {invite_url}\n"
            f"{banner}"
        )
        print(body, flush=True, file=sys.stderr)


def _email_html(code: str, magic_link_url: str) -> str:
    """Minimal, inline-styled, on-brand: the code big, one button, the
    expiry note. Every client renders this."""
    return f"""\
<div style="font-family: Georgia, 'Times New Roman', serif; max-width: 420px;
            margin: 0 auto; padding: 32px 24px; color: #44364a;">
  <p style="font-size: 14px; letter-spacing: 2px; color: #a21caf;
            text-transform: uppercase; margin: 0 0 16px;">Arrival Story</p>
  <p style="font-size: 16px; margin: 0 0 20px;">Here's your sign-in code:</p>
  <p style="font-size: 40px; letter-spacing: 8px; font-weight: bold;
            margin: 0 0 24px;">{code}</p>
  <a href="{magic_link_url}"
     style="display: inline-block; background: #a21caf; color: #ffffff;
            text-decoration: none; padding: 12px 24px; border-radius: 8px;
            font-size: 16px;">Sign in</a>
  <p style="font-size: 13px; color: #6d6076; margin: 24px 0 0;">
    The code and link expire in 15 minutes. If you didn't request this,
    you can ignore it.
  </p>
</div>
"""


def _invitation_email_html(inviter_name: str, birth_name: str, role_label: str, invite_url: str) -> str:
    """Same visual identity as the sign-in email, different content: no
    code, just the invite and a single button to the page."""
    return f"""\
<div style="font-family: Georgia, 'Times New Roman', serif; max-width: 420px;
            margin: 0 auto; padding: 32px 24px; color: #44364a;">
  <p style="font-size: 14px; letter-spacing: 2px; color: #a21caf;
            text-transform: uppercase; margin: 0 0 16px;">Arrival Story</p>
  <p style="font-size: 16px; margin: 0 0 24px;">
    {inviter_name} invited you as a {role_label} to {birth_name}'s page.
  </p>
  <a href="{invite_url}"
     style="display: inline-block; background: #a21caf; color: #ffffff;
            text-decoration: none; padding: 12px 24px; border-radius: 8px;
            font-size: 16px;">View the page</a>
  <p style="font-size: 13px; color: #6d6076; margin: 24px 0 0;">
    If you weren't expecting this, you can ignore it.
  </p>
</div>
"""


class ResendMessenger(Messenger):
    """Email via Resend's REST API (one POST, no SDK)."""

    def __init__(
        self,
        *,
        api_key: str,
        from_address: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._from = from_address or _RESEND_DEFAULT_FROM
        self._client = client or httpx.Client(timeout=_REQUEST_TIMEOUT)
        self._client.headers.update({"Authorization": f"Bearer {api_key}"})

    def send_challenge(
        self,
        identifier: str,
        identifier_kind: AuthIdentifierKind,
        code: str,
        magic_link_url: str,
    ) -> None:
        try:
            resp = self._client.post(
                _RESEND_URL,
                json={
                    "from": self._from,
                    "to": [identifier],
                    "subject": f"Your Arrival Story sign-in code: {code}",
                    "html": _email_html(code, magic_link_url),
                    "text": (
                        f"Your Arrival Story sign-in code: {code}\n\n"
                        f"Or sign in with this link: {magic_link_url}\n\n"
                        "The code and link expire in 15 minutes."
                    ),
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ChallengeDeliveryError(f"resend: {exc}") from exc

    def send_invitation(
        self,
        identifier: str,
        identifier_kind: AuthIdentifierKind,
        *,
        inviter_name: str,
        birth_name: str,
        role_label: str,
        invite_url: str,
    ) -> None:
        try:
            resp = self._client.post(
                _RESEND_URL,
                json={
                    "from": self._from,
                    "to": [identifier],
                    "subject": f"{inviter_name} invited you to {birth_name}'s page",
                    "html": _invitation_email_html(
                        inviter_name, birth_name, role_label, invite_url
                    ),
                    "text": (
                        f"{inviter_name} invited you as a {role_label} to "
                        f"{birth_name}'s page.\n\n{invite_url}"
                    ),
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ChallengeDeliveryError(f"resend: {exc}") from exc


class TwilioMessenger(Messenger):
    """SMS via Twilio's REST API (one form-encoded POST, no SDK)."""

    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        from_number: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._url = _TWILIO_URL.format(sid=account_sid)
        self._from = from_number
        self._client = client or httpx.Client(
            timeout=_REQUEST_TIMEOUT, auth=(account_sid, auth_token)
        )

    def send_challenge(
        self,
        identifier: str,
        identifier_kind: AuthIdentifierKind,
        code: str,
        magic_link_url: str,
    ) -> None:
        try:
            resp = self._client.post(
                self._url,
                data={
                    "To": identifier,
                    "From": self._from,
                    "Body": f"Arrival Story sign-in code: {code} — expires in 15 minutes.",
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ChallengeDeliveryError(f"twilio: {exc}") from exc

    def send_invitation(
        self,
        identifier: str,
        identifier_kind: AuthIdentifierKind,
        *,
        inviter_name: str,
        birth_name: str,
        role_label: str,
        invite_url: str,
    ) -> None:
        try:
            resp = self._client.post(
                self._url,
                data={
                    "To": identifier,
                    "From": self._from,
                    "Body": (
                        f"{inviter_name} invited you as a {role_label} to "
                        f"{birth_name}'s page on Arrival Story: {invite_url}"
                    ),
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ChallengeDeliveryError(f"twilio: {exc}") from exc


class RoutingMessenger(Messenger):
    """Delegates by identifier kind — email and SMS providers are configured
    (and fall back) independently."""

    def __init__(self, *, email: Messenger, phone: Messenger) -> None:
        self._email = email
        self._phone = phone

    def send_challenge(
        self,
        identifier: str,
        identifier_kind: AuthIdentifierKind,
        code: str,
        magic_link_url: str,
    ) -> None:
        channel = (
            self._email
            if identifier_kind is AuthIdentifierKind.email
            else self._phone
        )
        channel.send_challenge(identifier, identifier_kind, code, magic_link_url)

    def send_invitation(
        self,
        identifier: str,
        identifier_kind: AuthIdentifierKind,
        *,
        inviter_name: str,
        birth_name: str,
        role_label: str,
        invite_url: str,
    ) -> None:
        channel = (
            self._email
            if identifier_kind is AuthIdentifierKind.email
            else self._phone
        )
        channel.send_invitation(
            identifier,
            identifier_kind,
            inviter_name=inviter_name,
            birth_name=birth_name,
            role_label=role_label,
            invite_url=invite_url,
        )


def get_messenger() -> Messenger:
    """The configured messenger. Each channel is real when its env vars are
    set and console otherwise (same gating ethos as fulfillment.get_adapter),
    so dev needs zero config and prod can bring up email before SMS."""
    resend_key = os.getenv("RESEND_API_KEY")
    email: Messenger = (
        ResendMessenger(api_key=resend_key, from_address=os.getenv("RESEND_FROM"))
        if resend_key
        else ConsoleMessenger()
    )

    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM")
    phone: Messenger = (
        TwilioMessenger(account_sid=sid, auth_token=token, from_number=from_number)
        if sid and token and from_number
        else ConsoleMessenger()
    )

    return RoutingMessenger(email=email, phone=phone)
