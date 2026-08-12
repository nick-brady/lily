# Decisions

Product and design decisions that have already been made, with the reasoning
behind them. The point of this file is to stop settled questions from being
quietly reopened by later work.

**Before changing product behavior, read the relevant section here.** If a
change would contradict an entry, say so and ask — don't just implement it.
A decision is only superseded when it's explicitly reversed here.

**Format:** each entry is dated, states the decision, says *why*, and points at
where it lives in the code. When a decision is reversed, don't delete it —
strike it and add the replacement below, so the history of the reasoning stays
readable.

**Scope:** product and design choices. Working-style preferences (how commits
are made, how the dev environment runs) live in Claude's memory, not here.

> **Code comments can be stale — this file wins.** Four separate comments
> described a "36-week guess-edit lock" for a week after it was removed on
> 2026-07-31, and that outdated text got read back as if it were the decision.
> Verify against behavior, not comments.

---

## First principles

### Never hold a family's data hostage
*2026-07-11*

Every birth has a free ZIP download containing **all** of their data:
full-size images, audio files, a CSV of every contraction, a CSV of the family
guesses. Always free, no gate, no tier.

> "I NEVER want to hold data hostage.. they can pay to keep it hosted which is
> great, but.. I never want to hold it hostage."

Paying is for *hosting*, not for *access*. **Where:** `backend/export.py`;
surfaced on the birth settings page.

### Deleting an account really deletes the data
*2026-07-11*

> "if they want to delete it fully.. they deserve to have the right to have
> their data fully removed"

**Where:** `backend/account_deletion.py`.

---

## Privacy & audience

