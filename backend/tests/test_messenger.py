"""Messenger tests — the Resend/Twilio senders against mocked httpx
transports (no real provider calls), the env-gated factory, and the
kind-based routing."""
from __future__ import annotations

from urllib.parse import unquote_plus

import httpx
import pytest

import messenger
from messenger import (
    ChallengeDeliveryError,
    ConsoleMessenger,
    ResendMessenger,
    RoutingMessenger,
    TwilioMessenger,
    get_messenger,
)
from models import AuthIdentifierKind

_LINK = "http://localhost:3000/auth/verify?token=abc.def"


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


# ── Resend ────────────────────────────────────────────────────────────────


def test_resend_sends_code_only():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["auth"] = req.headers.get("authorization")
        seen["body"] = req.read().decode()
        return httpx.Response(200, json={"id": "email_123"})

    m = ResendMessenger(api_key="re_test", client=_client(handler))
    m.send_challenge("janet@example.com", AuthIdentifierKind.email, "312804")

    assert seen["url"] == "https://api.resend.com/emails"
    assert seen["auth"] == "Bearer re_test"
    assert "janet@example.com" in seen["body"]
    assert "312804" in seen["body"]
    # magic links are retired — no sign-in URL in the email
    assert "auth/verify" not in seen["body"]
    # sandbox default sender until a domain is verified
    assert "onboarding@resend.dev" in seen["body"]


def test_resend_failure_raises_delivery_error():
    m = ResendMessenger(
        api_key="re_bad",
        client=_client(lambda r: httpx.Response(401, json={"message": "nope"})),
    )
    with pytest.raises(ChallengeDeliveryError):
        m.send_challenge("j@example.com", AuthIdentifierKind.email, "1")


def test_resend_sends_invitation():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = req.read().decode()
        return httpx.Response(200, json={"id": "email_123"})

    m = ResendMessenger(api_key="re_test", client=_client(handler))
    m.send_invitation(
        "janet@example.com",
        AuthIdentifierKind.email,
        inviter_name="Sarah",
        birth_name="Lily",
        role_label="family member",
        invite_url=_LINK,
    )

    assert "janet@example.com" in seen["body"]
    assert "Sarah" in seen["body"]
    assert "Lily" in seen["body"]
    assert _LINK in seen["body"]


def test_resend_invitation_failure_raises_delivery_error():
    m = ResendMessenger(
        api_key="re_bad",
        client=_client(lambda r: httpx.Response(401, json={"message": "nope"})),
    )
    with pytest.raises(ChallengeDeliveryError):
        m.send_invitation(
            "j@example.com",
            AuthIdentifierKind.email,
            inviter_name="Sarah",
            birth_name="Lily",
            role_label="family member",
            invite_url=_LINK,
        )


# ── Twilio ────────────────────────────────────────────────────────────────


def test_twilio_refuses_signin_codes():
    # Auth is email-only — the SMS channel must never carry sign-in codes.
    m = TwilioMessenger(
        account_sid="AC_test",
        auth_token="tok",
        from_number="+15550001111",
        client=_client(lambda r: httpx.Response(201, json={"sid": "SM123"})),
    )
    with pytest.raises(ChallengeDeliveryError):
        m.send_challenge("+15557772222", AuthIdentifierKind.phone, "312804")


def test_twilio_sends_notify_optin_confirmation():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["body"] = req.read().decode()
        return httpx.Response(201, json={"sid": "SM123"})

    m = TwilioMessenger(
        account_sid="AC_test",
        auth_token="tok",
        from_number="+15550001111",
        client=_client(handler),
    )
    m.send_notify_optin("+15557772222")

    assert seen["url"].endswith("/Accounts/AC_test/Messages.json")
    assert "To=%2B15557772222" in seen["body"]
    assert "From=%2B15550001111" in seen["body"]
    body = unquote_plus(seen["body"])
    # carrier rules: the consent confirmation must deliver STOP language
    assert "STOP" in body
    assert "Birth updates only" in body


def test_notify_optin_failure_raises_delivery_error():
    m = TwilioMessenger(
        account_sid="AC_x",
        auth_token="tok",
        from_number="+1555",
        client=_client(lambda r: httpx.Response(400, json={"message": "bad To"})),
    )
    with pytest.raises(ChallengeDeliveryError):
        m.send_notify_optin("+1999")


