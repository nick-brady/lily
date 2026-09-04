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

### One contraction, two parents, one button
*2026-08-30 (PR #86) · refined 2026-09-03*

Both parents watch the page in labour and neither knows who will press the
button, so sometimes both do within a second. The server owns "the running
contraction": a START while one is running returns it rather than opening a
second (`uq_timeline_events_one_open_contraction` makes that true, not just
polite); a STOP is judged by the contraction's age on the server clock.

| STOP arrives when it is | the server |
| --- | --- |
| under 5 s old | does nothing — the tapper's tap was a START, not a stop |
| 5–10 s old | refuses with `just_started`; the page asks *Keep timing / Discard it* |
| 10 s or older | stops it, stamping `end_time` itself |

**Why 10 s and not 20:** the real contractions here run 14–101 s. A 20 s band
would put a dialog in front of a genuine short stop, and the dialog has no
"stop it anyway".

**Refinement (2026-09-03): the third quiet tap gets the dialog.** A STOP under
five seconds does nothing and says nothing, which is right for the partner
who reached at the same moment and baffling for someone who started it by
accident and keeps pressing STOP to make it go away. After three declined
taps on the same contraction the page shows the same *Keep timing / Discard
it* dialog. Counted on the client (`frontend/src/utils/stopTaps.js`); the
server's rule is unchanged.

> "if you click it on accident, and you don't see the x, you might keep
> clicking on it trying to stop it"

**Where:** `backend/routes/timeline.py` (`CONTRACTION_GRACE_SECONDS`,
`CONTRACTION_CONFIRM_SECONDS`), `frontend/src/pages/PublicBirthPage.jsx`
(`handleStop`).

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

### The labor clock is one 12-hour dial with a ring per day
*2026-08-16*

Every day of labor gets its own concentric ring, sharing the space a single
ring used to have to itself. One day is one ring and looks the way the artwork
always has; two days is two rings; past three, the oldest fold into the
innermost rather than being dropped.

> "if theirs had all their contractions in a day, then it would just show 1
> ring. if they have 2 days, then 2.. etc."

**Why:** the old geometry silently stopped meaning clock time past **11h 31m** —
beyond that it swept the strokes linearly while still drawing a dial, so a long
labor's artwork wasn't comparable to a short one and nothing on it said so.
With a first baby, labor crossing days isn't the exception.

**A "day" is a rolling 24h from the first contraction, not a calendar date.**
On calendar days a 9h evening labor that crosses midnight would become two
rings, which breaks the rule that one day looks like it always has.

**Rejected — a 24-hour dial.** It would make one ring exactly one day and let
the same time of day line up across rings. But 12 at the top is a watch face
everybody can read without being taught, and a 24-hour dial is a foreign
instrument. A day running past twelve hours wraps onto its own ring instead,
and the overlap layers rather than lying.

**Rejected — a ring per day distinguished by colour.** Unnecessary once the
rings have their own radial bands: they don't touch, so colour was free to do
a different job.

**Where:** `build_hours_clock` and `_ring_layout` in `backend/gift_artwork.py`;
`_clock.svg.j2`.

### AM is pale and fine, PM is deep and heavy
*2026-08-16*

Colour on the clock encodes time of day, not which day. AM strokes take the
lighter theme tone at low opacity and a finer width; PM takes the deeper tone,
heavier and more opaque.

**Why:** a 12-hour face can't tell 4am from 4pm, and that ambiguity was already
in the artwork. Hue alone couldn't carry it — the two chromatic tokens in each
palette are close to begin with, and a shared alpha washed the deep one out
until it matched the light one. Three cues together do carry it.

**Also:** the dial declares itself with `12 / 3 / 6 / 9`. Without numerals
nobody read it as a clock, which made every angle on it decoration.

### The milestones are marks, not words
*2026-08-16*

Each milestone is a small outlined symbol riding the grey circle of the day it
happened on, inside the dial. No labels.

> "no need to ever say what it is.. they'll figure it out and love it. and the
> design is more elegant"

**Why:** the labels were four tracked capitals crossing the rays where an
eight-pixel mark would do. They were also placed in polar coordinates while
the text block beside the clock is cartesian, with neither aware of the other
— which is how `STARTED PUSHING` came to be printed through the rule under the
date.

**Only kinds with a real mark are drawn** — `has_mark()`. A generic diamond
meaning "something happened, we won't say what" is noise on a keepsake, so
`name_announced` (the name is already set in 175pt italic on the same artwork),
`other`, and anything new draw nothing until someone gives them a mark.
`first_hold` is out too: hands need fingers, fingers don't survive at ~26px in
one flat colour, and it's the same moment as the arrival half an hour later.

**The arrival is a heart, not a sparkle** — and it sits on the ring with the
others rather than outside the dial. A sparkle is an ornament that could stand
for anything; this is the one mark on the artwork that is a person.

**All outlines.** Solid marks were the heaviest thing on a face otherwise made
of hairlines.

**Where:** `_STROKE_GLYPHS`, `_ICON_GLYPHS` and `has_mark` in
`backend/gift_artwork.py`. `scripts/render_milestone_marks.py` draws the set at
true print size — use it before adding a mark, because most ideas die at 26px.

### The hero photo sits beside the name, not inside the clock
*2026-08-16*

On `card_hours_photo` the photo moved from the middle of the clock face to a
circle beside the name.

**Why:** it was holding the dial's inner radius open, which is exactly the
space the day rings build inward into. Beside the name it reads as a portrait
rather than a hole in the artwork, and `hours_photo` can take the same clock
geometry as every other clock template.

---

### The clock's rings are calendar days, not 24-hour windows
*2026-09-03*

The radial "hours" artwork puts each day of labour on its own ring. Days are
now local calendar days: a contraction at 3am sits on the ring for the day
it says, and "the next day" is the next ring.

> "definitely want it to match _actual_ days.. so that the time is
> meaningful. otherwise its confusing as hell."

**Supersedes** the rolling window (24 hours from the first contraction),
chosen so an evening labour crossing midnight would stay one ring. On the
real data it did the opposite of what anyone expected: a labour that began
at 7:58am and ran to 8:41am the next morning put 87 contractions on "DAY 1"
— including every one after midnight — and left "DAY 2" with the last ten.
The cost of calendar days is that a 9pm–4am labour becomes two rings with a
seam at midnight, which is at least the seam a person would draw.

Alongside: a ring's **day label steps aside for a mark**. Both ride the same
grey circle and the label was pinned to six o'clock, so a milestone near six
sat on top of it. The mark's position means something and the label's does
not, so the label moves (six, then twelve, then around; the clearest spot
when a small ring has nothing fully clear).

**Where:** `CLOCK_DAY_BOUNDARY`, `build_hours_clock`, `_clear_label_angle`
in `backend/gift_artwork.py`.

---

### An order records what it cost, not only what it charged
*2026-09-03*

The first real order (test mode) charged $24.69. Printful quoted $13.69 to
make and post it, Stripe kept $1.02, and neither was stored — the dashboard
called the whole $24.69 revenue.

> "the order should track the amount received, and the amount spent. we
> should separate out shipping and the product as well."

- **What the buyer paid** lives on `gift_orders`: `product_price_cents`,
  `shipping_cents`, and `amount_cents` as the reconciling total. Postage is
  charged on top of the catalog price (see "Postage is charged, per parcel"),
  so the split is exact.
- **What the partner bills** lives on `gift_shipments`, because Printful's
  order — and its costs — belong to a parcel, and a "both" purchase is two
  parcels: `product_cost_cents`, `shipping_cost_cents`, `tax_cost_cents`,
  `total_cost_cents`, written from Printful's response when the draft is
  created (`costs_recorded_at`). Printful may revise a draft before it is
  confirmed; a later re-fetch on confirmation is the follow-up.
- **What Stripe kept** lives on `gift_orders.payment_fee_cents`, read from
  the balance transaction when the payment is confirmed. One payment can
  cover two orders; the fee is split in proportion to each order's amount,
  summing exactly. Best effort: a fee that can't be read is a warning in the
  log and a gap on the dashboard, never a failed fulfillment.
- **The dashboard's money tile says "Kept"**: charged, less Printful, less
  Stripe — and says how many paid orders have no costs in yet rather than
  quietly overstating the margin.
- Stripe's rate is 2.9% + 30¢ and is not negotiable at this size. The 30¢
  is what hurts on a mug; the answer is pricing, not another processor.

**Where:** migration 0044; `repositories/gift_orders.py` (`split_fee`,
`record_payment_fees`, `submit_shipment`); `payments.StripeClient.payment_fee_cents`;
`fulfillment/printful.py` (`_costs_cents`); `repositories/stats.revenue`.

---

### Keepsakes are made to order: cancel before print, replaced if wrong, no refund for a change of mind
*2026-09-04*

Not "all sales are final" — off-brand for a product whose whole tone is
generosity, and unenforceable for a defective item anyway. The Terms'
Purchases section now says what print-on-demand shops actually do:

- **Cancel for a full refund any time before we send it to print.** Every
  Printful draft is approved by hand, so this window already exists; it
  costs nothing but Stripe's fee (about a dollar).
- **Once it's in production, no refund for a change of mind.** The item
  exists and has one family's baby on it.
- **Damaged, defective or wrong: replaced or refunded, no argument.** Photo
  within 30 days. Printful reimburses its own errors, so this rarely costs us.
- **The address is the buyer's responsibility**, with help offered.

> "I'm happy to issue refunds, but the reality is, like, if they order
> something on Printful and I have to eat the costs, that kind of sucks."

The only cases that cost us are change-of-mind after production and a wrong
address, and the policy puts both on the buyer while staying kind. Refunds
go back to the card; Stripe keeps its fee either way.

**Where:** `frontend/src/pages/TermsPage.jsx` (Purchases), updated
2026-09-04; `help@arrivalstory.com` is the contact.

### The admin site has an Orders page
*2026-09-04*

Every order, newest first: reference, item, which page, buyer, charged, kept,
and one word of state — red when the operator must act. A row opens to the
money split (item/postage, Stripe fee, Printful cost), the printer's state
and reason, tracking, the buyer's email, the gift message, and doors into
the Stripe payment and Printful's orders dashboard. The one place to stand
when a buyer writes in quoting a reference. `GET /admin/orders`, gated like
the rest of the admin API.

### Drafts are approved, or cancelled and refunded, from our own Orders page
*2026-09-04*

Every Printful order is still created as a draft (`PRINTFUL_CONFIRM_ORDERS`
stays off), so nothing is charged to us until someone looks at it. That
look now happens on the admin Orders page instead of Printful's dashboard.
A draft row says "draft — approve?"; opening it offers **Approve · send to
print** and **Cancel & refund**. Each opens a dialog that shows the design,
the destination, and the money — what Printful will charge, what we keep,
or what goes back to the buyer — and asks once.

- **Approve** is `POST /orders/{id}/confirm` at Printful: the draft leaves
  draft, our account is charged, production starts. The shipment records
  `confirmed_at` and who did it. Buyers see nothing new — "being made"
  already covered this — and a second click is a no-op.
- **Cancel** deletes the Printful draft, refunds the Stripe payment in full
  (idempotent key, Stripe keeps its fee), and marks the order refunded,
  which also releases a family claim. It refuses once the draft has been
  confirmed or shipped — that's the Terms' "in production" line, and a
  refund at that point is a decision to eat the cost, made at Stripe by
  hand. The buyer's receipt page and order list say "cancelled and
  refunded" rather than the claim-race message.
- Approving is deliberate and never automatic: it is the moment our money
  moves, and reviewing the artwork once is the only quality gate there is.

**Where:** `backend/fulfillment/printful.py` (`confirm_order`,
`cancel_order`), `backend/repositories/gift_orders.py`
(`approve_shipment`, `cancel_and_refund`), `POST /admin/orders/{id}/approve`
and `/cancel` in `backend/routes/checkout.py`, migration 0047,
`frontend-admin/src/pages/OrdersPage.jsx`. Needs `orders/write` on the
Printful API token.

### The buyer can cancel from the receipt, until we send it to print
*2026-09-04*

The Terms promise a full refund any time before the order goes to print.
Nothing has happened in that window that a person would need to undo — the
draft sits at Printful unpaid — so making the buyer email us to ask would be
a form of friction dressed up as process. The receipt page offers **Cancel
this order** to the signed-in buyer (the receipt itself stays public by
order id; the button appears only when the viewer is the buyer), asks once,
and does it: the draft is deleted, Stripe refunds in full, a family claim
is released. It is a cancel, not a "request cancellation" — a request is
only right when someone has to act on it.

The window is exactly the admin's: not while the worker is mid-submit, not
on hold, never once approved or shipped. After approval the page says so
("It's already being made, so it can't be cancelled from here") and points
at help@. The receipt also now says where the order stands in words: "with
the printer, waiting for us to check it over", then "It's being made —
sent to print on the 5th", then "It's on its way".

**Where:** `POST /me/orders/{id}/cancel` in `backend/routes/checkout.py`,
`buyer_can_cancel` in `backend/repositories/gift_orders.py` (also the
`can_cancel` flag on every receipt line, and `yours` on the receipt),
`frontend/src/pages/OrderConfirmationPage.jsx`, `orderPresentation.js`.

### The printer tells us when it ships, and when it doesn't
*2026-09-04*

A shipped mug used to look exactly like one still on the press, and an
order Printful failed or held sat only in their dashboard. Printful's
webhooks now reach `POST /api/webhooks/printful/{token}`:

- **`package_shipped`** → the shipment records carrier, tracking number,
  tracking URL and ship date, becomes `shipped`, and the buyer gets one
  "It's on its way" email with a Track button — the only moment that phrase
  is true, which is why the receipt never said it before.
- **`order_failed` / `order_canceled`** → `failed` with Printful's reason,
  logged as an ERROR so it lands on the Logs page. **`order_put_hold`** →
  `on_hold` (a WARNING); `order_remove_hold` → back to `submitted`.
- The receipt page, the buyer's orders list and the parents' "Gifts
  received" all show the state and the tracking link.

> "does Printful provide tracking info to a webhook that we can get, and
> then update this later down the road?"

**Printful does not sign its webhooks**, so the URL carries a random token
(`PRINTFUL_WEBHOOK_TOKEN`); a wrong one is a 404 that says nothing. Events
are matched to our order by `external_id` (the order UUID's hex we send
when creating the draft), falling back to Printful's order id. Handling is
idempotent because Printful retries. Registration is one script,
`scripts/register_printful_webhook.py`, run on the box after deploy;
Printful keeps one webhook config per store, so re-running replaces it.

**The receipt page wears no theme.** It is ours, not the family's page, so
it uses the plain gradient `/account` uses rather than the birth's pattern.

**Where:** `repositories/gift_orders.apply_partner_event`,
`routes/checkout.printful_webhook`, `gift_receipt_email.send_shipped`,
migration 0046.

### Arrival Story sends the receipt; Stripe's stays off
*2026-09-04*

One email after a purchase, from us, through Resend — the receipt page in
the inbox: the design, who it's going to (city and state), item / postage /
total, the reference to quote, the gift message shown back, a button to the
receipt page. Never "on its way".

> "what do you think about sending a second email through resend? separate
> from stripe's?"

Two emails for one purchase read as a mistake ("was I charged twice?"), and
Stripe's says "Arrival Story $24.69" with none of the story. So Stripe's
"email customers about successful payments" setting stays **off** (it is off
in the sandbox; leave it off in live). Stripe's refund emails stay on — that
is the one case its automatic mail earns its place.

- **Once per checkout.** Both the webhook and the browser's confirm call
  reach the funnel; a claim on `gift_orders.receipt_emailed_at` decides which
  sends. A "both" purchase is one email covering both copies.
- **The address is the buyer's, from Stripe.** `customer_details.email` on
  the checkout session, falling back to the account's email (a phone-only
  account has none). Kept on the order as `buyer_email` for this purpose.
