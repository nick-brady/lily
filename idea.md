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

*Written 2026-09-02. Not done.*

Nobody has gone through the app with a keyboard or a screen reader. The
audience makes this matter more than usual: grandparents on phones, a parent
in labour who can't look at the screen, a relative with low vision following
along at 3am.

## What to check

- **The keyboard path** through setup, the contraction button, and the
  timeline: can every action be reached and fired without a pointer, and is
  focus visible everywhere it lands?
- **Focus management in `Modal`** (lifted to its own file in August): focus
  moves in when it opens, returns to the trigger when it closes, Escape
  closes it, and nothing behind it is reachable while it's open.
- **The running contraction.** A screen-reader user gets no announcement
  when one starts or stops; an `aria-live` region on the button's status
  would say it.
- **Colour contrast** of the muted text (`t-muted`, `text-gray-400`) on white
  and on the dark theme, and of the level pills on the admin Logs page.
- **Form labels** on setup and checkout: every input has a real label, not
  just a placeholder; errors are associated with their fields.
- **Reduced motion** is honoured by the hero and the carousel; check the
  timeline's photo reposition and the celebration confetti too.
- **The landing carousel auto-advances.** WCAG 2.2.2 wants a way to pause or
  stop anything that moves for more than five seconds. A visitor who
  navigates manually takes the wheel today; there is no explicit pause.
- **Alt text on uploaded photos.** They carry captions but no `alt`; the
  caption is the obvious alt when there is one, and "Photo" plus the time
  when there isn't.
- **`lang`, landmarks, and one `h1` per page** — done for the four public
  pages as part of the SEO work (2026-09-02); check the app pages.

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

## How to do it

Sit with the Twilio console open on the campaign page and a phone in hand.
Walk the app as a new parent, then as an invited relative, and write down
every text received beside the sample it should match. Ten minutes of
texts, an hour of comparing.

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
