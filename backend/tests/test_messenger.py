"""Messenger tests — the Resend/Twilio senders against mocked httpx
transports (no real provider calls), the env-gated factory, and the
kind-based routing."""
from __future__ import annotations

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


def test_resend_sends_code_and_link():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["auth"] = req.headers.get("authorization")
        seen["body"] = req.read().decode()
        return httpx.Response(200, json={"id": "email_123"})

    m = ResendMessenger(api_key="re_test", client=_client(handler))
    m.send_challenge("janet@example.com", AuthIdentifierKind.email, "312804", _LINK)

    assert seen["url"] == "https://api.resend.com/emails"
    assert seen["auth"] == "Bearer re_test"
    assert "janet@example.com" in seen["body"]
    assert "312804" in seen["body"]
    assert _LINK in seen["body"]
    # sandbox default sender until a domain is verified
    assert "onboarding@resend.dev" in seen["body"]


def test_resend_failure_raises_delivery_error():
    m = ResendMessenger(
        api_key="re_bad",
        client=_client(lambda r: httpx.Response(401, json={"message": "nope"})),
    )
    with pytest.raises(ChallengeDeliveryError):
        m.send_challenge("j@example.com", AuthIdentifierKind.email, "1", _LINK)


# ── Twilio ────────────────────────────────────────────────────────────────


def test_twilio_sends_code():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["auth"] = req.headers.get("authorization", "")
        seen["body"] = req.read().decode()
        return httpx.Response(201, json={"sid": "SM123"})

    m = TwilioMessenger(
        account_sid="AC_test",
        auth_token="tok",
        from_number="+15550001111",
        client=_client(handler),
    )
    m.send_challenge("+15557772222", AuthIdentifierKind.phone, "312804", _LINK)

    assert seen["url"].endswith("/Accounts/AC_test/Messages.json")
    assert "To=%2B15557772222" in seen["body"]
    assert "From=%2B15550001111" in seen["body"]
    assert "312804" in seen["body"]
    # SMS carries the code only, never the link
    assert "token" not in seen["body"]


def test_twilio_basic_auth_applied_on_default_client():
    # the default client carries (sid, token) basic auth
    m = TwilioMessenger(account_sid="AC_x", auth_token="tok", from_number="+1555")
    assert m._client.auth is not None


def test_twilio_failure_raises_delivery_error():
    m = TwilioMessenger(
        account_sid="AC_x",
        auth_token="tok",
        from_number="+1555",
        client=_client(lambda r: httpx.Response(400, json={"message": "bad To"})),
    )
    with pytest.raises(ChallengeDeliveryError):
        m.send_challenge("+1999", AuthIdentifierKind.phone, "1", _LINK)


# ── Routing + factory ─────────────────────────────────────────────────────


class _Recorder(ConsoleMessenger):
    def __init__(self):
        self.calls = []

    def send_challenge(self, identifier, identifier_kind, code, magic_link_url):
        self.calls.append(identifier_kind)


def test_routing_delegates_by_kind():
    email, phone = _Recorder(), _Recorder()
    r = RoutingMessenger(email=email, phone=phone)
    r.send_challenge("j@example.com", AuthIdentifierKind.email, "1", _LINK)
    r.send_challenge("+1555", AuthIdentifierKind.phone, "2", _LINK)
    assert email.calls == [AuthIdentifierKind.email]
    assert phone.calls == [AuthIdentifierKind.phone]


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