- **Best effort, after the response.** A BackgroundTask with its own session,
  like the shipment. A failed send logs a warning and releases the claim;
  it never fails fulfillment.
- **The image outlives the inbox.** The receipt page presigns S3 for an hour;
  the email carries the HMAC-signed artwork link with a year's expiry.
- **Failures are not emailed to the buyer.** A shipment the printer refused
  is the operator's to fix first; the receipt page says so honestly, the
  inbox does not.

**Where:** `gift_receipt_email.py`, `messenger.send_email`,
`gift_fulfillment.fulfill_gift_from_session`, migration 0045.

### Stripe sends the buyer back to a receipt, not the page
*2026-09-04*

After paying, the buyer used to land straight on the birth page with a
banner. Stripe's own success screen is a flash; the page after it is the
receipt the buyer remembers, and there wasn't one.

> "I'm left kind of confused because I expected to see some sort of order
> complete page after the stripe checkout."

`success_url` now points at `/b/{slug}/order/{order_id}`. The page confirms
the checkout session on load (the browser path; the webhook is the source of
truth), then shows the order **honestly**: a thank-you and the true state —
being sent to the printer, being made, or *we hit a problem*, never "on its
way" when the printer refused it — an eight-character reference from the
order id, the design, the product option, where it's going as city and state
only, item / postage / total matching the Stripe receipt, the gift message
back to them, and one button to the child's page. While a payment is still
settling it polls for about twelve seconds before saying anything worrying.

