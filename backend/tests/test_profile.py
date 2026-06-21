"""Display names: seeding from invite hints + the PATCH /me route."""
from __future__ import annotations

from fastapi.testclient import TestClient

from models import User
from repositories import users as users_repo


class _FlushOnly:
    def flush(self) -> None:
        pass


def test_seed_sets_name_when_empty() -> None:
    user = User(email="rose@example.com")
    set_it = users_repo.set_display_name_if_empty(_FlushOnly(), user=user, name="Grandma Rose")
    assert set_it is True
    assert user.display_name == "Grandma Rose"


def test_seed_does_not_overwrite_existing() -> None:
    user = User(email="rose@example.com", display_name="Rose")
    set_it = users_repo.set_display_name_if_empty(_FlushOnly(), user=user, name="Grandma Rose")
    assert set_it is False
    assert user.display_name == "Rose"


def test_seed_ignores_blank_and_none() -> None:
    user = User(email="x@example.com")
    assert users_repo.set_display_name_if_empty(_FlushOnly(), user=user, name=None) is False
    assert users_repo.set_display_name_if_empty(_FlushOnly(), user=user, name="   ") is False
    assert user.display_name is None


def test_patch_me_requires_auth() -> None:
    from main import app

    response = TestClient(app).patch("/me", json={"display_name": "X"})
    assert response.status_code == 401