def test_twilio_basic_auth_applied_on_default_client():
    # the default client carries (sid, token) basic auth
    m = TwilioMessenger(account_sid="AC_x", auth_token="tok", from_number="+1555")
    assert m._client.auth is not None


def test_twilio_sends_invitation_with_link():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = req.read().decode()
        return httpx.Response(201, json={"sid": "SM123"})

    m = TwilioMessenger(
        account_sid="AC_test",
        auth_token="tok",
        from_number="+15550001111",
        client=_client(handler),
    )
    m.send_invitation(
        "+15557772222",
        AuthIdentifierKind.phone,
        inviter_name="Sarah",
        birth_name="Lily",
        role_label="co-parent",
        invite_url=_LINK,
    )

    assert "To=%2B15557772222" in seen["body"]
    assert "Sarah" in seen["body"]
    # unlike the OTP SMS, the invitation SMS does carry the link — there's
    # no code to fall back on
    assert _LINK in unquote_plus(seen["body"])


def test_twilio_invitation_failure_raises_delivery_error():
    m = TwilioMessenger(
        account_sid="AC_x",
        auth_token="tok",
        from_number="+1555",
        client=_client(lambda r: httpx.Response(400, json={"message": "bad To"})),
    )
    with pytest.raises(ChallengeDeliveryError):
        m.send_invitation(
            "+1999",
            AuthIdentifierKind.phone,
            inviter_name="Sarah",
            birth_name="Lily",
            role_label="co-parent",
            invite_url=_LINK,
        )


# ── Routing + factory ─────────────────────────────────────────────────────


class _Recorder(ConsoleMessenger):
    def __init__(self):
        self.calls = []
        self.invitation_calls = []
        self.optin_calls = []

    def send_challenge(self, identifier, identifier_kind, code):
        self.calls.append(identifier_kind)

    def send_notify_optin(self, phone):
        self.optin_calls.append(phone)

    def send_invitation(self, identifier, identifier_kind, **kwargs):
        self.invitation_calls.append(identifier_kind)


def test_routing_sends_challenges_to_email_channel_only():
    email, phone = _Recorder(), _Recorder()
    r = RoutingMessenger(email=email, phone=phone)
    r.send_challenge("j@example.com", AuthIdentifierKind.email, "1")
    assert email.calls == [AuthIdentifierKind.email]
    assert phone.calls == []


def test_routing_sends_notify_optin_to_phone_channel():
    email, phone = _Recorder(), _Recorder()
    r = RoutingMessenger(email=email, phone=phone)
    r.send_notify_optin("+15557772222")
    assert phone.optin_calls == ["+15557772222"]
    assert email.optin_calls == []


def test_routing_delegates_invitations_by_kind():
    email, phone = _Recorder(), _Recorder()
    r = RoutingMessenger(email=email, phone=phone)
    r.send_invitation(
        "j@example.com",
        AuthIdentifierKind.email,
        inviter_name="Sarah",
        birth_name="Lily",
        role_label="family member",
        invite_url=_LINK,
    )
    r.send_invitation(
        "+1555",
        AuthIdentifierKind.phone,
        inviter_name="Sarah",
        birth_name="Lily",
        role_label="co-parent",
        invite_url=_LINK,
    )
    assert email.invitation_calls == [AuthIdentifierKind.email]
    assert phone.invitation_calls == [AuthIdentifierKind.phone]


def _channels(m: RoutingMessenger):
    return type(m._email).__name__, type(m._phone).__name__


def test_factory_defaults_to_console(monkeypatch):
    for var in (
        "RESEND_API_KEY",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_FROM",
    ):
        monkeypatch.delenv(var, raising=False)
    assert _channels(get_messenger()) == ("ConsoleMessenger", "ConsoleMessenger")


def test_factory_gates_each_channel_independently(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_x")
    for var in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM"):
        monkeypatch.delenv(var, raising=False)
    assert _channels(get_messenger()) == ("ResendMessenger", "ConsoleMessenger")

    # Twilio needs all three vars — two of three still falls back
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_x")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
    assert _channels(get_messenger())[1] == "ConsoleMessenger"
    monkeypatch.setenv("TWILIO_FROM", "+1555")
    assert _channels(get_messenger()) == ("ResendMessenger", "TwilioMessenger")
