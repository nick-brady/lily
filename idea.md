# Contractions when the signal drops

*Written 2026-08-30. Not built — thinking, mostly.*

## The problem

A tap on the contraction button with no connectivity throws, sets the error
banner, and is gone. There is no service worker, no queue, no retry, and
nothing in local storage: `handleStart` awaits the POST and that is the whole
mechanism. The button state is derived from server events, so the UI simply
never leaves START, and the contraction that just happened is not recorded
anywhere.

Labour happens in hospital rooms, basements, car parks and lifts. This is the
one interaction in the product that cannot afford to need the network, and
it is currently the one most dependent on it.

> "I think what ultimately I'm going to have to do is really think about how
> internet intermittency is going to work with this. Likely, though, I'm going
> to say the web is somewhat limited in this, and this would be more of
> something that can be managed in an iPhone or Android application."

## Where the web genuinely runs out

Worth being honest about which parts are hard limits and which are just work:

**Solvable on the web, and not that hard**
- A tap survives a dead network: write it to IndexedDB first, sync when the
  connection returns. The tap time is the truth; the POST is just delivery.
- Surviving a reload or a closed tab, same way.
- A service worker keeps the page loading with no signal at all.
- `navigator.onLine` plus a failed request is enough to know to queue.

**Hard on the web**
- **The screen locking.** iOS Safari suspends timers and JavaScript when the
  screen locks. A running contraction cannot tick, and a tap cannot be
  captured while the phone is in a pocket. Wake Lock helps only while the tab
  is foregrounded and the battery allows.
- **Background sync.** Chrome has Background Sync; Safari does not. On iOS a
  queued tap only leaves the device when someone opens the page again.
- **Being reachable at all.** No lock-screen control, no widget, no
  complication, no volume-button shortcut. In labour, unlocking a phone and
  finding a tab is a real cost.
- **Notifications.** Web push on iOS requires the site be installed to the
  home screen first, which nobody does mid-contraction.

So the web can be made to *never lose a tap*. What it cannot be is *ready to
hand* — and during labour that may matter more.

## What that suggests

Two pieces, and they are independent:

1. **Make the web lose nothing.** Queue taps locally and reconcile on
   reconnect. Worth doing regardless of whether an app ever exists, because
   it is also what makes the app's sync story simple: the server already has
   to accept a tap that happened three minutes ago.
2. **A native app for the timing itself.** Lock-screen and watch access,
   background execution, local notifications, a widget. The web page stays
   what it already is — the thing the family follows.

## What the server would need either way

Mostly it is ready, and this week's work moved it closer:

- `start` already accepts `occurred_at`, so a queued tap can carry the time
  it actually happened rather than the time it was delivered. `PastDatetime`
  allows it with a 60s skew tolerance — a longer offline window would need
  that bound revisited.
- `stop` now stamps the server clock, which is right for a live tap and
  **wrong for a replayed one**. A queued stop would need to supply its own
  end time, and the route would have to trust it. Worth designing before
  building the queue, not after.
- Ordering. Two devices queueing offline, then both syncing, can deliver a
  start after a stop. `uq_timeline_events_one_open_contraction` will refuse
  the second open contraction, which is the right instinct but the wrong
  error for a replay.
- Idempotency. A retried delivery must not create a second contraction. A
  client-supplied id on the event would settle it — there is none today; ids
  are `gen_random_uuid()` server-side.

None of that is a reason to wait. It is a reason to decide the offline
contract first, since it is the same contract the app would use.

---

# Alerting, without a vendor

*Written 2026-08-31, as part of "Seeing it fail". The rest of that piece was
built 2026-09-01 — see the DECISIONS entry "Logs are files on the box plus a
30-day table the admin site reads". This is what's left of it.*

Resend is already a dependency for transactional email. A cron that reads the
last stretch of `app_logs` and emails a digest when there is anything at
WARNING or above would cover the whole need — no new service, no account, no
bill, and it fails in the safe direction (a missed email, not a missed
outage). Every row carries a `fingerprint` for exactly this: the digest can
say "new failure" and "seen 40 times since Tuesday" rather than listing lines.
If it ever gets noisy, that is also the natural point to reach for something
bought.

