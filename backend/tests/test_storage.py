"""Storage helpers — no live S3 required."""
from __future__ import annotations

import uuid

from storage import object_key


def test_object_key_layout() -> None:
    family_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    birth_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    key = object_key(family_id=family_id, birth_id=birth_id, filename="abc.jpg")
    assert key == f"f/{family_id}/b/{birth_id}/abc.jpg"
