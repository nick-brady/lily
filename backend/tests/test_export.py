"""The export builders are pure (rows in → text out), so we pin the parts
that would corrupt an archive silently: interval math, media naming and
cross-refs, author fallbacks, and — most importantly — the invariant that
no sensitive field ever reaches a produced file.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import export
from models import (
    AudienceScope,
    BirthStatus,
    MediaKind,
    ReactionKind,
    TimelineEventType,
)


T0 = datetime(2026, 3, 15, 2, 30, 45, tzinfo=timezone.utc)


def _event(
    seq,
    event_type,
    *,
    minutes=0,
    payload=None,
    posted_by=None,
    scope=AudienceScope.public,
):
    occurred = T0 + timedelta(minutes=minutes)
    return SimpleNamespace(
        id=uuid.uuid4(),
        sequence_id=seq,
        event_type=event_type,
        occurred_at=occurred,
        posted_at=occurred,
        posted_by_user_id=posted_by,
        payload=payload or {},
        audience_scope=scope,
    )


def _contraction(seq, *, minutes, duration=52, ignored=False, posted_by=None):
    payload = {"type": "contraction", "duration_seconds": duration, "end_time": None}
    if duration is not None:
        payload["end_time"] = (
            T0 + timedelta(minutes=minutes, seconds=duration)
        ).isoformat()
    if ignored:
        payload["ignore_interval_before"] = True
    return _event(
        seq,
        TimelineEventType.contraction,
        minutes=minutes,
        payload=payload,
        posted_by=posted_by,
    )


def _asset(kind=MediaKind.photo, mime="image/jpeg", key="f/x/b/y/a.jpg"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        kind=kind,
        mime_type=mime,
        original_s3_key=key,
        created_at=T0,
    )


def _csv_rows(text):
    lines = text.strip().splitlines()
    return lines[0].split(","), [line.split(",") for line in lines[1:]]


# ---- contractions.csv ----


def test_contraction_intervals_computed_from_sorted_starts():
    events = [
        _contraction(1, minutes=0),
        _contraction(2, minutes=7),
        _contraction(3, minutes=12, ignored=True),
    ]
    header, rows = _csv_rows(export.contractions_csv(events, {}))
    interval_col = header.index("interval_from_previous_start_seconds")
    assert rows[0][interval_col] == ""            # first row has no previous
    assert rows[1][interval_col] == "420"         # 7 minutes
    assert rows[2][interval_col] == "300"         # 5 minutes
    assert rows[2][header.index("interval_ignored")] == "yes"
    assert rows[0][header.index("interval_ignored")] == "no"


def test_still_running_contraction_has_blank_duration_and_end():
    events = [_contraction(1, minutes=0, duration=None)]
    header, rows = _csv_rows(export.contractions_csv(events, {}))
    assert rows[0][header.index("duration_seconds")] == ""
    assert rows[0][header.index("end_time_utc")] == ""


# ---- media naming ----


def test_attached_media_named_by_event_sequence():
    asset = _asset()
    event = _event(
        7,
        TimelineEventType.photo,
        payload={"media_id": str(asset.id), "caption": "hi"},
    )
    names = export.plan_media_names([event], [asset])
    assert names[asset.id] == "media/0007-20260315T023045Z-photo.jpg"


def test_orphan_media_still_exported_under_unattached_name():
    asset = _asset(kind=MediaKind.voice_memo, mime="audio/webm", key="f/x/b/y/a.webm")
    names = export.plan_media_names([], [asset])
    name = names[asset.id]
    assert name.startswith("media/unattached-20260315T023045Z-voice_memo-")
    assert name.endswith(".webm")
    assert str(asset.id)[:8] in name


def test_name_collisions_get_suffixed():
    a1, a2 = _asset(), _asset()
    e1 = _event(7, TimelineEventType.photo, payload={"media_id": str(a1.id)})
    e2 = _event(7, TimelineEventType.photo, payload={"media_id": str(a2.id)})
    names = export.plan_media_names([e1, e2], [a1, a2])
    assert len(set(names.values())) == 2
    assert any(name.endswith("-2.jpg") for name in names.values())


def test_extension_fallback_chain():
    assert export._ext_for(_asset(mime="image/jpeg")) == ".jpg"
    assert export._ext_for(_asset(mime=None, key="f/x/b/y/clip.png")) == ".png"
    assert export._ext_for(_asset(mime=None, key="f/x/b/y/noext")) == ".bin"


# ---- timeline.csv ----


def test_timeline_cross_references_media_and_falls_back_on_author():
    asset = _asset()
    events = [
        _event(
            3,
            TimelineEventType.photo,
            payload={"media_id": str(asset.id), "caption": "first smile"},
        ),
        _event(4, TimelineEventType.milestone, payload={"title": "Baby Born!"}),
    ]
    media_files = export.plan_media_names(events, [asset])
    header, rows = _csv_rows(export.timeline_csv(events, {}, media_files))
    assert rows[0][header.index("media_file")] == media_files[asset.id]
    assert rows[0][header.index("caption")] == "first smile"
    assert rows[0][header.index("posted_by")] == export.FALLBACK_AUTHOR
    assert rows[1][header.index("title")] == "Baby Born!"
    assert rows[1][header.index("media_file")] == ""


# ---- guesses.csv ----


def _birth(**overrides):
    base = dict(
        child_name="Lily Wren",
        slug="lily-wren",
        status=BirthStatus.born,
        theme="lily",
        child_dob=T0,
        child_weight_lbs=7.125,
        child_length_in=20.0,
        birth_started_at=T0,
        birth_completed_at=T0,
        created_at=T0,
        shipping_address={"line1": "123 Secret Ln", "city": "Nowhere"},
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_guess_scores_only_when_actuals_known():
    guess = SimpleNamespace(
        display_name="Janet",
        weight_lbs=7.5,
        length_in=None,
        created_at=T0,
        updated_at=T0,
    )
    header, rows = _csv_rows(export.guesses_csv([guess], _birth()))
    assert rows[0][header.index("closeness_score")] == "0.38"
    header, rows = _csv_rows(
        export.guesses_csv([guess], _birth(child_weight_lbs=None))
    )
    assert rows[0][header.index("closeness_score")] == ""


# ---- the sensitive-data invariant ----


def test_no_sensitive_data_reaches_any_produced_text():
    birth = _birth()
    asset = _asset()
    events = [
        _contraction(1, minutes=0),
        _event(2, TimelineEventType.photo, payload={"media_id": str(asset.id)}),
    ]
    comment = SimpleNamespace(
        event_id=events[1].id,
        user_id=None,
        body="So excited!",
        created_at=T0,
        updated_at=T0 + timedelta(minutes=1),
    )
    reaction = SimpleNamespace(
        event_id=events[1].id, user_id=None, kind=ReactionKind.love, created_at=T0
    )
    seq = {e.id: e.sequence_id for e in events}
    media_files = export.plan_media_names(events, [asset])
    produced = "\n".join(
        [
            export.birth_json(birth),
            export.readme_text(birth),
            export.contractions_csv(events, {}),
            export.guesses_csv([], birth),
            export.timeline_csv(events, {}, media_files),
            export.comments_csv([comment], seq, {}),
            export.reactions_csv([reaction], seq, {}),
            export.family_csv([("Janet", "family_viewer", T0)]),
        ]
    )
    lowered = produced.lower()
    assert "shipping" not in lowered
    assert "123 secret ln" not in lowered
    assert "unlock" not in lowered
    assert "storage_tier" not in lowered
    assert "@" not in produced  # display names only, never emails

    meta = json.loads(export.birth_json(birth))
    assert "shipping_address" not in meta
    assert "is_unlocked" not in meta
    assert meta["child_name"] == "Lily Wren"
    assert meta["export_format_version"] == export.EXPORT_FORMAT_VERSION


def test_comment_edited_flag():
    event = _event(2, TimelineEventType.text_note, payload={"body": "hello"})
    seq = {event.id: 2}
    edited = SimpleNamespace(
        event_id=event.id,
        user_id=None,
        body="fixed typo",
        created_at=T0,
        updated_at=T0 + timedelta(minutes=2),
    )
    pristine = SimpleNamespace(
        event_id=event.id, user_id=None, body="hi", created_at=T0, updated_at=T0
    )
    header, rows = _csv_rows(export.comments_csv([edited, pristine], seq, {}))
    assert rows[0][header.index("edited")] == "yes"
    assert rows[1][header.index("edited")] == "no"
