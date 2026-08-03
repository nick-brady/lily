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
    from routes import births as births_routes

    user = SimpleNamespace(id=uuid.uuid4())
    db = _FakeFamilyDB()

    family = births_routes._resolve_birth_family(
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
    from routes import births as births_routes

    user = SimpleNamespace(id=uuid.uuid4())
    db = _FakeFamilyDB(family=None)

    with pytest.raises(HTTPException) as exc_info:
        births_routes._resolve_birth_family(
            db, payload=_payload(family_id=uuid.uuid4()), current_user=user
        )
    assert exc_info.value.status_code == 404


def test_family_id_rejects_non_member(monkeypatch):
    from routes import births as births_routes

    user = SimpleNamespace(id=uuid.uuid4())
    family = Family(id=uuid.uuid4(), primary_owner_user_id=uuid.uuid4())
    db = _FakeFamilyDB(family=family)
    monkeypatch.setattr(births_routes.families_repo, "get_membership", lambda *a, **kw: None)

    with pytest.raises(HTTPException) as exc_info:
        births_routes._resolve_birth_family(
            db, payload=_payload(family_id=family.id), current_user=user
        )
    assert exc_info.value.status_code == 403


def test_family_id_rejects_viewer_role(monkeypatch):
    from routes import births as births_routes

    user = SimpleNamespace(id=uuid.uuid4())
    family = Family(id=uuid.uuid4(), primary_owner_user_id=uuid.uuid4())
    db = _FakeFamilyDB(family=family)
    membership = SimpleNamespace(role=FamilyRole.family_viewer)
    monkeypatch.setattr(
        births_routes.families_repo, "get_membership", lambda *a, **kw: membership
    )

    with pytest.raises(HTTPException) as exc_info:
        births_routes._resolve_birth_family(
            db, payload=_payload(family_id=family.id), current_user=user
        )
    assert exc_info.value.status_code == 403


@pytest.mark.parametrize("role", [FamilyRole.owner, FamilyRole.co_parent])
def test_family_id_attaches_existing_family_for_parent(monkeypatch, role):
    from routes import births as births_routes

    user = SimpleNamespace(id=uuid.uuid4())
    family = Family(id=uuid.uuid4(), primary_owner_user_id=uuid.uuid4())
    db = _FakeFamilyDB(family=family)
    membership = SimpleNamespace(role=role)
    monkeypatch.setattr(
        births_routes.families_repo, "get_membership", lambda *a, **kw: membership
    )

    result = births_routes._resolve_birth_family(
        db, payload=_payload(family_id=family.id), current_user=user
    )

    assert result is family
    # joining an existing family creates nothing new
    assert db.added == []
    assert db.flushes == 0


# ── delete_birth: the settings danger zone ──


def test_delete_birth_rejects_co_parent():
    from routes import births as births_routes

    access = SimpleNamespace(
        role=FamilyRole.co_parent, birth=SimpleNamespace(id=uuid.uuid4())
    )

    with pytest.raises(HTTPException) as exc_info:
        births_routes.delete_birth(access=access, db=SimpleNamespace())
    assert exc_info.value.status_code == 403


class _DeleteBirthDB:
    """Enough Session for delete_birth: the sibling-count query, the family
    lookup, and whatever DELETEs the family cleanup issues."""

    def __init__(self, *, remaining, family=None, calls=None):
        self._remaining = remaining
        self._family = family
        self.calls = calls if calls is not None else []
        self.deleted_tables: list[str] = []

    def scalar(self, _stmt):
        return self._remaining

    def execute(self, stmt):
        self.deleted_tables.append(stmt.table.name)
        return None

    def get(self, _model, _ident):
        return self._family

    def commit(self):
        self.calls.append("commit")


def _delete_birth_env(monkeypatch, *, hard_deleted=True):
    from routes import births as births_routes

    calls: list = []
    birth = SimpleNamespace(id=uuid.uuid4(), family_id=uuid.uuid4())
    access = SimpleNamespace(role=FamilyRole.owner, birth=birth)

    def fake_erase(db, b, now):
        assert b is birth
        calls.append("erase")
        return ["key-a", "key-b"], hard_deleted

    monkeypatch.setattr(births_routes, "erase_birth", fake_erase)
    monkeypatch.setattr(
        births_routes.storage,
        "delete_objects",
        lambda keys: calls.append(("s3", tuple(keys))) or [],
    )
    return births_routes, access, calls


def test_delete_birth_erases_commits_then_clears_s3(monkeypatch):
    """The commit-before-external ordering is the contract: rows go first,
    S3 objects only after the transaction holds."""
    births_routes, access, calls = _delete_birth_env(monkeypatch)
    # a sibling page survives, so the family is left alone
    db = _DeleteBirthDB(remaining=1, calls=calls)

    response = births_routes.delete_birth(access=access, db=db)

    assert response.status_code == 204
    assert calls == ["erase", "commit", ("s3", ("key-a", "key-b"))]
    assert db.deleted_tables == []


def test_deleting_the_last_page_takes_the_family_with_it(monkeypatch):
    """An empty family used to survive, invisible on the account page but
    still offered by the setup wizard as somewhere to add a baby — silently
    re-admitting every co-parent and viewer who was ever on it."""
    births_routes, access, calls = _delete_birth_env(monkeypatch, hard_deleted=True)
    db = _DeleteBirthDB(remaining=0, calls=calls)

    births_routes.delete_birth(access=access, db=db)

    assert db.deleted_tables == ["families"]  # memberships CASCADE


def test_a_soft_deleted_last_page_scrubs_the_family_instead(monkeypatch):
    """A birth with gift orders soft-deletes so the Stripe records survive,
    and it still points at the family — so the family can't be dropped or the
    FK cascade would take the birth with it. Same rule as account deletion."""
    births_routes, access, calls = _delete_birth_env(monkeypatch, hard_deleted=False)
    family = SimpleNamespace(display_name="The Brady Family")
    db = _DeleteBirthDB(remaining=0, family=family, calls=calls)

    births_routes.delete_birth(access=access, db=db)

    assert db.deleted_tables == ["family_memberships"]
    assert family.display_name == "Deleted"