The one thing it cannot cover: a log on the machine cannot report that the
machine is gone. `/api/health` exists so an outside uptime check can.

---

# A basic accessibility review

*Written 2026-09-02. First pass done 2026-09-04 (code audit + fixes, PR
"Accessibility: every overlay is a dialog…"); the browser pass is still to do.*

## Done in the first pass

- Every overlay is a real dialog: `hooks/useDialog.js` gives the Modal, the
  lightbox, the gift editor, the bottom sheets, the account-deletion dialog
  and the celebration a role and name, moves focus in and back, closes on
  Escape, keeps Tab inside, and stops the page behind scrolling.
- The timeline photo opens from the keyboard; icon-only buttons (theme
  toggle, menu, remove photo/video, record, discard, gap marker, delete,
  cancel contraction) have names; every placeholder-only field has a label.
- Live regions: connection status, the page error and gift banners, admin
  errors; the contraction clock is a `role="timer"` that stays quiet with a
  status line that announces start and stop once.
- Motion: the STOP pulse, sheets, confetti and pings stop under reduced
  motion; the landing carousel has a Pause button.
- A global `:focus-visible` ring; the timeline's 24px icon buttons and the
  post Edit/Delete links have 40px hit areas; the admin warning pill has
  dark text; the private routes have their own tab titles; the settings
  page's sections are h2 under its h1.

## Still to do

- **The browser pass**: axe DevTools on each page, a keyboard-only pass of
  the parent flow, VoiceOver on an iPhone through a birth page as a viewer.
  The code audit can't see contrast or what a screen reader actually says.
- **Landmarks on the app pages**: `/account`, `/setup`, `/login` and the
  invite page have no `<main>`; the setup wizard's steps each carry an h1.
- **Transcripts**: uploaded videos and voice memos have no captions or
  transcript, and the composer's previews neither.
- **Errors tied to their fields**: no `aria-describedby`/`aria-invalid`
  anywhere; hints and errors float beside inputs.
