"""Pure-function tests for audience-scope visibility."""
from __future__ import annotations

import pytest

from models import AudienceScope, FamilyRole
from repositories.births import visible_scopes_for_role


def test_non_member_sees_nothing() -> None:
    """A birth page is private: no membership, no scopes. Callers turn the
    empty set into a 404 rather than serving an empty timeline, so someone
    who guessed a slug can't tell a real page from an unused one."""
    assert visible_scopes_for_role(None) == frozenset()


def test_family_viewer_sees_the_family_tier() -> None:
    scopes = visible_scopes_for_role(FamilyRole.family_viewer)
    assert AudienceScope.group_targeted in scopes
    assert AudienceScope.parents_only not in scopes


def test_family_viewer_still_sees_retired_public_rows() -> None:
    """`public` is retired and nothing new is written with it, but rows
    posted before the change must not vanish from the family's timeline."""
    assert AudienceScope.public in visible_scopes_for_role(FamilyRole.family_viewer)


@pytest.mark.parametrize("role", [FamilyRole.owner, FamilyRole.co_parent])
def test_parents_see_every_scope(role: FamilyRole) -> None:
    scopes = visible_scopes_for_role(role)
    for scope in AudienceScope:
        assert scope in scopes