**Not on it, on purpose:** the buyer's email, the street address, Stripe or
Printful ids, our costs, or another thing to buy.

**Public, like the confirm route.** The order id is the key; the page carries
nothing a stranger could use. `GET /b/{slug}/orders/{order_id}` returns this
order and any companion paid in the same session (a "both" purchase), scoped
to the birth in the URL, `Cache-Control: no-store`. The old `gift_session`
handling on the birth page stays for checkouts started before this shipped.

**Where:** `routes/checkout.py` (`gift_order_receipt`),
`repositories/gift_orders.receipt`, `frontend/src/pages/OrderConfirmationPage.jsx`,
`utils/orderPresentation.js`.

---

## Shipping address

### Framed prints in, announcement cards out
*2026-08-24*

The cards were never a product: no fulfillment mapping, so they sat as
"$25.00 coming soon" — a placeholder wearing a price tag. Gone (catalog row
deactivated, renderings soft-deleted; `0032`).

A framed print takes their place: the same three designs as the mug on a
matted 12×16 poster (Printful 795), $79. It costs $35.70 + ~$10.50 shipping
against the mug's $5.95 + $6.49 — roughly 3.5× the margin per order, and it's
the thing people hang in a nursery.

> "that kinda seems like a better gift option than the cards"

Frames are drawn by composing the existing card design onto the bigger sheet
(`GiftTemplate.inner`), not by redrawing: vector stays crisp, the theme
background fills the 2% the mat covers, and only photos need more pixels.