### A birth page is private — there is no public tier
*2026-08-05 → 2026-08-06 · `ca4058c` (PR #57)*

A birth page is reachable by invite or not at all. The `public` audience tier
was retired; the composer offers two tiers, not three.

> "by default, pages need to be private. you know? obviously can't have
> strangers viewing a page.. I don't even think making a page 'public' is a
> good idea"

**Why:** "Public" promised "anyone with the link can see," which was never
true — the timeline already 401'd anonymous callers. It was also the *default*,
so it silently collected every post anyone ever made without being chosen.

**Where:** `AUDIENCE_OPTIONS` in `frontend/src/components/UpdateForm.jsx:10`;
`AudienceScope` in `backend/models.py:47`.

**Constraint:** the `public` value stays in the enum and must never be written.
Dropping it is DDL, and DDL on that table queues behind live SSE transactions.
`family_viewer` is still granted it so anything the backfill missed stays
visible to the family rather than vanishing.

### A stranger gets a 404, and no hint that an invite exists
*2026-08-05*

Someone with no claim on the page — anonymous or signed in — gets a 404/401 and
"this is a private birth." Nothing more.

> "not even a mention they should ask the parents for an invite, because they
> woulda invited them if they wanted."

### The teaser is for invite-token holders, and it's narrow
*2026-08-05*

An invite link carries a token; that link is what earns the teaser page. The
teaser returns a **narrow preview schema** — `child_name`, `slug`, `status`,
`theme` — never the full birth object. Arriving at `/b/<slug>` cold is not the
same as arriving from an invite, and the two must not render the same thing.

> "the qr code on the birth invite or w/e is going to have the token embedded
> in it that allows them to sign up"

**Note:** the invite token is the only key to the page. That's accepted — it's
an invite link, and you can't see the link without being given it.

### Posts are scoped per-post, defaulting to Family
*2026-05-24 · `387f98a`*

Each timeline event carries an `audience_scope`: **Family** (`group_targeted`,
everyone invited) or **Parents only** (`parents_only`). Default is Family.

---

## Money & what's free

### Comments are not gated — the unlock was removed
*2026-07-19*

The $12 comment unlock was un-gated entirely and the purchase path removed.
Reasoning lives in the business-model notes under
`/Users/Shared/bradys/Brady's/Business Models/Lily`.

**Safe to remove outright:** it had never been used in the wild.

### Paid storage stays
*2026-07-19*

Un-gating comments didn't remove the storage concept — there's still something
for a birth whose storage has been paid for. **Where:** `storage_paid_until`,
`storage_lifetime` on `Birth`.

### Lifetime storage is ~$50, and it's a real flag
*2026-07-20*

`storage_lifetime` is a boolean, never a far-future sentinel date, so the page
can honestly say "forever."

---

## The family pool (guesses)

### Guesses never lock on the calendar
*2026-07-31*

There is **deliberately no calendar lock** on guess edits. Guesses stay
editable until `born`; `updated_at` rides out on the board so the family can
see who changed their mind late.

> "why should it ever lock? the parent knows the due date.. but the actual
> birth date is never known unless its an induction"

**Why:** a due date tells nobody what the baby will weigh, and the one date
that *is* knowable early — a booked induction — was never protected by freezing
at 36 weeks anyway, since new guesses stayed open. The freeze bound only the
people who guessed early and honestly, which is backwards for a pool that wants
everyone in from 20 weeks.

**Supersedes:** the 36-week (`due_date - 28 days`) edit freeze. Four comments
still described that lock a week later; corrected 2026-08-08.

**`due_date` locks nothing now** — it shows on the guess board and prefills the
date field (`frontend/src/components/GuessForm.jsx:46`). That's all it does.

**Where:** `backend/routes/engagement.py:449`.

### The only lock is the date guess at labor start
*2026-07-31*

`date_guess` closes when labor begins, because the page itself is broadcasting
the answer at that point. Calling "today" off the live contraction timeline is
cheating, not fun. The whole pool closes at `born`.

### There is no "lock in your guess" action
*2026-07-31*

The explicit lock-in was removed as confusing.

> "it's kinda 'locked' the second you put it in.. and you can change it per the
> rules we have... whats the point of 'locking' it at all. sorta confusing."

### Weight is the ranking; other dimensions get medals
*2026-07-31*

Weight is the gold — it's the number families actually ask about — and drives
`rank`. Length takes a separate medal. Date is not part of the ranking.

**Refinements:** ties share a medal, and a medal needs **at least two
contenders** — "closest length" is a hollow prize when one person was the only
one to name a length.

**Where:** `_award` and the settle path in `backend/routes/engagement.py:461`.

### The boy/girl call gets no medal, and stays off the keepsake
*2026-08-10*

The gender call is scored on the page (✓/✗ once settled) and appears nowhere in
the artwork. Both stay that way.

> "it's a 50-50 so a bunch of people would have it. it's fine as is"

**Why:** every medal is awarded on a *distance* — `_award` takes the smallest
delta. A call has no delta, so a fourth medal would land on roughly half the
jar at once, and a medal half the room is wearing isn't one. It would also push
🏆🥈🥉 the rest of the way into reading as 1st/2nd/3rd/4th place, which the
medal set was shaped to avoid.

**Considered and not built:** stating it on the keepsake as a fact rather than
an award — *"Eleven of twelve said boy. She's a girl."* Still the right shape
if this is ever revisited; it just isn't worth the two SVG templates yet.

**Where:** `MEDALS` in `frontend/src/components/Predictions.jsx`;
`_build_pool_scene` in `backend/gift_artwork.py` passes only name, weight and
length per row. The `Call` column already hides itself when the gender pool is
off, so a birth that was never a surprise renders correctly in both places.

### The pool's voice: intuition, not betting
*2026-08-01*

The entry points name the faculty being consulted rather than the mechanic,
which turns a betting pool into a folk tradition. Two lines, split by audience:

- **Parent onboarding** — "One more thing — what's your mother's intuition
  telling you? 🎈" (`frontend/src/pages/SetupPage.jsx:596`)
- **Invite redeem** — "One last thing — hunches before hellos 🎈"
  (`frontend/src/pages/InviteRedeemPage.jsx:391`), because a viewer hasn't got
  a mother's intuition about this baby

**Why:** it needed to sit alongside "from bump to baby" — clever and maternal
rather than cute.

### It's called "The guessing jar"
*2026-08-08 — provisional*

Renamed from **"The family pool."** Shorthand in copy is "the jar" (as "the
pool" was before it): *"Settle the jar," "Weight is what settles the jar."*

**Why:** the 2026-08-01 question *"is 'the family pool' the right word for
this?"* produced the two intuition lines above but never the rename, so the
betting-pool framing survived in the headers. The jar is the jellybean jar at
the school fair — guessing at a quantity, warm and childhood-flavored, no
wager.

**Explicitly provisional** — "can change it later." Don't treat it as settled
vocabulary the way the entries above are.

**Not renamed, deliberately:** the `mug_pool` / `card_pool` template IDs, the
`_pool.svg.j2` partial, `gender_pool_enabled`, and the `PoolPill` component.
Those are persisted identifiers and internal names — renaming them would mean
a migration for zero user-visible gain. The keepsake artwork never printed the
section name at all (it prints "N GUESSES" / "CLOSEST: NAME"), so nothing
physical changed.

### The guess UI states the guess and offers an update
*2026-08-01 · applied everywhere 2026-08-08*

Reads as `Your guess — 7 lbs 6 oz, 20", on Aug 15. Update` with **Update**
underlined. With no guess yet: "You haven't left your guess yet! Make it now."

**Why:** the previous card didn't say what had been guessed, and the action
didn't read as clickable.

**Applies to every surface showing your own guess.** This shipped to Birth
settings in 2026-08-01 but the birth-page pool modal kept the old
"Your guess is in, sealed 🎈 — change it →" — which stated nothing and read as
a caption, so it got missed. Both now render the shared `YourGuessLine` in
`frontend/src/components/Predictions.jsx`, beside the formatters, so the two
can't drift apart again.

### Parents guess from settings too
*2026-08-01*

The birth settings page carries the same pool-guess link and the same modal as
the birth page.

### Gender is a two-option control, not a checkbox
*2026-07-30*

Boy / Girl / surprise as a toggle. The bare checkbox didn't say what it did.

---

## The Baby Born! moment

### The announcement must be reversible — an accidental tap needs a way back
*2026-08-08*

Deleting the Born milestone undoes the whole flip: status reverts, the arrival
time clears, and watchers' pages roll back.

> "what if you click it on accident.. it needs to be deletable"

**Why:** the Born milestone isn't a post *about* the birth — it *is* the
announcement. Deleting it used to soft-delete the event while leaving the birth
`born`, which stranded the page: the Baby Born! button renders only while status
isn't `born`, and the arrival time is edited *through that same event*.

**Rejected alternative:** making the Born milestone undeletable. That "fixes"
the stranding by making the accidental-tap case permanent, which is worse.
**The event must stay deletable.**

**Where:** `delete_event` in `backend/routes/timeline.py`; `unmark_born` in
`backend/repositories/births.py`.

### ~~The undo is offered from the "is here" card, and it's named — not an ×~~
*~~2026-08-10~~ — superseded the same day by "The Born milestone is the
celebration" below. The × reasoning survives the reversal; the card it was
attached to doesn't.*

~~The parent-facing arrival card carries an **Undo the announcement** text
button, handing the Born milestone to the timeline's existing delete confirm.~~

### The Born milestone is the celebration; the parent's arrival banner is gone
*2026-08-10*

For a parent the page used to state the birth twice: a banner derived from
`birth.status`, and a Born milestone drawn as the same chip as Water Broke.
Now there's one — the Born card in the story, at display size, with the name.

> "it's distracting to have that undo the announcement on what is an exciting
> thing. but.. it's also confusing that to remove that you have to delete the
> baby born milestone. maybe that Lily Wren is here... we should just make the
> milestone in place be a little nicer"

**Why:** the banner reflected `status`, so it had no event behind it and no
controls of its own — which is exactly why removing it meant deleting
something else, and why offering an undo meant parking a delete link on the
happiest card on the page. The milestone already carries its own edit and
delete. Undoing the announcement is now just deleting the announcement, in
the place you're already looking at it.

**Follows:** "Announcing the birth belongs in the composer, not a card of its
own" — the banner was the last of the card-of-its-own idea.

**Rejected alternative:** the × on the banner. At a card's corner × means
*dismiss this card*, but this one rolls the birth back for everyone watching;
an affordance shouldn't lean on the dialog to correct its own signal. The same
reasoning retired the composer's rotate-to-×.

**Kept:** viewers still get their own full arrival hero — someone arriving cold
needs the headline. Parents were there.

**Where:** `BornMilestoneItem` in `frontend/src/components/Timeline.jsx`; the
removed section in `frontend/src/pages/PublicBirthPage.jsx`.

### Undoing lands where the evidence says
*2026-08-08*

Reverts to `in_labor` if a live contraction exists, keeping `birth_started_at`;
otherwise to `preparing`, clearing it. A recorded contraction is a real
observation and must survive — but if none was recorded, `mark_born` *inferred*
that timestamp, and keeping it would assert a labor that never happened.

### Nobody posts at the moment of birth — so ask for the time
*2026-07-30 → 2026-07-31*

The Baby Born flow leads with "When did they arrive?" rather than burying the
time under a confirmation.

> "born — for example. it will never be entered right when it happens,
> obviously. so actually saying the time is pretty important"

**Why:** you post once you have a free hand, so the prefilled "now" is nearly
always 15–40 minutes late. Correction is the norm, not the exception.

### A born-time correction never moves the labor start
*2026-07-30 · `3decda0`*

Editing the Born milestone's time updates `birth_completed_at` only.
`birth_started_at` is left alone, even if that makes the arrival precede the
labor start.

> "would born _ever_ be less than the first contraction... no.. not really..
> unless it was wrong, in which case.. it kinda makes sense for it to be
> .. wrong."

**Why:** dragging the start back to match reported a 0-minute labor and
destroyed a correctly recorded first-contraction time, with no undo. A wrong
entered time should produce a wrong-*looking* record — not the loss of a
correct value.

---

## Timeline

### Timestamps are editable
*2026-07-30*

Posts carry their real time, not just the posting time — a whole branch of work
in its own right.

### Nothing on a birth timeline happens in the future
*2026-07-30 · `3decda0`*

Backdating is the point; forward-dating is never legitimate and a
future-stamped event pins itself above the story forever.

### Contraction times can't be edited
Their durations and gap markers are derived from them.

### A failed edit must not look like a saved one
*2026-07-30 · `3decda0`*

The edit modal stays open and says why on failure. It used to close regardless,
so a rejected correction looked exactly like a saved one — the worst outcome
for someone fixing their baby's arrival time.

---

## Gifts & keepsakes

### Artwork waits a few hours after the arrival time
*2026-07-31*

No artwork generates until `birth_completed_at + 4h`.

> "we should hold on generating the artwork renders until maybe a few hours
> after the birth to solve for this. they'll probably correct it reasonably
> quickly."

**Where:** `ARTWORK_GRACE_PERIOD` in `backend/repositories/gifts.py`.

### Anything that changes the story invalidates the artwork
*2026-07-31*

Edits, deletes, and recorded measurements all call `gifts_repo.mark_stale` —
for any milestone, not just the birth. A corrected arrival time or caption has
to reach the keepsake, not just the page.

### Gifts live after the timeline, not before it
*2026-07-19*

### A gift tile shows the product; the modal shows the artwork
*2026-07-21*

The tile is the rendered mug. Clicking opens a modal with the **full artwork**
so you can see what's actually on it, plus multiple product angles from
Printful as tiles.

> "when you click on a gift, you should see the rendered gift, but you should
> also see the full artwork, so you know what's on it."

### "One for me" is not either/or
*2026-07-20*

Buying for the family and buying one for yourself is not a radio choice — both
at once, qty 2, two shipping addresses.

### Keep the leaderboard gift; add the birth announcement card
*2026-07-20*

### Keepsakes don't belong dropped into settings
*2026-07-30*

The keepsake section works on the main page. Dropping it into the settings page
as-is doesn't make sense — surfacing it elsewhere needs its own thought.

---

## Shipping address

### The address ask must explain itself, and stay optional
*2026-07-30*

Framed around gifts — *"People may want to get you gifts, make it easy for them
to ship it to you"* — with **(optional)** in the header so it never implies
gift-receiving is being forced on them.

Add that gifts ship straight to you **without senders ever needing to ask for
your address**. Sharing a birth story with someone means you probably don't
mind them seeing your address.

**Removed:** "Skip it and gift-senders just type your address at checkout
instead."

### Collect it before the birth, not after
*2026-07-30*

> "the parent isn't going to be typing in addresses the day after their kid is
> born because they're scrolling the settings page of this app. no way in hell."

This is why the ask appears pre-birth even though gifts only exist post-birth.

---

## Onboarding & setup

### Creating a page leads somewhere, not straight to the page
*2026-07-29*

After creating a baby's page, walk through inviting family and leaving your own
prediction — each step skippable with "you can do this later in Birth Settings."

### Skip goes on the left
*2026-07-29*

Standard onboarding placement. It was on the wrong side and read as off
immediately.

### Don't prefill weights and heights
*2026-07-29*

### The create-your-page flow needs Google SSO
*2026-08-04*

### The theme picker doesn't animate
*2026-08-03*

Default to the first theme, already selected, rendering before a name is typed.
Sliding it in from center was too much.

---

## Deletion & account

### A birth page can be deleted from its own settings
*2026-07-29*

In a clearly marked danger area on `/b/<slug>/settings`. Account deletion is a
different thing and doesn't cover it.

### "Delete my account" doesn't belong prominent on the main page
*2026-07-30*

> "I feel like that is a little... intense."

### An owner of an empty family can leave, and that removes the family
*2026-08-02 → 2026-08-07*

Deleting your only birth page shouldn't strand you in a family you can't leave.
The rule matches what `account_deletion.erase_sole_parent_family` already
encodes and `delete_birth` already calls: refusing an owner on **role alone** is
a dead end when there's nothing left to own.

### A viewer who leaves their last page is not a new parent
*2026-08-03*

Someone who stops following their last birth must not be redirected into the
create-a-baby-page wizard. Wrong ending for someone who was never a parent.

---

## Landing page & hero video

### The hero phone runs the real components
*2026-07-08*

`Timeline`, `CommentThread`, `ReactionBar`, `ContractionButton` mount for real
with scripted fixture data; a cue engine mutates that fixture state.

> "i want to use the real components in the phone to avoid drift."

Explicitly chosen over a mocked UI, and made the *only* option in the plan.

### The carousel shows exactly what the hero shows
*2026-07-19*

Same timeline, same photos — including the pixel fixes made to the hero phone.

### Video and image assets live in S3 behind presigned URLs
*2026-07-19*

Not committed into the repo as blobs.

### The hero overlay stays light
*2026-07-19*

It drifted back to dark during the S3 work and was put back.

### A long hero video is acceptable
*2026-07-13*

~40s is fine if it tells the whole story.

> "the point is they will understand the app.. and if they actually watch all
> of it then I've really got them?"

---

## Admin & metrics

### Admin is a separate client, deployed as its own site
*2026-07-15*

Its own frontend (`frontend-admin`, admin.arrivalstory.com), sharing the
backend.

### No Metabase, no Google Analytics
*2026-07-15*

Self-hosted metrics through purpose-built CRUD APIs instead.

> "it's too easy to just make CRUD apis with AI (you)."

GA was ruled out on past experience. Track signups, shares, and whether people
who were shared to actually log in.

---

## Infrastructure

### fail2ban is installed on the box
*2026-07-19*

Added after noticing probing traffic.

---

<!--
Compiled 2026-08-08 from all 14 sessions in this project directory, plus
rationale already written into commits and code comments. Entries without a
commit hash come from conversation and were checked against current behavior
where possible. Correct anything misattributed.
-->
