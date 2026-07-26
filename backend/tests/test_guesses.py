"""Family-pool scoring and board assembly.

The upsert itself is Postgres-specific (partial-unique ON CONFLICT) and is
exercised against the dev database; here we pin the pure parts — the one
true scoring function and the server-side ranking the routes return.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

from repositories import guesses as guesses_repo


def test_score_mirrors_original_predictions_component():
    # weight-only exact guess (Jena) beats a both-fields near miss
    assert guesses_repo.score(
        8.4375, None, actual_weight_lbs=8.4375, actual_length_in=20.5
    ) == 0
    both = guesses_repo.score(
        8.7, 20.25, actual_weight_lbs=8.4375, actual_length_in=20.5
    )
    assert both == (8.7 - 8.4375) + 0.5 * (20.5 - 20.25)


def test_score_none_when_nothing_guessed():
    assert (
        guesses_repo.score(None, None, actual_weight_lbs=8.0, actual_length_in=20.0)
        is None
    )


def test_score_length_ignored_without_actual_length():
    # only the weight component counts when the parents recorded no length
    s = guesses_repo.score(8.0, 25.0, actual_weight_lbs=8.5, actual_length_in=None)
    assert s == 0.5


def _guess_row(name, weight, length, user_id=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        display_name=name,
        weight_lbs=weight,
        length_in=length,
        created_at=None,
    )


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
    birth = SimpleNamespace(id=uuid.uuid4(), child_weight_lbs=8.4375, child_length_in=20.5)

    board = engagement._guess_board(None, birth, me)
    assert board.settled is True
    names = [g.display_name for g in board.guesses]
    assert names == ["Jena", "Papa", "Shrug"]  # exact win first, no-guess last
    assert board.guesses[0].rank == 1 and board.guesses[0].is_mine
    assert board.guesses[2].rank is None and board.guesses[2].score is None


def test_guess_board_unsettled_has_no_ranks(monkeypatch):
    from routes import engagement

    rows = [_guess_row("Papa", 9.6, 21.3)]
    monkeypatch.setattr(
        engagement.guesses_repo, "list_guesses", lambda db, birth_id: rows
    )
    birth = SimpleNamespace(id=uuid.uuid4(), child_weight_lbs=None, child_length_in=None)

    board = engagement._guess_board(None, birth, None)
    assert board.settled is False
    assert board.guesses[0].rank is None and board.guesses[0].score is None
    assert board.guesses[0].is_mine is False