### The wall leads the framed prints
*2026-08-24*

The first framed design is drawn *for* the frame rather than borrowed from
the cards: the labor runs the perimeter of the mat opening as an open loop —
first contraction bottom-left of centre, the heart of her arrival bottom-
right — every tick a contraction sized by duration, AM pale / PM deep as on
the mug, the milestone marks riding the line, six-hour time marks with the
date at midnight. The family's comments and reactions dot the *outside* of
the line at the moment they happened: their pulse alongside hers. Inside,
seven photos hang like frames on a wall, the day in reading order.

> "I love design C … the outer part of it with the contractions and the dots"

The border is capped to the last 72 hours before the birth, so a long labor
(or Braxton Hicks logged days early) shows its final three days rather than
compressing weeks onto the line. Iterated as a scratch script against real
data before touching production (`frame_proto.py`, session scratchpad); the
comments/ruler interior of the earlier draft was dropped for the wall.

### The numbers say what was timed, not what happened
*2026-08-25*

Every design's numbers line read "97 CONTRACTIONS · 26H 56M · EVERY 6.5 MIN".
Two of those three infer what wasn't recorded: not every contraction gets
timed, the first and last are the likeliest to be missed, and a start marked
late turns the duration into nonsense on a $79 print. A number a partner
"corrects" at the dinner table is a print nobody buys.

Now: **"97 CONTRACTIONS TIMED · FIRST AT 7:58 AM"** — a count of what was
logged, and a moment that happened. The birth time isn't repeated here: every
design already says it in the "born … at" line an inch above. The average
interval is gone everywhere; so is the labor duration. The dial keeps its
rays: they show what was logged without asserting anything about what wasn't.

> "not every contraction will be recorded.. the first and last may be
> missed.. afraid that it's going to be wrong"

### The ornament is a ceramic photo circle, not a wooden dial
*2026-08-26*

The first ornament was a wooden oval carrying the labor clock. At three
inches a photo of the baby is the better ornament, and ceramic (Printful 881,
circle) takes a photo where wood took ink badly. Her picture fills the disc,
her name and the day at the foot on a soft scrim. The photo starts as the one
taken **nearest the moment of birth** — before or after — rather than the
first one after, and can be changed but not removed (without it the ornament
is a blank white disc). Still $24.

> "that's a much better ornament for the baby.. and it should be a photo on
> it.. probably the one right before or after birth (closest one)"

### The photo book: twenty-four pages, a photo a page while pages last
*2026-08-25*

A hardcover 8×8 (Printful 1564), $49, matte by default because two of its
pages are for a pen and glossy paper takes ink badly. Title → the clock → the
pool in full (leaderboard, medal, named ruler) → the day: photos hung one to
a page while pages last, two to four per page as the story grows, the
family's notes on pages spread between them → the milestones → pages ruled
for writing → a closing. A story with few photos gets more ruled pages, each
under its own heading, not blank ones.

> "add a few blank pages for people to write in … make it clear the pages
> are for writing in"

Always offered, whatever the photo count — the editor says that uploading
more fills more pages. Copy uses the child's name, never a pronoun. The book
is the first design that is many files (`render_book`): the cover wrap is the
template's canvas and what the partner photographs; the pages travel with the
order as their own files; the front face alone is what the gallery shows.

### The story is the second framed print
*2026-08-24*

