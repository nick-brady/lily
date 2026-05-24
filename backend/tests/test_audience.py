"""Pure-function tests for audience-scope visibility."""
from __future__ import annotations

import pytest

from models import AudienceScope, FamilyRole
from repositories.births import visible_scopes_for_role


def test_anonymous_sees_only_public() -> None:
    assert visible_scopes_for_role(None) == {AudienceScope.public}


def test_family_viewer_sees_public_and_group_targeted() -> None:
    scopes = visible_scopes_for_role(FamilyRole.family_viewer)
    assert AudienceScope.public in scopes
    assert AudienceScope.group_targeted in scopes
    assert AudienceScope.parents_only not in scopes


@pytest.mark.parametrize("role", [FamilyRole.owner, FamilyRole.co_parent])
def test_parents_see_every_scope(role: FamilyRole) -> None:
    scopes = visible_scopes_for_role(role)
    for scope in AudienceScope:
        assert scope in scopes
