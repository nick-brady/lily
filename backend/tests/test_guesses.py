"""Family-pool scoring and board assembly.

The upsert itself is Postgres-specific (partial-unique ON CONFLICT) and is
exercised against the dev database; here we pin the pure parts — the three
per-dimension distances and the server-side medals the routes return.
"""
from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace

from repositories import guesses as guesses_repo


def test_each_dimension_is_measured_in_its_own_units():
    """No exchange rate between pounds, inches and days. The old single score
    was |Δlbs| + 0.5 × |Δin|, pricing an inch at eight ounces — which is how
    an exactly-right weight guess lost to one 2 oz out."""
    assert guesses_repo.weight_delta(8.4375, actual_weight_lbs=8.4375) == 0
    assert guesses_repo.weight_delta(8.7, actual_weight_lbs=8.4375) == 8.7 - 8.4375
    assert guesses_repo.length_delta(20.25, actual_length_in=20.5) == 0.25
    assert (
        guesses_repo.date_delta(dt.date(2026, 8, 15), actual_date=dt.date(2026, 7, 30))
        == 16
    )


def test_an_unguessed_dimension_scores_none_not_zero():
    """A guess that named nothing must sink, never win by having no error to
    accumulate."""
    assert guesses_repo.weight_delta(None, actual_weight_lbs=8.0) is None
    assert guesses_repo.length_delta(None, actual_length_in=20.0) is None
    assert guesses_repo.date_delta(None, actual_date=dt.date(2026, 7, 30)) is None


def test_no_distance_without_an_actual_to_measure_against():
    assert guesses_repo.weight_delta(8.0, actual_weight_lbs=None) is None
    assert guesses_repo.length_delta(25.0, actual_length_in=None) is None
    assert guesses_repo.date_delta(dt.date(2026, 8, 1), actual_date=None) is None


def _guess_row(name, weight, length, user_id=None, sex=None, date=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        display_name=name,
        weight_lbs=weight,
        length_in=length,
        sex_guess=sex,
        date_guess=date,
        created_at=None,
    )