Replaces the clock card fitted onto the sheet. Every moment of the timeline
— photos, milestones, short notes — wraps the mat opening in order, starting
on the top edge past the top-left corner and running clockwise back up the
left edge; the labor clock sits small in the middle with her name beneath.

**Spaced by beat, not by clock.** Thirty weeks to the delivery room is
months and the labor is hours; on a time-proportional line the pregnancy is
a sliver. A photo claims 1 unit of line, a milestone 0.7, a note 0.55.

**Photos are an inch, always; the count follows.** A print is read from
three feet, and a thumbnail under ¾″ is a smudge. The line holds ~24 at an
inch; a busier story thins evenly (every milestone kept, notes capped at 8),
a quieter one spreads out. Each placed photo is a slot the parent can swap.

> "It really depends on how much they post … we would have to be dynamic."

**Nothing sits on a corner** — two pictures straddling an arc overlap. Notes
hang upright and inward with their time beneath; long ones become just the
dot. Pregnancy moments are labelled by week from `due_date`, days once labor
starts. No portrait beside the name: she's already on the line.

### Two designs lead, "see more" opens the third and a custom placeholder
*2026-08-24*

Each product family shows two designs; "See more" reveals the third and a
dashed "Something of your own — coming soon" tile. Two reads curated; a wall
reads catalog. The custom tile is a door, not a product: no price, nothing to
buy, no editor.

### The shelf: mugs, frames, coming next, storage
*2026-08-24*

Physical products first (mug, then framed print), then a "Coming next"
section naming the ornament and the photo book as real products we've priced
but not drawn, then the storage gifts. Both next products are verified on the
Printful catalogue: wooden ornaments ($8.21, six shapes, 585×945 @150 DPI,
front and back), hardcover photo book ($11–12, cover + 24 per-page image
files — not a PDF).

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

### We collect the destination, not Stripe
*2026-08-23*

Stripe Checkout holds exactly one shipping address per session, so buying a
copy for the family and a copy for yourself in one payment was refused unless
the parents had already saved theirs — and the buyer, usually not a parent,
had no way to save it. The address was never Stripe's to hold: Printful ships
the mug, Stripe was a convenient form.

The buyer now names each destination on the send step and `collect_shipping`
is False in every case (`routes/checkout.py`). A buyer typing the family's
address never writes it to `births.shipping_address` — that field is the
parents' own record, not a guest's guess.

### The order snapshots the address it was bought against
*2026-08-23*

`gift_orders.shipping_address` is written at purchase, including when it's
copied from the parents' saved address. It is not re-read at shipping time.

> "the birth address can be updated, after all.. so a historical record at the
> time of purchase is only a good thing."

The payment was for a parcel to a particular place. If the family updates
their address between paying and shipping, an order already paid for
shouldn't quietly change destination — and a year later the order should
still say where it went. Every order names its own destination, so there's no
"null means look somewhere else" rule to remember.

### Ship to the US only, for now
*2026-08-23*

`GIFT_SHIPPING_COUNTRIES` is `"US"`. The address form offers no country
picker, because offering a choice the checkout would refuse is a wrong answer
waiting to be given. `address_validation.check_structure` still reads the
allowed list rather than assuming one, so widening is a config change plus a
form field.

### Address validation advises, it never refuses
*2026-08-23*

Structure — required fields, a country we ship to, a state code (Printful
won't take a US order without one) — refuses. Google's Address Validation API
only suggests the postal service's spelling and admits when it can't confirm a
place. New construction, rural routes and flats the postal file hasn't caught
up with are real addresses, and someone who knows where their sister lives
shouldn't be overruled by a database. Inert until `GOOGLE_MAPS_API_KEY` is
set; a Google outage never blocks a sale.

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

### Every overlay is a dialog, through one hook
*2026-09-04*

A dozen overlays — confirmations, bottom sheets, the gift editor, the
lightbox, the celebration — were each a dimmed `<div>` with an `onClick`.
None had a dialog role, moved focus, closed on Escape, or kept Tab inside,
so a keyboard or screen-reader user was left on the page behind. They all go
through `frontend/src/hooks/useDialog.js` now: one ref on the panel gives it
role, name (its first heading, or a label), focus in and back, Escape, a tab
ring, and a scroll-locked page. The role and name are set on the DOM by the
hook rather than repeated in JSX, so adding a sheet stays one line.

Alongside, from the same review: the contraction clock is a `role="timer"`
that announces nothing on its own (a screen reader must not read every
second) with a status line that says "in progress" and "no contraction"
once; motion that carries no information stops under `prefers-reduced-
motion`; the landing carousel can be paused (WCAG 2.2.2); a global
`:focus-visible` ring, since the custom buttons hid the browser's.

**Where:** `useDialog.js` and its call sites (`Modal.jsx`, `Lightbox.jsx`,
`GiftWizard.jsx`, `GiftGallery.jsx`, `ThemePickerSheet.jsx`, `PoolPill.jsx`,
`AccountPage.jsx`, `CelebrationOverlay.jsx`); `ContractionButton.jsx`;
`index.css`; `PhoneCarouselSection.jsx`. The rest of the review is in idea.md.

### The public pages are pre-rendered at build time; the rest stays a single-page app
*2026-09-02*

Someone searching "arrival story" should find the site, and a link pasted
into a family group chat should unfurl with a title and a picture. Four
pages are public — `/`, `/pricing`, `/privacy`, `/terms` — and their content
is the same for every visitor, so `npm run build` renders them to static
HTML with React's server renderer (`frontend/src/entry-server.jsx`,
`frontend/scripts/prerender.mjs`) and nginx serves `pricing/index.html`
before falling back to the SPA shell, which lives on as `app.html` because
`index.html` is now the home page. The browser hydrates the markup and
carries on as the SPA it always was.

