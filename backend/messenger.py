"""Auth challenge + invitation dispatch.

`Messenger` is the interface. `ConsoleMessenger` prints credentials to the
backend log (the dev default); `ResendMessenger` (email) and
`TwilioMessenger` (SMS) are the real providers, each gated on its own env
vars — see `get_messenger()`. Channels fall back independently, so a
partly-configured environment still works and zero config keeps today's
console behavior.

Three contracts:
- `send_challenge`: given a verified email address and an OTP code, deliver
  the code so the user can sign in. Auth is email-only (2026-07-23 auth
  decision) and magic links are retired — the code is the whole message.
- `send_invitation`: given an identifier and an already-built invite URL,
  tell someone they've been invited to a birth page. Invites may still ride
  SMS — that's delivery of a link someone's family member asked us to send,
  not a login channel.
- `send_notify_optin`: confirmation text for the birth-events opt-in. It
  verifies the number is real and delivers the STOP language the consent
  record depends on. Birth events are the only thing SMS ever carries.
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

# Where a person writes when something is wrong. Replies to transactional
# mail land here too. (The mailbox itself is a setup task — see idea.md.)
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "help@arrivalstory.com")


class ChallengeDeliveryError(Exception):
    """The provider couldn't deliver the message — worth a 503, not a 500."""


class Messenger(ABC):
    @abstractmethod
    def send_challenge(
        self,
        identifier: str,
        identifier_kind: AuthIdentifierKind,
        code: str,
    ) -> None: ...

    @abstractmethod
    def send_notify_optin(self, phone: str) -> None: ...

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
    """Prints credentials to stderr. Dev only.

    Deliberately `print`, not `logging`: these lines carry live sign-in
    codes, invite links, email addresses and phone numbers, and the
    logging tree writes to a file and to the `app_logs` table. Bypassing
    it is what guarantees none of that is ever persisted. `get_messenger`
    only falls back to this class when no real channel is configured.
    """

    def send_challenge(
        self,
        identifier: str,
        identifier_kind: AuthIdentifierKind,
        code: str,
    ) -> None:
        banner = "=" * 72
        body = (
            f"\n{banner}\n"
            f"  SIGN-IN CODE for {identifier}\n"
            f"  Code: {code}\n"
            f"{banner}"
        )
        print(body, flush=True, file=sys.stderr)

    def send_notify_optin(self, phone: str) -> None:
        banner = "=" * 72
        body = (
            f"\n{banner}\n"
            f"  SMS OPT-IN CONFIRMATION for {phone}\n"
            f"  (would send the birth-alerts confirmation text)\n"
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


def _email_html(code: str) -> str:
    """Minimal, inline-styled, on-brand: the code big, the expiry note.
    No links or buttons — a code renders identically everywhere, can't be
    swallowed by a link-rewriting spam filter, and works when the sign-in
    happens on a different device than the inbox (the iPad-at-2am case)."""
    return f"""\
<div style="font-family: Georgia, 'Times New Roman', serif; max-width: 420px;
            margin: 0 auto; padding: 32px 24px; color: #44364a;">
  <p style="font-size: 14px; letter-spacing: 2px; color: #a21caf;
            text-transform: uppercase; margin: 0 0 16px;">Arrival Story</p>
  <p style="font-size: 16px; margin: 0 0 20px;">Here's your sign-in code:</p>
  <p style="font-size: 40px; letter-spacing: 8px; font-weight: bold;
            margin: 0 0 24px;">{code}</p>
  <p style="font-size: 13px; color: #6d6076; margin: 24px 0 0;">
    The code expires in 15 minutes. If you didn't request this,
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
    ) -> None:
        try:
            resp = self._client.post(
                _RESEND_URL,
                json={
                    "from": self._from,
                    "to": [identifier],
                    "subject": f"Your Arrival Story sign-in code: {code}",
                    "html": _email_html(code),
                    "text": (
                        f"Your Arrival Story sign-in code: {code}\n\n"
                        "The code expires in 15 minutes."
                    ),
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ChallengeDeliveryError(f"resend: {exc}") from exc

    def send_notify_optin(self, phone: str) -> None:
        raise ChallengeDeliveryError(
            "resend is an email channel; notify opt-in requires SMS"
        )

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
    ) -> None:
        # Auth is email-only; sign-in codes never ride SMS.
        raise ChallengeDeliveryError("twilio is an SMS channel; sign-in codes go by email")

    def send_notify_optin(self, phone: str) -> None:
        try:
            resp = self._client.post(
                self._url,
                data={
                    "To": phone,
                    "From": self._from,
                    # The consent-confirmation text: verifies the number is
                    # real and delivers the STOP language the TCPA consent
                    # record depends on. Must stay in sync with the sample
                    # registered in the Twilio A2P 10DLC campaign. STOP
                    # itself is handled by Twilio's Advanced Opt-Out.
                    "Body": (
                        "Arrival Story: you're set — we'll text you the moment "
                        "labor begins. Birth updates only, ever. "
                        "Msg & data rates may apply. Reply STOP to opt out."
                    ),
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
                    # The opt-out line is required by carrier (A2P 10DLC)
                    # rules: unlike the OTP, this is a first message to
                    # someone who hasn't personally opted in. It must stay
                    # in sync with the sample registered in the Twilio
                    # campaign. STOP itself is handled by Twilio's
                    # Advanced Opt-Out — no backend handling needed.
                    "Body": (
                        f"{inviter_name} invited you as a {role_label} to "
                        f"{birth_name}'s page on Arrival Story: {invite_url} "
                        "Reply STOP to opt out."
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
    ) -> None:
        # Auth is email-only; the phone channel never carries sign-in codes.
        self._email.send_challenge(identifier, identifier_kind, code)

    def send_notify_optin(self, phone: str) -> None:
        self._phone.send_notify_optin(phone)

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


def send_email(*, to: str, subject: str, html: str, text: str) -> bool:
    """One transactional email, for the things that aren't a sign-in code or
    an invitation (the order receipt). Resend when configured; otherwise a
    dev-only print to stderr — deliberately not the logging tree, since the
    body names the buyer. Returns whether it was accepted; never raises."""
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        banner = "=" * 72
        print(f"\n{banner}\n  EMAIL to {to}\n  {subject}\n\n{text}\n{banner}", flush=True, file=sys.stderr)
        return True
    try:
        resp = httpx.post(
            _RESEND_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": os.getenv("RESEND_FROM") or _RESEND_DEFAULT_FROM,
                "to": [to],
                "reply_to": SUPPORT_EMAIL,
                "subject": subject,
                "html": html,
                "text": text,
            },
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return True
    except httpx.HTTPError:
        return False


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
