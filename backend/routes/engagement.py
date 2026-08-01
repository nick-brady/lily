"""Engagement on timeline events — reactions, comments, and the family
pool (guesses). Each surface exists twice: `/birth/{id}/...` for members
and `/b/{slug}/...` for anyone authed who found the page (Aunt Linda via
QR card); both funnel into the same `_do_*` helpers."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import get_current_user
from db import get_db
from events import publish_comment_change, publish_reaction_change
from models import Birth, BirthStatus, FamilyRole, ReactionKind, User
from repositories import births as births_repo
from repositories import comments as comments_repo
from repositories import guesses as guesses_repo
from repositories import reactions as reactions_repo
from repositories import timeline as timeline_repo
from routes.deps import (
    BirthAccess,
    PublicEngagementAccess,
    require_birth_access,
    require_public_engagement,
    require_visible_event,
    resolve_public_birth,
    scope_set_for_visitor,
)
from schemas import (
    CommentCreateIn,
    CommentEditIn,
    CommentOut,
    GuessBoardOut,
    GuessIn,
    GuessOut,
    ReactionCountOut,
    ReactionToggleIn,
)

router = APIRouter()


# ============ Reactions ============


async def _do_toggle_reaction(
    db: Session,
    *,
    birth: Birth,
    role: FamilyRole | None,
    user: User,
    event_id: uuid.UUID,
    kind: ReactionKind,
    add: bool,
) -> dict[ReactionKind, ReactionCountOut]:
    event = require_visible_event(db, event_id, birth=birth, role=role)
    if add:
        changed = reactions_repo.add_reaction(
            db, event_id=event.id, user_id=user.id, kind=kind
        )
    else:
        changed = reactions_repo.remove_reaction(
            db, event_id=event.id, user_id=user.id, kind=kind
        )
    db.commit()
    if changed:
        await publish_reaction_change(
            birth.id,
            kind="reaction_added" if add else "reaction_removed",
            event_id=event.id,
            reaction_kind=kind.value,
            user_id=user.id,
        )
    summary = reactions_repo.summarize_event(
        db, event_id=event.id, requester_user_id=user.id
    )
    return {
        k: ReactionCountOut(count=s.count, mine=s.mine)
        for k, s in summary.items()
    }


@router.post(
    "/birth/{birth_id}/event/{event_id}/reactions",
    response_model=dict[ReactionKind, ReactionCountOut],
)
async def add_reaction(
    event_id: uuid.UUID,
    payload: ReactionToggleIn = Body(...),
    access: BirthAccess = Depends(require_birth_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[ReactionKind, ReactionCountOut]:
    return await _do_toggle_reaction(
        db,
        birth=access.birth,
        role=access.role,
        user=current_user,
        event_id=event_id,
        kind=payload.kind,
        add=True,
    )


@router.delete(
    "/birth/{birth_id}/event/{event_id}/reactions/{kind}",
    response_model=dict[ReactionKind, ReactionCountOut],
)
async def remove_reaction(
    event_id: uuid.UUID,
    kind: ReactionKind,
    access: BirthAccess = Depends(require_birth_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[ReactionKind, ReactionCountOut]:
    return await _do_toggle_reaction(
        db,
        birth=access.birth,
        role=access.role,
        user=current_user,
        event_id=event_id,
        kind=kind,
        add=False,
    )


@router.post(
    "/b/{slug}/event/{event_id}/reactions",
    response_model=dict[ReactionKind, ReactionCountOut],
)
async def public_add_reaction(
    event_id: uuid.UUID,
    payload: ReactionToggleIn = Body(...),
    access: PublicEngagementAccess = Depends(require_public_engagement),
    db: Session = Depends(get_db),
) -> dict[ReactionKind, ReactionCountOut]:
    return await _do_toggle_reaction(
        db,
        birth=access.birth,
        role=access.role,
        user=access.user,
        event_id=event_id,
        kind=payload.kind,
        add=True,
    )


@router.delete(
    "/b/{slug}/event/{event_id}/reactions/{kind}",
    response_model=dict[ReactionKind, ReactionCountOut],
)
async def public_remove_reaction(
    event_id: uuid.UUID,
    kind: ReactionKind,
    access: PublicEngagementAccess = Depends(require_public_engagement),
    db: Session = Depends(get_db),
) -> dict[ReactionKind, ReactionCountOut]:
    return await _do_toggle_reaction(
        db,
        birth=access.birth,
        role=access.role,
        user=access.user,
        event_id=event_id,
        kind=kind,
        add=False,
    )


# ============ Comments ============


def _comment_out(comment, author_name: str | None) -> CommentOut:
    out = CommentOut.model_validate(comment)
    out.author_name = author_name
    return out


def _author_name_map(db: Session, comments: list) -> dict[uuid.UUID, str | None]:
    user_ids = {c.user_id for c in comments}
    if not user_ids:
        return {}
    rows = db.execute(
        select(User.id, User.display_name).where(User.id.in_(user_ids))
    ).all()
    return {uid: name for uid, name in rows}


async def _do_create_comment(
    db: Session,
    *,
    birth: Birth,
    role: FamilyRole | None,
    user: User,
    event_id: uuid.UUID,
    body: str,
) -> CommentOut:
    event = require_visible_event(db, event_id, birth=birth, role=role)
    comment = comments_repo.create_comment(
        db, event_id=event.id, user_id=user.id, body=body.strip()
    )
    db.commit()
    db.refresh(comment)
    await publish_comment_change(
        birth.id,
        kind="comment_added",
        event_id=event.id,
        comment_id=comment.id,
        body=comment.body,
        user_id=user.id,
    )
    return _comment_out(comment, user.display_name)


async def _do_edit_comment(
    db: Session,
    *,
    birth: Birth,
    user: User,
    event_id: uuid.UUID,
    comment_id: uuid.UUID,
    body: str,
) -> CommentOut:
    comment = comments_repo.get_comment(db, comment_id)
    if (
        comment is None
        or comment.event_id != event_id
        or comment.deleted_at is not None
    ):
        raise HTTPException(status_code=404, detail="Comment not found")
    # Only the author can edit. Parents can delete but not rewrite words.
    if comment.user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the author can edit")
    comments_repo.edit_body(db, comment, body.strip())
    db.commit()
    db.refresh(comment)
    await publish_comment_change(
        birth.id,
        kind="comment_updated",
        event_id=event_id,
        comment_id=comment.id,
        body=comment.body,
    )
    return _comment_out(comment, user.display_name)


async def _do_delete_comment(
    db: Session,
    *,
    birth: Birth,
    role: FamilyRole | None,
    user: User,
    event_id: uuid.UUID,
    comment_id: uuid.UUID,
) -> Response:
    comment = comments_repo.get_comment(db, comment_id)
    if comment is None or comment.event_id != event_id:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.deleted_at is not None:
        return Response(status_code=204)
    # Authors can delete their own. Parents can moderate anyone's.
    is_author = comment.user_id == user.id
    if not (is_author or births_repo.is_parent(role)):
        raise HTTPException(status_code=403, detail="Not allowed")
    comments_repo.soft_delete(db, comment)
    db.commit()
    await publish_comment_change(
        birth.id,
        kind="comment_deleted",
        event_id=event_id,
        comment_id=comment.id,
    )
    return Response(status_code=204)


@router.get(
    "/birth/{birth_id}/event/{event_id}/comments",
    response_model=list[CommentOut],
)
def list_event_comments(
    event_id: uuid.UUID,
    access: BirthAccess = Depends(require_birth_access),
    db: Session = Depends(get_db),
) -> list[CommentOut]:
    event = require_visible_event(
        db, event_id, birth=access.birth, role=access.role
    )
    rows = comments_repo.list_for_event(db, event_id=event.id)
    names = _author_name_map(db, rows)
    return [_comment_out(r, names.get(r.user_id)) for r in rows]


@router.get(
    "/b/{slug}/event/{event_id}/comments",
    response_model=list[CommentOut],
)
def public_list_event_comments(
    slug: str,
    event_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CommentOut]:
    """Comments are the heart of the keepsake — and viewing is auth-gated,
    so readers are signed-in viewers like everyone else on the page."""
    birth = resolve_public_birth(db, slug)
    visible = scope_set_for_visitor(db, birth, current_user)
    event = timeline_repo.get_event(db, event_id)
    if (
        event is None
        or event.birth_id != birth.id
        or event.deleted_at is not None
        or event.audience_scope not in visible
    ):
        raise HTTPException(status_code=404, detail="Event not found")
    rows = comments_repo.list_for_event(db, event_id=event.id)
    names = _author_name_map(db, rows)
    return [_comment_out(r, names.get(r.user_id)) for r in rows]


@router.post(
    "/birth/{birth_id}/event/{event_id}/comments",
    response_model=CommentOut,
)
async def create_event_comment(
    event_id: uuid.UUID,
    payload: CommentCreateIn = Body(...),
    access: BirthAccess = Depends(require_birth_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentOut:
    return await _do_create_comment(
        db,
        birth=access.birth,
        role=access.role,
        user=current_user,
        event_id=event_id,
        body=payload.body,
    )


@router.post(
    "/b/{slug}/event/{event_id}/comments",
    response_model=CommentOut,
)
async def public_create_event_comment(
    event_id: uuid.UUID,
    payload: CommentCreateIn = Body(...),
    access: PublicEngagementAccess = Depends(require_public_engagement),
    db: Session = Depends(get_db),
) -> CommentOut:
    return await _do_create_comment(
        db,
        birth=access.birth,
        role=access.role,
        user=access.user,
        event_id=event_id,
        body=payload.body,
    )


@router.patch(
    "/birth/{birth_id}/event/{event_id}/comments/{comment_id}",
    response_model=CommentOut,
)
async def edit_event_comment(
    event_id: uuid.UUID,
    comment_id: uuid.UUID,
    payload: CommentEditIn = Body(...),
    access: BirthAccess = Depends(require_birth_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentOut:
    return await _do_edit_comment(
        db,
        birth=access.birth,
        user=current_user,
        event_id=event_id,
        comment_id=comment_id,
        body=payload.body,
    )


@router.patch(
    "/b/{slug}/event/{event_id}/comments/{comment_id}",
    response_model=CommentOut,
)
async def public_edit_event_comment(
    event_id: uuid.UUID,
    comment_id: uuid.UUID,
    payload: CommentEditIn = Body(...),
    access: PublicEngagementAccess = Depends(require_public_engagement),
    db: Session = Depends(get_db),
) -> CommentOut:
    return await _do_edit_comment(
        db,
        birth=access.birth,
        user=access.user,
        event_id=event_id,
        comment_id=comment_id,
        body=payload.body,
    )


@router.delete(
    "/birth/{birth_id}/event/{event_id}/comments/{comment_id}",
    status_code=204,
)
async def delete_event_comment(
    event_id: uuid.UUID,
    comment_id: uuid.UUID,
    access: BirthAccess = Depends(require_birth_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    return await _do_delete_comment(
        db,
        birth=access.birth,
        role=access.role,
        user=current_user,
        event_id=event_id,
        comment_id=comment_id,
    )


@router.delete(
    "/b/{slug}/event/{event_id}/comments/{comment_id}",
    status_code=204,
)
async def public_delete_event_comment(
    event_id: uuid.UUID,
    comment_id: uuid.UUID,
    access: PublicEngagementAccess = Depends(require_public_engagement),
    db: Session = Depends(get_db),
) -> Response:
    return await _do_delete_comment(
        db,
        birth=access.birth,
        role=access.role,
        user=access.user,
        event_id=event_id,
        comment_id=comment_id,
    )


# ============ The family pool (guesses) ============


# There is deliberately no calendar lock on edits. A due date tells nobody
# what the baby will weigh, and the only date that IS knowable early — a
# booked induction — was never protected by freezing edits at 36 weeks: new
# guesses stay open until the birth, so anyone who hadn't guessed yet simply
# guessed after the booking. The freeze bound only the people who guessed
# early and honestly, which is backwards for a pool that wants everyone in
# from 20 weeks. Guesses now stay editable until `born`, `updated_at` rides
# out on the board, and the family can see for itself who changed their mind
# late. The one lock that stays is `date_guess` at labor start — there the
# page itself is broadcasting the answer.


def _award(items, delta_field: str, winner_field: str) -> None:
    """Crown the closest guess in one dimension. Ties share the medal.

    A medal needs at least two contenders — "closest length" is a hollow
    prize when one person was the only one to name a length, and the same
    used to hand out the date crown for a 16-day miss simply because nobody
    else had guessed a day.
    """
    contenders = [
        (getattr(item, delta_field), item)
        for _, item in items
        if getattr(item, delta_field) is not None
    ]
    if len(contenders) < 2:
        return
    best = min(delta for delta, _ in contenders)
    for delta, item in contenders:
        if delta == best:
            setattr(item, winner_field, True)


def _guess_board(db: Session, birth: Birth, current_user_id) -> GuessBoardOut:
    """Everyone's guesses; once the parents record the actual measurements
    the board is settled — scored and ranked server-side (the one scoring
    implementation lives in repositories/guesses.py).

    Pre-settle, other people's guess VALUES are sealed here (names stay
    visible, numbers/sex/date go out null) — sealing in the serializer, not
    the client, or the "blur" would leak in the JSON."""
    rows = guesses_repo.list_guesses(db, birth_id=birth.id)
    settled = bool(birth.child_weight_lbs)
    items = []
    for g in rows:
        item = GuessOut.model_validate(g)
        item.is_mine = current_user_id is not None and g.user_id == current_user_id
        if not settled and not item.is_mine:
            item.weight_lbs = None
            item.length_in = None
            item.sex_guess = None
            item.date_guess = None
        items.append((g, item))
    actual_date = None
    if settled:
        actual_date = (
            birth.birth_completed_at.date()
            if birth.birth_completed_at is not None
            else None
        )
        for g, item in items:
            item.weight_delta_lbs = guesses_repo.weight_delta(
                g.weight_lbs, actual_weight_lbs=birth.child_weight_lbs
            )
            item.length_delta_in = guesses_repo.length_delta(
                g.length_in, actual_length_in=birth.child_length_in
            )
            item.date_delta_days = guesses_repo.date_delta(
                g.date_guess, actual_date=actual_date
            )
        # Weight is the ranking: it's the number families ask about, and gold
        # is the top row so the board reads top-down.
        items.sort(
            key=lambda pair: (
                pair[1].weight_delta_lbs is None,
                pair[1].weight_delta_lbs or 0,
            )
        )
        rank = 0
        for _, item in items:
            if item.weight_delta_lbs is not None:
                rank += 1
                item.rank = rank
        _award(items, "weight_delta_lbs", "weight_winner")
        _award(items, "length_delta_in", "length_winner")
        _award(items, "date_delta_days", "date_winner")
    return GuessBoardOut(
        guesses=[item for _, item in items],
        actual_weight_lbs=birth.child_weight_lbs,
        actual_length_in=birth.child_length_in,
        actual_sex=birth.child_sex if settled else None,
        actual_date=actual_date,
        settled=settled,
        gender_pool_enabled=birth.gender_pool_enabled,
        due_date=birth.due_date,
    )


def _do_put_guess(db: Session, *, birth: Birth, user: User, payload: GuessIn) -> GuessOut:
    """Upsert the caller's guess. Free engagement, like reactions and
    comments. Two locks, both tied to something that actually happened:
    the whole pool closes at born, and the date field alone closes at labor
    start — calling "today" from the live contraction timeline is cheating,
    not fun. Sizes stay editable right up to the birth (see the note above
    `_guess_board` for why there's no calendar freeze)."""
    if birth.status is BirthStatus.born:
        raise HTTPException(
            status_code=409, detail="The baby is here — the pool is settled"
        )
    if (
        payload.weight_lbs is None
        and payload.length_in is None
        and payload.sex_guess is None
        and payload.date_guess is None
    ):
        raise HTTPException(
            status_code=422, detail="Guess something — a size, a date, or both"
        )
    if payload.sex_guess is not None and not birth.gender_pool_enabled:
        raise HTTPException(
            status_code=422, detail="This pool isn't taking boy/girl guesses"
        )
    date_sent = "date_guess" in payload.model_fields_set
    if date_sent and payload.date_guess is not None and birth.status is BirthStatus.in_labor:
        raise HTTPException(
            status_code=422,
            detail="Date guesses closed when labor began — nice try 😉",
        )
    if not (user.display_name or "").strip():
        # same contract as comments: the client name-captures, then retries
        raise HTTPException(
            status_code=422,
            detail={
                "code": "name_required",
                "message": "Add your name so the family knows whose guess this is",
            },
        )
    row = guesses_repo.upsert_guess(
        db,
        birth=birth,
        user=user,
        weight_lbs=payload.weight_lbs,
        length_in=payload.length_in,
        sex_guess=(
            payload.sex_guess
            if "sex_guess" in payload.model_fields_set
            else guesses_repo.UNSET
        ),
        # Absent field ≠ null: a mid-labor resubmit whose form hid the
        # closed date field must preserve the date already on record.
        date_guess=(payload.date_guess if date_sent else guesses_repo.UNSET),
    )
    out = GuessOut.model_validate(row)
    out.is_mine = True
    return out


@router.get("/birth/{birth_id}/guesses", response_model=GuessBoardOut)
def list_guesses(
    access: BirthAccess = Depends(require_birth_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GuessBoardOut:
    return _guess_board(db, access.birth, current_user.id)


@router.get("/b/{slug}/guesses", response_model=GuessBoardOut)
def list_public_guesses(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GuessBoardOut:
    """The pool is page content, and viewing is auth-gated like the rest
    of the page."""
    birth = resolve_public_birth(db, slug)
    return _guess_board(db, birth, current_user.id if current_user else None)


@router.put("/birth/{birth_id}/guess", response_model=GuessOut)
def put_guess(
    payload: GuessIn,
    access: BirthAccess = Depends(require_birth_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GuessOut:
    return _do_put_guess(db, birth=access.birth, user=current_user, payload=payload)


@router.put("/b/{slug}/guess", response_model=GuessOut)
def put_public_guess(
    payload: GuessIn,
    access: PublicEngagementAccess = Depends(require_public_engagement),
    db: Session = Depends(get_db),
) -> GuessOut:
    return _do_put_guess(db, birth=access.birth, user=access.user, payload=payload)