> "the rest of the app can remain a SPA.. but.. in hindsight.. I do need
> someone to be able to search and find 'arrival story'"

- **No Next.js, no runtime server rendering.** A second framework, router,
  Tailwind config and deploy for four static pages; or a Node process on the
  box for output a build step produces identically. Build-time rendering
  gives a crawler the same bytes SSR would and adds nothing at request time.
- **One source for what a page says about itself:** `src/seo/routeMeta.js`.
  The pre-render writes it into each page's head; `usePageMeta` applies it
  on client-side navigation. Titles under 65 characters, descriptions under
  160, JSON-LD for Organization and WebSite only — nothing invented.
- **A family's page is never for an index.** `/b/`, `/invite/`, `/account`,
  `/setup`, `/login` are `noindex, nofollow` twice over: as an
  `X-Robots-Tag` header from nginx and as a meta tag from the app. Real
  `robots.txt` and `sitemap.xml` replace the shell that used to answer for
  them with a 200. `robots.txt` deliberately does **not** disallow the
  private routes: Disallow stops the fetch, so a crawler would never see the
  noindex and could still list a leaked URL bare. It blocks only `/api/`,
  and carries no comments — it is a public file, and listing the private
  paths in it would be a map.
- **The demo phones are client-only on purpose.** `PhoneFrame` renders its
  screen empty until mount: the demo timelines are built from `Date.now()`
  and the visitor's locale, so what the build machine rendered could never
  match the browser and React would throw the page away. The frame itself
  pre-renders at full size so nothing moves.
- **The landing page renders while auth is loading** instead of returning
  nothing. The session is an httpOnly cookie, so the browser cannot know it
  is signed in before `/me` answers; the first client render has to match
  the pre-rendered logged-out page. A signed-in parent sees the hero for
  that round trip before landing on their page, where they used to see a
  blank.
- **Media queries start at a fixed answer** (`useMediaQuery`): the poster,
  not the video; the pen not yet down on the wordmark. The real answer
  arrives in an effect a frame later, so server and first paint agree.
- **Getting found is a step only the owner can do:** verify the domain in
  Search Console, submit the sitemap, request indexing. The code makes the
  pages worth indexing; that makes them indexed.

### Logs are files on the box plus a 30-day table the admin site reads
*2026-09-01*

No Datadog, no Kibana — the same reasoning as the analytics entry above.
Every record from the web process and the worker goes three ways
(`backend/observability.py`): stderr for journald, JSON lines under
`/opt/lily/logs/<service>.jsonl` rotated ninety days by logrotate, and the
`app_logs` table for INFO and above, which the admin site's Logs page shows
(`frontend-admin/src/pages/LogsPage.jsx`, shaped after Datadog's explorer:
facets, search, a stripe per level, the whole record on click).

> "don't need datadog.. but I need to at least be writing to log files that
> I can monitor."

- **Per-request access lines go to files only.** The table is for what the
  app *said*, not every request it answered; the access line has the request
  id and is there when a trace is needed.
- **Table retention is thirty days**, swept hourly by the worker's idle loop.
  Files keep ninety.
- **Every response carries `X-Request-Id`**, and a 500 body says it too, so
  a failure a family reports is one lookup, not archaeology.
- **`/health` is public and answers 503** when the database can't be
  reached or the worker hasn't been heard from in two minutes, so an outside
  uptime check can be pointed at it with no further work.
- **`app_logs.user_id` is a plain column, not a foreign key.** A rolling
  log table must not slow down or block an account deletion; a UUID with no
  row behind it says nothing.
- **Nothing personal goes in a log line.** Callers log ids and counts; the
  `Enrich` filter redacts anything shaped like an email, a phone number, or
  a token that slips through, in messages and tracebacks alike. The dev-only
  console messenger deliberately keeps using `print`, which the logging tree
  never sees, because its lines are sign-in codes.
- **Alerting is a follow-up**: a Resend digest of new `fingerprint`s, which
  is why every row carries one.

---

<!--
Compiled 2026-08-08 from all 14 sessions in this project directory, plus
rationale already written into commits and code comments. Entries without a
commit hash come from conversation and were checked against current behavior
where possible. Correct anything misattributed.
-->

## The story frame's photos are ticked, not placed

*2026-08-27.* The story frame borrowed the wall's editor: pick a panel, then
choose its photo. On the wall that's the right model — the panels are free
and any photo can sit anywhere. On the story it's a lie: a photo's place on
the line *is* the moment it was taken, so swapping panel five for a photo
from three hours later puts it at the wrong point in the day. The only real
decision a parent has is which photos make the line — the line has a length
budget (`story_thin`, an inch a photo) and drops photos evenly when the day
has more than fit.

So the story's photo section is a **roll**: every day photo in order, each
with a tick. Ticked ones are on the frame at their true time; unticked are
left off. The thinning picks the initial ticks; a parent's ticks are stored
as `layout_overrides.story = {off: [...], on: [...]}` — *off* never boards,
*on* is pinned past the thinning, and the rest stay the thinning's to
decide, so unticking one brings the next dropped photo back on its own. When
the line is full the remaining ticks grey out with "untick one to make room";
nothing moves that the parent didn't move. `/gifts/{rendering}/story-roll`
answers a draft the way `book-plan` does, so the ticks never guess.

Crops on the story are keyed by the photo's media id rather than its slot
index: positions shift as photos come and go, the photo doesn't. There is no
upload for this design — a photo that never rode the timeline has no time
and so no place on the line. The wall and the book keep the picker.