def _birth(**overrides):
    base = dict(
        id=uuid.uuid4(),
        child_weight_lbs=None,
        child_length_in=None,
        child_sex=None,
        due_date=None,
        gender_pool_enabled=False,
        birth_completed_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_guess_board_ranks_and_marks_mine(monkeypatch):
    from routes import engagement

    me = uuid.uuid4()
    rows = [
        _guess_row("Papa", 9.6, 21.3),
        _guess_row("Jena", 8.4375, None, user_id=me),
        _guess_row("Shrug", None, None),
    ]
    monkeypatch.setattr(
        engagement.guesses_repo, "list_guesses", lambda db, birth_id: rows
    )
    birth = _birth(child_weight_lbs=8.4375, child_length_in=20.5)

    board = engagement._guess_board(None, birth, me)
    assert board.settled is True
    names = [g.display_name for g in board.guesses]
    assert names == ["Jena", "Papa", "Shrug"]  # exact win first, no-guess last
    assert board.guesses[0].rank == 1 and board.guesses[0].is_mine
    assert board.guesses[2].rank is None
    assert board.guesses[2].weight_delta_lbs is None


def test_guess_board_unsettled_has_no_ranks(monkeypatch):
    from routes import engagement

    rows = [_guess_row("Papa", 9.6, 21.3)]
    monkeypatch.setattr(
        engagement.guesses_repo, "list_guesses", lambda db, birth_id: rows
    )
    birth = _birth()

    board = engagement._guess_board(None, birth, None)
    assert board.settled is False
    assert board.guesses[0].rank is None
    assert board.guesses[0].weight_delta_lbs is None
    assert board.guesses[0].is_mine is False


def test_gold_goes_to_the_closest_weight_not_a_blended_score(monkeypatch):
    """The finding this replaces. Linda nailed the weight and was an inch out
    on length; Maya was 2 oz out and exact on length. The old formula gave
    Maya the trophy, which every family would read as wrong."""
    from routes import engagement

    rows = [
        _guess_row("Maya", 8.25, 20.0, date=dt.date(2026, 8, 15)),
        _guess_row("Linda", 8.125, 21.0),
    ]
    monkeypatch.setattr(
        engagement.guesses_repo, "list_guesses", lambda db, birth_id: rows
    )
    birth = _birth(
        child_weight_lbs=8.125,
        child_length_in=20.0,
        birth_completed_at=dt.datetime(2026, 7, 30, 22, 0, tzinfo=dt.timezone.utc),
    )

    board = engagement._guess_board(None, birth, None)
    by_name = {g.display_name: g for g in board.guesses}
    assert by_name["Linda"].weight_winner is True  # 🏆 exact weight
    assert by_name["Maya"].weight_winner is False
    assert by_name["Maya"].length_winner is True  # 🥈 exact length
    assert by_name["Linda"].length_winner is False
    # 🥉 needs a contest: Maya is the only one who named a day
    assert by_name["Maya"].date_winner is False


def test_medals_are_shared_on_a_tie(monkeypatch):
    from routes import engagement

    rows = [_guess_row("Papa", 8.0, 20.0), _guess_row("Nana", 8.0, 20.0)]
    monkeypatch.setattr(
        engagement.guesses_repo, "list_guesses", lambda db, birth_id: rows
    )
    birth = _birth(child_weight_lbs=8.5, child_length_in=21.0)

    board = engagement._guess_board(None, birth, None)
    assert all(g.weight_winner for g in board.guesses)
    assert all(g.length_winner for g in board.guesses)


def test_uncontested_dimensions_award_nothing(monkeypatch):
    """A "closest length" medal is hollow when one person was the only one to
    name a length — and the date crown used to go to a 16-day miss for exactly
    this reason."""
    from routes import engagement

    rows = [
        _guess_row("Papa", 8.0, 20.0, date=dt.date(2026, 8, 20)),
        _guess_row("Nana", 8.4, None),
    ]
    monkeypatch.setattr(
        engagement.guesses_repo, "list_guesses", lambda db, birth_id: rows
    )
    birth = _birth(
        child_weight_lbs=8.125,
        child_length_in=20.0,
        birth_completed_at=dt.datetime(2026, 7, 30, 22, 0, tzinfo=dt.timezone.utc),
    )

    board = engagement._guess_board(None, birth, None)
    by_name = {g.display_name: g for g in board.guesses}
    # two weight guesses → contested, gold awarded
    assert by_name["Papa"].weight_winner is True
    # one length guess, one date guess → no silver, no bronze
    assert not any(g.length_winner for g in board.guesses)
    assert not any(g.date_winner for g in board.guesses)


def test_missing_a_dimension_costs_only_that_medal(monkeypatch):
    """What makes it fair to invite someone mid-labor, after the date guess has
    already closed: they still compete for gold and silver."""
    from routes import engagement

    rows = [
        _guess_row("Early", 8.9, 22.0, date=dt.date(2026, 7, 30)),
        _guess_row("JoinedLate", 8.125, 20.0),  # no date — arrived mid-labor
        _guess_row("Alsodated", 9.5, 23.0, date=dt.date(2026, 8, 9)),
    ]
    monkeypatch.setattr(
        engagement.guesses_repo, "list_guesses", lambda db, birth_id: rows
    )
    birth = _birth(
        child_weight_lbs=8.125,
        child_length_in=20.0,
        birth_completed_at=dt.datetime(2026, 7, 30, 22, 0, tzinfo=dt.timezone.utc),
    )

    board = engagement._guess_board(None, birth, None)
    by_name = {g.display_name: g for g in board.guesses}
    assert by_name["JoinedLate"].weight_winner is True
    assert by_name["JoinedLate"].length_winner is True
    assert by_name["Early"].date_winner is True  # exact day, contested
    assert by_name["JoinedLate"].date_delta_days is None


# ── Sealing, locks, gender, date (2026-07-27 pool v2) ─────────────────────


def test_board_seals_others_values_pre_settle(monkeypatch):
    from datetime import date

    from routes import engagement

    me = uuid.uuid4()
    rows = [
        _guess_row("Papa", 9.6, 21.3, sex="boy", date=date(2026, 8, 1)),
        _guess_row("Jena", 8.4, 20.0, user_id=me, sex="girl", date=date(2026, 8, 3)),
    ]
    monkeypatch.setattr(
        engagement.guesses_repo, "list_guesses", lambda db, birth_id: rows
    )
    board = engagement._guess_board(None, _birth(), me)

    papa = next(g for g in board.guesses if g.display_name == "Papa")
    mine = next(g for g in board.guesses if g.is_mine)
    # names visible, values sealed — the seal happens server-side so the
    # numbers never ride the JSON
    assert papa.weight_lbs is None and papa.length_in is None
    assert papa.sex_guess is None and papa.date_guess is None
    assert mine.weight_lbs == 8.4 and mine.sex_guess == "girl"
    assert board.actual_sex is None and board.actual_date is None


def test_board_reveals_everything_once_settled(monkeypatch):
    from datetime import date, datetime, timezone

    from routes import engagement

    rows = [
        _guess_row("Papa", 9.6, 21.3, date=date(2026, 8, 1)),
        _guess_row("Jena", 8.4, 20.0, date=date(2026, 8, 4)),
        _guess_row("NoDate", 8.5, None),
    ]
    monkeypatch.setattr(
        engagement.guesses_repo, "list_guesses", lambda db, birth_id: rows
    )
    birth = _birth(
        child_weight_lbs=8.4375,
        child_length_in=20.5,
        child_sex="girl",
        birth_completed_at=datetime(2026, 8, 3, 14, 30, tzinfo=timezone.utc),
    )
    board = engagement._guess_board(None, birth, None)

    assert board.settled is True
    assert board.actual_sex == "girl"
    assert board.actual_date == date(2026, 8, 3)
    papa = next(g for g in board.guesses if g.display_name == "Papa")
    jena = next(g for g in board.guesses if g.display_name == "Jena")
    nodate = next(g for g in board.guesses if g.display_name == "NoDate")
    assert papa.weight_lbs == 9.6  # unsealed
    # Jena is 1 day off, Papa 2 — Jena alone wins the date crown
    assert jena.date_winner is True
    assert papa.date_winner is False and nodate.date_winner is False


def test_board_date_winner_ties_share(monkeypatch):
    from datetime import date, datetime, timezone

    from routes import engagement

    rows = [
        _guess_row("Early", 8.0, None, date=date(2026, 8, 2)),
        _guess_row("Late", 8.0, None, date=date(2026, 8, 4)),
    ]
    monkeypatch.setattr(
        engagement.guesses_repo, "list_guesses", lambda db, birth_id: rows
    )
    birth = _birth(
        child_weight_lbs=8.0,
        birth_completed_at=datetime(2026, 8, 3, 2, 0, tzinfo=timezone.utc),
    )
    board = engagement._guess_board(None, birth, None)
    assert all(g.date_winner for g in board.guesses)


def _put_guess_env(monkeypatch, *, birth):
    """Shared harness for _do_put_guess: fake user, recorded upsert. The route
    no longer reads the caller's existing row (the 36-week freeze was the only
    thing that needed it), so first guess and edit take the same path — upsert
    resolves either against the unique (birth, user) row."""
    from routes import engagement

    calls = {}

    def fake_upsert(db, **kwargs):
        calls.update(kwargs)
        row = _guess_row(
            kwargs["user"].display_name,
            kwargs["weight_lbs"],
            kwargs["length_in"],
            user_id=kwargs["user"].id,
        )
        return row

    monkeypatch.setattr(engagement.guesses_repo, "upsert_guess", fake_upsert)
    user = SimpleNamespace(id=uuid.uuid4(), display_name="Janet")
    return engagement, user, calls


def test_put_guess_rejects_sex_when_pool_disabled(monkeypatch):
    import pytest
    from fastapi import HTTPException

    from models import BirthStatus
    from schemas import GuessIn

    birth = _birth(gender_pool_enabled=False, status=BirthStatus.preparing)
    engagement, user, _ = _put_guess_env(monkeypatch, birth=birth)
    with pytest.raises(HTTPException) as exc:
        engagement._do_put_guess(
            None, birth=birth, user=user,
            payload=GuessIn(weight_lbs=8.0, sex_guess="girl"),
        )
    assert exc.value.status_code == 422


def test_put_guess_accepts_sex_when_pool_enabled(monkeypatch):
    from datetime import date

    from models import BirthStatus
    from schemas import GuessIn

    birth = _birth(gender_pool_enabled=True, status=BirthStatus.preparing)
    engagement, user, calls = _put_guess_env(monkeypatch, birth=birth)
    engagement._do_put_guess(
        None, birth=birth, user=user,
        payload=GuessIn(weight_lbs=8.0, sex_guess="girl", date_guess=date(2026, 8, 1)),
    )
    assert calls["sex_guess"] == "girl"
    assert calls["date_guess"] == date(2026, 8, 1)


def test_put_guess_date_closes_at_labor(monkeypatch):
    import pytest
    from datetime import date
    from fastapi import HTTPException

    from models import BirthStatus
    from schemas import GuessIn

    birth = _birth(status=BirthStatus.in_labor)
    engagement, user, calls = _put_guess_env(monkeypatch, birth=birth)
    # sending a date mid-labor → rejected
    with pytest.raises(HTTPException) as exc:
        engagement._do_put_guess(
            None, birth=birth, user=user,
            payload=GuessIn(weight_lbs=8.0, date_guess=date(2026, 8, 1)),
        )
    assert exc.value.status_code == 422

    # omitting the date mid-labor → accepted, and the existing date is
    # preserved (UNSET, not nulled)
    engagement._do_put_guess(
        None, birth=birth, user=user, payload=GuessIn(weight_lbs=8.0)
    )
    assert calls["date_guess"] is engagement.guesses_repo.UNSET


def test_put_guess_reaches_upsert_inside_36_weeks(monkeypatch):
    """No calendar freeze. The 36-week lock used to 409 before ever reaching
    the upsert, which only bound the people who guessed early — anyone who
    hadn't guessed yet could still open a fresh one after the induction was
    booked. Both cases below used to be dead on arrival."""
    from datetime import datetime, timedelta, timezone

    from models import BirthStatus
    from schemas import GuessIn

    # 20 days out — well inside the old 28-day window
    birth = _birth(
        status=BirthStatus.preparing,
        due_date=datetime.now(timezone.utc).date() + timedelta(days=20),
    )
    engagement, user, calls = _put_guess_env(monkeypatch, birth=birth)
    out = engagement._do_put_guess(
        None, birth=birth, user=user, payload=GuessIn(weight_lbs=8.0)
    )
    assert out.is_mine and calls["weight_lbs"] == 8.0

    # ...and a page whose due date has already come and gone
    overdue = _birth(
        status=BirthStatus.preparing,
        due_date=datetime.now(timezone.utc).date() - timedelta(days=3),
    )
    engagement2, user2, calls2 = _put_guess_env(monkeypatch, birth=overdue)
    engagement2._do_put_guess(
        None, birth=overdue, user=user2, payload=GuessIn(weight_lbs=9.0)
    )
    assert calls2["weight_lbs"] == 9.0


def test_put_guess_closed_once_born(monkeypatch):
    """The one lock on the whole pool: it closes at born."""
    import pytest
    from fastapi import HTTPException

    from models import BirthStatus
    from schemas import GuessIn

    birth = _birth(status=BirthStatus.born)
    engagement, user, _ = _put_guess_env(monkeypatch, birth=birth)
    with pytest.raises(HTTPException) as exc:
        engagement._do_put_guess(
            None, birth=birth, user=user, payload=GuessIn(weight_lbs=8.0)
        )
    assert exc.value.status_code == 409
