"""_resolve_birth_family: whether a new birth starts a fresh family or
joins an existing one (second child, twins). DB-free, matching the rest
of the unit suite — a fake session records add()/flush() calls and
families_repo.get_membership is monkeypatched."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from models import Family, FamilyMembership, FamilyRole


class _FakeFamilyDB:
    def __init__(self, family: Family | None = None):
        self._family = family
        self.added: list = []
        self.flushes = 0

    def get(self, _model, _pk):
        return self._family

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushes += 1


def _payload(family_id=None, baby_name="Lily Rose"):
    return SimpleNamespace(family_id=family_id, baby_name=baby_name)


def test_no_family_id_creates_new_family_and_owner_membership():
    import main

    user = SimpleNamespace(id=uuid.uuid4())
    db = _FakeFamilyDB()

    family = main._resolve_birth_family(
        db, payload=_payload(family_id=None), current_user=user
    )

    assert isinstance(family, Family)
    assert family.primary_owner_user_id == user.id
    assert family.display_name == "Lily Rose Family"
    assert family in db.added
    memberships = [o for o in db.added if isinstance(o, FamilyMembership)]
    assert len(memberships) == 1
    assert memberships[0].role == FamilyRole.owner
    assert memberships[0].user_id == user.id


def test_unknown_family_id_404s():
    import main

    user = SimpleNamespace(id=uuid.uuid4())
    db = _FakeFamilyDB(family=None)

    with pytest.raises(HTTPException) as exc_info:
        main._resolve_birth_family(
            db, payload=_payload(family_id=uuid.uuid4()), current_user=user
        )
    assert exc_info.value.status_code == 404


def test_family_id_rejects_non_member(monkeypatch):
    import main

    user = SimpleNamespace(id=uuid.uuid4())
    family = Family(id=uuid.uuid4(), primary_owner_user_id=uuid.uuid4())
    db = _FakeFamilyDB(family=family)
    monkeypatch.setattr(main.families_repo, "get_membership", lambda *a, **kw: None)

    with pytest.raises(HTTPException) as exc_info:
        main._resolve_birth_family(
            db, payload=_payload(family_id=family.id), current_user=user
        )
    assert exc_info.value.status_code == 403


def test_family_id_rejects_viewer_role(monkeypatch):
    import main

    user = SimpleNamespace(id=uuid.uuid4())
    family = Family(id=uuid.uuid4(), primary_owner_user_id=uuid.uuid4())
    db = _FakeFamilyDB(family=family)
    membership = SimpleNamespace(role=FamilyRole.family_viewer)
    monkeypatch.setattr(
        main.families_repo, "get_membership", lambda *a, **kw: membership
    )

    with pytest.raises(HTTPException) as exc_info:
        main._resolve_birth_family(
            db, payload=_payload(family_id=family.id), current_user=user
        )
    assert exc_info.value.status_code == 403


@pytest.mark.parametrize("role", [FamilyRole.owner, FamilyRole.co_parent])
def test_family_id_attaches_existing_family_for_parent(monkeypatch, role):
    import main

    user = SimpleNamespace(id=uuid.uuid4())
    family = Family(id=uuid.uuid4(), primary_owner_user_id=uuid.uuid4())
    db = _FakeFamilyDB(family=family)
    membership = SimpleNamespace(role=role)
    monkeypatch.setattr(
        main.families_repo, "get_membership", lambda *a, **kw: membership
    )

    result = main._resolve_birth_family(
        db, payload=_payload(family_id=family.id), current_user=user
    )

    assert result is family
    # joining an existing family creates nothing new
    assert db.added == []
    assert db.flushes == 0