Per-slot `photo_slots` overrides saved against the story before this are
ignored at render, as are its old index-keyed crops.

Notes and milestones don't get ticks. Milestones always stay; notes are
capped at eight, sampled evenly, before any photo is thinned — and that
stays automatic. A single roll of every moment with a shared budget was
considered and declined (2026-08-27) as too much editor for the gain.

## A gallery page in the book carries its own photos

*2026-08-28.* Moving a gallery page did nothing you could see. Photo slots
are handed out by walking the finished page list (`plan_book`), and the day's
photos fill slots 0, 1, 2… in order — so a page moved, the photos were
re-dealt by the new positions, and everything landed where it started.
Swapping two gallery pages produced a byte-identical plan. Moving a gallery
*past a notes or ruled page* did work; gallery-past-gallery was a no-op.

A gallery page now carries its photos in the arrangement:
`{"kind": "gallery", "count": 2, "photos": [media_id, …]}`. Moving the page
moves them; choosing a photo writes it onto the page rather than into a
numbered slot; the auto sample fills only what a page hasn't been given.
`book_slot_choices` turns the pages back into the slot→photo map the renderer
wants, with any index-keyed `photo_slots` from before as its base, so a book
arranged under the old shape keeps its picks.

The same reason the story's photos are ticked rather than placed: what the
parent moves should carry what's on it. Crops on the book key by media id for
the same reason — a slot number means nothing once pages move. The wall and
the filmstrips keep index-keyed crops: their slots are fixed positions.

The first rearrange pins every gallery page to the photo it was showing.
That's the point — from then on the order is the parent's, not the day's —
and *Reset to default* hands it back.

## The book's editor shows the parent's pages, not the printer's twenty-four

*2026-08-28.* The strip padded itself to twenty-four with ruled filler pages,
so removing a page appeared to do nothing: the count never moved, and a
filler quietly took the removed page's place. Telling the parent how many
were "still free to fill" made the arithmetic visible but kept the padding in
their book, which isn't theirs.

The strip now shows only the pages the parent has made — remove one and it
says *Page 19 of 19*. The partner still binds twenty-four and no other
number, so at **Next** a shorter book is told what will happen: *"Your book
has 19 pages. The book is bound with twenty-four pages, so we need to add 5
ruled pages at the back, for writing in. If you'd prefer, you can go back and
fill it yourself."* **Add them and continue**, or **Go back** and
fill them yourself. The + is refused only at twenty-four.

> "have a warning where it actually does decrease the pages … they can either
> continue, hit go back, or cancel, so they can add the pages themselves"

Nothing about the printed book changed — `plan_book` fills to twenty-four
exactly as before. The fillers simply stop pretending to be the parent's
pages before they've agreed to them, which is why the arrangement the editor
sends no longer carries them.
## Postage is charged, per parcel, at the partner's rate

*2026-08-27.* Printful bills us shipping on every order — $5–$10.50 inside
the US, per parcel — and nobody was paying it. The prices carried roughly one
parcel's worth, and a "both" purchase (a copy to the family and one to the
buyer) was two parcels for zero postage; the sheet even said *Shipping
included*.

Postage is now its own line. At checkout each order's destination is quoted
against Printful's `POST /shipping/rates` (`gift_shipping.quote`), the
cheapest service they offer is what's charged, and the number is written onto
the order (`gift_orders.shipping_cents`, migration 0040) beside the address
it was quoted for. Stripe shows the item and a *Shipping* line (two parcels
→ *Shipping (2 parcels)*); the order records the total for its own copy, so
a two-address purchase can carry two different postages and the refund of a
lost family claim is still exact. The sheet asks for the same quote as the
address is typed (`/gifts/{rendering}/shipping-quote`) and the pay button
carries the total, so Stripe's page never shows a number the buyer hasn't
seen.

When the partner can't be asked — their rates call fails, or no partner is
configured — the product's flat stand-in (`shipping_estimate_cents`, their
Aug 2026 flat rates) is charged instead and the order says so
(`shipping_estimated`). A partner outage at the moment of paying is not the
buyer's problem, and a guess should admit it is one.

### The catalog price is the item; postage is charged on top

*Decided 2026-08-31.* The prices were first worked out with a parcel's
postage inside them — the framed print as $35.70 + ~$10.50 to ship, the book
as $11.23 + ~$7.50 — back when the sheet said *Shipping included*. Breaking
postage out left that open: was $79 meant to be the all-in number, or the
price of the print?

The price of the print. The catalog price is the item, and shipping is added
to it, quoted live for wherever the parcel is going.

> "the buyer has to pay for shipping on top of my base price. that's what i
> want."

So the base prices stay where they are and are **not** to be "corrected"
later by someone reading the old arithmetic and assuming postage was
double-counted. A mug is $18 plus its postage, a framed print $79 plus its
postage. `gift_catalog_items.base_price_cents` is the item alone;
`gift_orders.shipping_cents` is the parcel.

## A book page is stored three ways: raw, display, thumbnail

*2026-08-28.* Clicking a page in the book editor left it blank for seconds.
The pages weren't thumbnails: `book_pages` handed the editor the print files
— 2325px PNGs, up to 2.4MB a page — so the browser downloaded a
multi-megabyte file to draw a 48px tile, and twenty-five of them to open the
strip.

A page is now stored at three sizes, the shape Pearl settled on
(`services/image_processor.py`, `?variant=thumbnail|display|raw`):