- **Contrast**: measure `t-faint` (#9ca3af) and `text-gray-400` on white for
  the timeline timestamps and secondary copy; the dark-mode faint pair is
  the tightest.
- **Header menu keyboard semantics** (arrow keys, focus on open); the tab
  switcher and segmented controls without `aria-selected`/`aria-pressed`;
  charts with no text alternative; `autoFocus` on page load pulling focus
  past content and raising the phone keyboard.

## How to check it

axe DevTools in Chrome on each page for the mechanical failures, then a
keyboard-only pass of the whole parent flow, then VoiceOver on an iPhone
through a birth page as a viewer — that last one is the audience.

---

# Every text the app sends, against what the campaign promised

*Written 2026-09-03. Not done — a compliance walk-through, not a feature.*

The Twilio A2P 10DLC campaign was registered with sample messages and a
described use case. Carriers and Twilio hold the sender to that: a text that
doesn't match the registered samples, or a number texted without the consent
the campaign describes, is what gets a campaign suspended. Nobody has walked
the customer journey end to end and compared what the app actually sends to
what was filed.

## What the app sends today (from `backend/messenger.py`)

1. **Sign-in code** — email only now (`request_challenge` rejects phones), so
   no SMS. Confirm the campaign doesn't still describe an SMS OTP.
2. **Opt-in confirmation** (`send_notify_optin`, on saving a notify phone):
   "Arrival Story: you're set — we'll text you the moment labor begins. Birth
   updates only, ever. Msg & data rates may apply. Reply STOP to opt out."
3. **Invitation** (`send_invitation`, when a parent invites by phone): "{name}
   invited you as a {role} to {baby}'s page on Arrival Story: {link} Reply
   STOP to opt out." — sent to someone who has not personally opted in,
   on the strength of the parent's relationship. Whether the campaign covers
   that is the first thing to check.

## What to check, in journey order

- **Signup and phone capture.** Where is the number collected, what consent
  language sits next to the field, and does it match the campaign's
  "how consumers opt in" description word for word?
- **The invitation text.** Is a parent-initiated invite covered by the
  campaign's use case? If the campaign says "recipients opt in via the web
  form", it isn't. The fix might be wording on the invite screen, or
  registering the use case, or dropping SMS invites for email plus a link
  the parent shares themselves.
- **The promise in the opt-in text.** It says "we'll text you the moment
  labor begins." **Nothing sends that text.** `notify_phone` is written by
  the auth routes and read by nothing else — the born milestone and labour
  start send no SMS. Either build the birth alert (and register its sample)
  or stop promising it; a confirmation that promises a message that never
  comes is its own kind of problem.
- **STOP / HELP.** Twilio Advanced Opt-Out handles STOP; confirm HELP is
  configured and that a STOPped number is never texted again by the
  invitation path (it goes through the same Twilio number, so it should be
  blocked by Twilio — verify, don't assume).
- **Frequency and quiet hours.** State what the campaign promised; make sure
  the app cannot exceed it (e.g. repeated invites to the same number).
- **Records.** `notify_phone_opted_in_at` is the consent timestamp. Check
  it's set on every path that stores a number, and that clearing the number
  clears it.

- **The Terms' "Text messaging terms" section** promises two texts the app
  does not send — "a single 'first day' memory update after a birth" and "a
  yearly memory message about your own page" — and omits the invitation
  text it does send. The registered campaign, the Terms and the code have to
  say the same three or four things.

## How to do it

Sit with the Twilio console open on the campaign page and a phone in hand.
Walk the app as a new parent, then as an invited relative, and write down
every text received beside the sample it should match. Ten minutes of
texts, an hour of comparing.

---

# The keepsakes should say where they came from

*Written 2026-09-03. Not built.*

A book on a shelf and a mug on a desk are the two places a relative will see
Arrival Story a year from now, and neither says so. Both keepsakes should
carry the brand, and the book should carry the way back to the page.

## The book

A QR code on the first page (the title page, not the cover), pointing at the
birth page. Anyone who picks the book up can scan it and see the day itself —
the videos, the voice memos, the things a book can't hold. The page is
private and the link carries no token, so a scan lands on the sign-in, which
is right: the QR is a door for people who already belong, not an invite.

Sizing: a QR at 1 inch square with a quiet margin scans reliably from a
printed page; the title page has room.

## The mug

Two things, decided in conversation:

- **The Arrival Story wordmark**, small, somewhere it looks like a maker's
  mark rather than an advert. The script wordmark at ~0.6 inch on the wrap,
  opposite the design or under it.
- **A QR code, if anywhere, on the bottom.** The link itself printed on the
  mug was vetoed ("wife didn't like the idea of the link on the mug"), and a
  QR on the wrap competes with the artwork. The bottom is where a maker's
  mark goes on ceramics anyway.

The catch: Printful's mugs print the wrap only — the base is not a print
area on their 11oz/15oz mugs. So a bottom QR needs either a different
supplier for that product or dropping the idea for mugs and keeping it to
the book. Worth confirming on the product spec before designing around it.

Minimum size for a QR to survive sublimation on a curved wrap is ~0.8 inch;
smaller than that and the modules blur.

---

# Gift colours should follow the baby, not the brand

*Written 2026-09-03. Not built.*

Pink is Arrival Story's default and it suits the app. It does not suit a
radial sunburst for a boy. Today the gift palettes follow the birth's chosen
theme (`gift_themes.py`: lily, blossom, dino, ocean, golden, starry) and the
theme defaults to lily — so a family that never changes it gets pink
keepsakes whatever the baby.

## What to do instead

- **Default the gift palette from what is known.** Girl → lily or blossom.
  Boy → ocean. Not known (or not shared) → a neutral: dino's green, or
  golden. The birth already records the baby's sex once the pool settles,
  and the parents can set it at any time.
- **Keep it a default, not a rule.** The editor should offer the palette as
  a choice per design, prefilled from the above, so a family who wants a
  green sunburst for a girl gets one without changing the page's theme.
- **Don't retheme the page.** The app's own colour is the family's choice in
  settings and separate from what prints; the two only share a default.

## Where it touches

`gift_themes.for_theme` picks the palette; the renderers read `birth.theme`.
A `palette` field on the rendering (design) would carry the per-design
choice; the default would be derived from `birth.child_sex` when the theme
is the untouched default. Existing designs keep whatever they were rendered
with.

---

# Gaps that mark themselves

*Written 2026-09-03. Not built.*

When contractions weren't recorded for a stretch — sleep, a car ride, the
walk in from the parking garage — the parent has to tap the little clock on
the next contraction to mark a "gap before" it. That flag
(`ignore_interval_before` on the payload) is what keeps the stats honest:
the interval chart and the keepsakes skip that span rather than drawing a
two-hour-forty-minute "interval". It works, and nobody in labour is going to
remember to do it.

> "if there's a very high statistical probability there's a gap, then just
> assume there is … it should appear different than a gap that they manually
> assigned."

## The rule

A contraction's interval is a gap when it is wildly out of step with the
ones around it — say more than five times the median of the previous few
intervals, and at least twenty minutes. Lily's real data has two: 2h40m and
3h05m, in a night where contractions were three to five minutes apart.
Nothing near the boundary; the threshold can be generous.

Three states per contraction, not two:

| `ignore_interval_before` | means | drawn as |
| --- | --- | --- |
| `true` | the parent marked it | the gap pill as today |
| absent, and the rule fires | assumed | the same pill, lighter, "gap before?" |
| `false` | the parent said *no gap* | nothing; the interval counts |

Absent-and-quiet is the common case and draws nothing. The parent's answer,
either way, is stored so it never gets asked twice and never gets re-inferred
after a "no".

## The interaction

Tap the lighter pill: *"We assumed a gap here — 2h 40m after the previous
contraction, when they'd been about four minutes apart. Is that right?"*
**Yes, there was a gap** writes `true`. **No, they kept coming** writes
`false`. Tapping outside cancels and leaves it assumed. The existing clock
button still toggles a manual mark for the cases the rule misses.

## What treats it as a gap

Everything that reads the flag today — `gift_stats`, `export.py`, the stats
panel — reads one function instead: *is there a gap before this contraction*,
which returns the explicit flag when present and the inference otherwise. So
an assumed gap is a gap for the charts and the keepsakes from the moment it
appears, and confirming it changes only how it's drawn. The inference lives
in one place, server-side, and rides out on the event as `gap_assumed` so the
client draws rather than decides.

## Worth deciding

- Whether the assumed state should also be shown to viewers, or only to the
  parents who can answer the question. Probably parents only.
- Whether a *manual* mark should suppress the question on neighbours — a
  parent who marked one gap has shown they know the control exists.

---

# Approve orders automatically after a grace window

*Written 2026-09-04. Not built — and deliberately not yet.*

Every Printful order is a draft until someone approves it, and today that
someone is Nick, from the admin Orders page. That is right for now: nobody
has held a mug or a book from this pipeline yet, so every order is still a
chance to catch a bad crop or the wrong product before money moves. It is
also the only step in the whole flow that waits on a human, and if orders
ever arrive faster than one person checks their phone, each one sits for a
day for no reason a buyer would accept.

## The shape

A timer, not a flag. Approve at payment time and you lose the cancel path,
the claim race for family gifts, and the veto; wait for a human and you lose
the day. Thirty minutes buys all three for nothing.

- **A grace window** (30 minutes, a setting) during which the buyer can
  cancel from the receipt and the operator can still veto from the admin
  page. That window already covers the two moments cancels actually happen:
  "oops, wrong address" and "my sister just bought the same one".
- **The worker approves when the window closes,** on the housekeeping tick
  that already runs every five minutes: paid, draft at the printer,
  `paid_at` older than the window, not on hold, not failed, not cancelled.
  The same `approve_shipment` the admin button calls, recorded with no
  `confirmed_by_user_id` — approved by the clock, and the log says so.
- **Off by default.** An environment setting (`AUTO_APPROVE_AFTER_MINUTES`,
  unset means never) turned on once enough real orders have come out right.
  The admin button keeps working either way, for approving early while
  watching, or for the one that needs a look.
- **The buyer's copy gets a deadline.** "You can cancel until we send it to
  print" becomes "You can cancel for the next 30 minutes", with the actual
  time shown on the receipt page and in the receipt email. More honest than
  the open-ended promise, and it explains the wait.
- **Nothing on hold auto-approves.** Printful holds are questions; a person
  answers them.

## When

After the first handful of orders have arrived looking right — the trigger
is trust in the artwork pipeline, not order volume. Until then the manual
step is the quality gate and costs a few minutes a day.

**Where it would go:** `Housekeeping` in `backend/scripts/media_worker.py`
(a fourth tick), `approve_shipment` in `backend/repositories/gift_orders.py`
already does the work, `orderPresentation.js` and `gift_receipt_email.py`
for the deadline copy. Record the decision in DECISIONS.md when it flips on.

# Set up help@arrivalstory.com

*Written 2026-09-04. Not done — a mailbox task, not code.*

The receipt page and the receipt email now say "Questions? Email
help@arrivalstory.com", and replies to any Arrival Story email are addressed
there (`reply_to` on every Resend send). The address does not exist yet.

## What to set up

1. **Receiving.** Cheapest: Cloudflare Email Routing (the domain's DNS is
   already there for the site) forwarding `help@arrivalstory.com` to a
   personal inbox — free, five minutes, and replies can still be sent
   from the personal account with a "send as" alias. Or a Google Workspace
   seat if a real shared inbox is wanted later.
2. **Sending.** `RESEND_FROM` is `hello@arrivalstory.com`. Confirm the domain
   is verified in Resend (SPF, DKIM, DMARC records) so receipts don't land in
   spam; the sign-in codes have been going out from it, so this is probably
   done — check the Resend dashboard says "verified".
3. **The address in the app** is one constant in each codebase:
   `frontend/src/utils/support.js` and `messenger.SUPPORT_EMAIL` (env
   `SUPPORT_EMAIL` overrides). Change it in both if the address changes.
4. **Who reads it, and how fast.** A buyer quoting a reference expects an
   answer within a day. Decide where it forwards and that it is watched.

---

# The loop that already half exists

*Written 2026-08-31. Not built — a thing to decide, not a task.*

## The shape of this business is unusual

One purchase, no repeat, and a window of about nine months per customer that
opens and closes whether or not anyone is ready. Most products get to earn a
customer back next month; this one gets a single pass, at a moment nobody
schedules.

Which makes ordinary acquisition a poor fit. You cannot retarget someone into
being pregnant, and by the time a person is searching for something like this
they are often already past the part it is best at.

## But the distribution is already in the product

Every birth puts the page in front of a dozen relatives, and those relatives
are the most qualified audience this product will ever have: self-selected as
people who care about a new baby, watching the thing work at the exact moment
it is most affecting. Some of them are pregnant. More of them know someone
who is.

The mechanism to reach them exists and works — viewer invitations, a
shareable link, a page they will open on the day. **What does not exist is
any way for one of them to become a parent with their own page.** Grepping
the public birth page, the invitation redemption page and the timeline turns
up nothing that offers it: no "start your own", nowhere to go. The loop is
half-built, and the missing half is the cheap half.

## The hard part is timing, not placement

Someone watching a birth page is watching the *end* of someone else's
pregnancy. They need this at the *beginning* of their own — possibly a year
later. A call to action at the moment of highest feeling is aimed at a person
who has no use for it yet, and the ordinary answer (retarget them) is exactly
what this audience should not be subjected to.

So the interesting question is not where to put a button. It is what survives
the gap:

- something that reaches them later, at their own moment, without pestering
  them in between
- or something physical — a keepsake in a relative's house is a distribution
  surface with a shelf life measured in years, which is the one thing digital
  acquisition cannot buy
- or nothing at all, on the view that this spreads by people telling each
  other, and the job is only to be worth telling about

## The tension worth naming

This page is a family's private record of a day. The product's whole tone is
that it is not selling them anything while they use it — the keepsakes sit
apart, the gift shelf never interrupts. Putting acquisition on that page
risks the exact quality that makes it worth passing on. A tasteful version of
this matters more here than it would almost anywhere else, and a clumsy one
would cost more than it earned.

## One thing that is already in place

First-touch attribution is built and running: `ref` and `utm_*` are captured
on arrival, kept, and recorded against every visit and every signup. So
whatever gets built here can be measured from the day it ships, and the
question "did the loop work" has an answer rather than an opinion.