| variant | what it is | size | for |
| --- | --- | --- | --- |
| raw | the 2325px print PNG | 31.58 MB a book | the order; untouched |
| display | 900px WebP q82 | 0.78 MB (32KB a page) | the page on screen |
| thumbnail | 300px WebP q85 | 0.17 MB (7KB a page) | the page strip |

Measured, not estimated: every object read back and summed. Opening a book
went from ~31.6MB to 0.17MB for the strip plus 32KB for the page you're on.

**Made at render time, not on request, and not by a new worker.** The
derivatives ride along with the render that already happens off-request (a
book's render is scheduled as a background task from `save_gift_design`),
which is where the print files are written too — one pass, one place. The
whole render, twenty-five pages and their fifty derivatives including every
upload, is ~14s. Pearl makes its derivatives inline in the upload request
and reserves Celery for embeddings; ours are further off the request path
than that, so a queue would buy nothing yet. It would start to matter if
renders got long enough to outlive a deploy restart, since a background task
lost that way leaves the rendering `pending` until something re-renders it.

A book rendered before a variant existed falls back to the next size up and
ultimately to the print file (`{**raw, **display}`, `{**display, **thumb}`),
so nothing needs re-rendering to keep working — it gets fast when it next
renders. A derivative that can't be made is logged and skipped; a thumbnail
is never a reason to fail a render.

And the wait itself is now visible: the page dims under a spinner until its
image has arrived, rather than sitting blank as if broken. The strip's tiles
fade in and load lazily.

> "I was confused why the page wasn't loading … generate thumbnails, raw, and
> display … don't we need to have a worker of some sort?"

## The book's print files are made when it's ordered, not when it's saved

*2026-08-29.* Every save of a book design rasterized all twenty-four pages
**at print resolution** — 2325px files nobody was going to look at, since the
editor draws them 900px wide, and that only a buyer would ever need. It cost
14.3s, a **+195MB** memory spike, and 31.6MB written to S3 on every save of a
design that may never be ordered.

A save now draws the pages for the screen (`page_width`), and the print files
are made once, on the way to the partner (`ensure_print_pages`, called from
`submit_shipment`). Files are handed to a sink as they're rasterized rather
than collected, so a book costs one page of memory instead of twenty-five.

| | before | after |
| --- | --- | --- |
| save | 14.3s, +195MB, 31.6MB stored | **6.1s, +144MB, 1.2MB stored** |
| order | — | 11.0s, +123MB, once per book sold |

The cover keeps its print size at save: it's what the partner photographs for
the mockup, and it's one file. The remaining memory at save is rasterization
surfaces (the cover alone is a 5370×2850 cairo surface) and the photos
embedded in the SVG as data URIs — not the page files, which is what the
earlier +195MB was mostly made of.

> "I don't think we need to render all of the pages … we're doing needless
> work"

**Printful was never part of this.** A book has only ever been photographed
by its cover — one mockup call, Front and Back. The waste was all ours.

`ensure_print_pages` is idempotent and makes only what's missing, so a retried
shipment costs nothing, and a book ordered twice renders its pages once.

## Photos are stored three ways, and a worker makes the two small ones

*2026-08-29.* Every image was served at upload resolution, to every surface,
however small it was drawn. `GET /media/{id}` presigned `original_s3_key`
and redirected — the only thing it could serve — and `api.mediaUrl(id)` was
the only way the client could ask. Measured locally: fifteen photos, **42.0
MB, 2,867 KB each**. The gift editor's picker mounts one `<img>` per photo in
the whole birth at ~57px, none lazy; the book strip's `PageGlyph` draws them
at **22px**. `width`/`height` were NULL on every row because nothing had ever
decoded one.

A photo now has three forms, the shape Pearl settled on:

| variant | what | measured |
| --- | --- | --- |
| `raw` | the original, untouched | 2,867 KB |
| `display` | 1600px WebP q82 | **186 KB** |
| `thumbnail` | 320px WebP q85 | **14 KB** |

That picker: **42.0 MB → 0.20 MB, 211× lighter.** A timeline photo: 2,867 KB
→ 186 KB. A gift render pulls 1.39 MB where it pulled ~20 MB of originals.

**1600, not 2048.** The timeline photo is 736×384 CSS — 1472 device px on a
2× screen — and `gift_artwork._photo_data` already capped at 1600. The only
surface that wants more is a full-screen lightbox on a big retina display,
and that is better served by the original on demand than by making every
timeline photo 60% heavier. So the lightbox loads `raw`, showing the display
copy it already has cached until the original arrives.

**A worker makes them, not the request.** `scripts/media_worker.py`, its own
process — `lily-worker.service` in prod, a compose service in dev. An upload
writes the original and returns; the worker claims a photo a moment later
with `FOR UPDATE SKIP LOCKED`, in one statement, committing *before* it
touches S3 — holding a row lock across a network round trip is the
idle-in-transaction pattern that blocked a migration here in July. A claim
older than ten minutes is taken as abandoned and retried; a file Pillow
can't read records `variants_error` and is retired rather than retried
forever.

**Missing means fall back to the original.** That is what made this safe to
ship ahead of the worker and why there was no backfill to write: every
reader keeps working and the app simply gets lighter as copies appear. It
also means the worker can be stopped at any time without breaking anything.

`hot_s3_key` / `cold_s3_key` were left alone. They are for the storage-tier
lifecycle — moving a birth's media to cold storage when a family stops
paying for the page to stay live — which is a different axis from
resolution.

> "the client is trying to work with full sized images when it needs
> thumbnails"

The worker deliberately does **not** take gift renders yet. It can't push SSE
either (`events.py` is an in-process broker) — nothing here needs it, since
a client that loaded the original before a variant existed just gets the
variant next time.
