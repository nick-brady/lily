# Image variants, and a worker to make them

*Written 2026-08-29. **Built 2026-08-30** — see the DECISIONS entry "Photos are
stored three ways, and a worker makes the two small ones". Kept for the
reasoning; the sizes landed at 1600/320 rather than 1600/300, and the
lightbox loads the original rather than the display copy.*

## The problem

Every image in Arrival Story is served at full upload resolution, to every
surface, however small it's drawn.

Measured on production:

| | |
| --- | --- |
| photos | 11 |
| total | 30 MB |
| **average** | **2.79 MB each** |
| `width` / `height` | NULL on every row |

`GET /media/{id}` presigns `asset.original_s3_key` and redirects — that's the
only thing it can serve. So the gift editor's photo picker, which draws
twelve of these as ~60px tiles, pulls about **33 MB to render a thumbnail
grid**. The timeline, the galleries and the crop box are all the same story.
Nothing knows an image's dimensions either, because nothing has ever decoded
one.

This is separate from the book's page files (see *Related*, below). It's the
general case, and it's the worse one.

## What we want

> "It's about how we manage images within Arrival Story completely. We should
> have: the raw image, a display image which is a web photo, a thumbnail
> which is a display photo. A worker process should be responsible for
> generating these images once the raw image is uploaded in the background so
> that it doesn't affect API response time."

Three variants per asset, the shape Pearl settled on
(`server_python/app/services/image_processor.py`, and its
`?variant=thumbnail|display|raw`):

| variant | what it is | for |
| --- | --- | --- |
| `raw` | the original upload, untouched | downloads, exports, print |
| `display` | 1600px WebP q82 | lightboxes, the crop box, anything looked at |
| `thumbnail` | 300px WebP q85 | grids, pickers, strips, anything scanned |

## How we'd build it

**Serving.** `GET /media/{id}?variant=thumbnail|display|raw`, defaulting to
`raw` so nothing existing changes. Same presigned redirect as today, same
auth gate. On the client, `api.mediaUrl(id, 'thumbnail')`; every grid and
picker asks for thumbnails, every lightbox and crop box for display.

**A variant that isn't ready falls back to `raw`.** That's what makes the
whole thing safe to ship before anything has been generated: the app works
exactly as it does now, and gets lighter as the worker catches up. It also
means no backfill script — production's eleven photos are just the first
eleven rows the worker claims.

**Generation.** Upload is untouched: write the original, return the timeline
event, done. No response gets slower. A worker claims assets whose variants
are missing, decodes once, writes both variants, and records their keys —
plus `width`/`height`, since it has the image open anyway.

**The worker.** Its own process, `lily-worker.service`, a sibling of
`lily.service` in the existing systemd role — so it's an Ansible template and
a unit file, not new infrastructure. No Redis, no Celery. It claims work with

```sql
SELECT ... FROM media_assets
WHERE kind = 'photo' AND archived_at IS NULL AND display_s3_key IS NULL
FOR UPDATE SKIP LOCKED LIMIT 1
```

which is transactional, survives restarts, and lets a second worker be added
later by starting a second unit.

### Where the keys live — decided: store them

The paths can be conventional (`.../thumbnails/{uuid}.webp`, as Pearl does)
but **whether a variant exists is a column**, not something we infer.

Pearl can get away with deriving both, because it generates its variants
inline in the upload request — by the time anything asks, they exist. Ours
are made later, by a worker, so "is it ready yet?" is a live question on
every single image request. Answered from a column it costs nothing; answered
from the bucket it's an S3 HEAD per image, or a 404 the browser has to eat.

Two nullable columns on `media_assets` — `display_s3_key`, `thumbnail_s3_key`
— give us three things a convention can't:

1. the worker's claim query, indexable, with no bucket listing;
2. an instant fallback decision, no round trip;
3. freedom to change size, quality or format later without orphaning
   everything silently.

A single JSONB `variants` map was considered — flexible for adding sizes
without a migration — but for two fixed variants it buys little and makes the
claim predicate fiddlier to index.

## Shape of the work

- migration: `display_s3_key`, `thumbnail_s3_key` on `media_assets`, partial
  index on the claim predicate
- `image_variants.py`: decode once, EXIF-transpose, produce both variants
- worker: claim loop, `lily-worker.service`, Ansible template in the systemd
  role
- `GET /media/{id}?variant=`, with fallback to raw
- client: `mediaUrl(id, variant)`, then every call site chooses one
- tests: fallback when absent, the claim doesn't double-serve, a bad image
  fails the row and not the worker

## Related, agreed, not started

**The book renders more than it needs to.** `render_book` rasterizes all
twenty-four pages *at print resolution* on every design save and holds them
all in memory — a **+195 MB** spike and ~14s, when the print files are only
needed if someone actually orders. Render pages at display size for the
editor; make the print files at order time. Roughly 6× less memory (2325² →
900² is 6.7× fewer pixels) and a much faster save.

(The mockup was never the problem: a book has only ever been photographed by
its cover — one Printful call, Front and Back.)

**Once the worker exists, gift renders should move onto it too.** Same two
wins: the memory spike leaves the web process, and a render stops dying with
a deploy restart. Today `render_rendering` is a FastAPI background task, and
nothing sweeps a rendering left `pending` when the process goes away.

**PR #75** already gives the book's pages raw/display/thumbnail variants in
this same shape. Whatever naming we settle on here, the two should match.

---

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

# Seeing it fail

*Written 2026-08-31. Not built.*

## The problem

If Arrival Story breaks for a family at three in the morning, nobody finds
out. There is no error tracking, nothing writes an application log to disk,
and `/api/health` returns 404, so there is nothing for an uptime check to
watch. The first signal would be a text message, or silence.

That matters more here than in most products. A labour happens once. A family
cannot come back tomorrow and re-record the night — so a bug during it isn't
an inconvenience to apologise for, it's a hole in the only account of
something that will never happen again.

> "this is a big deal … I want to make sure I have good logging on my system.
> don't need datadog.. but I need to at least be writing to log files that I
> can monitor."

## Where it stands

- **Nothing configures logging.** Six modules call `logging.getLogger`, but
  no `basicConfig` or `dictConfig` runs in the web app, so those lines go
  wherever uvicorn's defaults send them. Five places still use `print()`.
- **Everything lands in journald** — persistent on this box (106 MB so far),
  size-capped with no time limit. Fine for reading after the fact; not a file
  you can tail, grep on a schedule, or ship anywhere.
- **`/opt/lily/logs` already exists**, created by the `common` Ansible role,
  and is empty. The intent was there.
- **nginx has access and error logs**, rotated 14 days — the only real log
  files on the machine.
- **One HTTP middleware exists** (`slide_session_cookie`, `main.py:55`), so
  there is already a place a request-logging middleware would sit.
- **`/` returns `{"name": "arrival-story", "status": "running"}`** without
  touching the database — it says the process is up, not that the app works.

## The shape of it

**A health endpoint worth monitoring.** `/api/health` that actually asks the
database a question and reports the alembic revision. Unauthenticated, cheap,
and honest: a 200 should mean "this can serve a family", not "a process is
listening". Then any uptime checker — an external ping every minute — has
something real to watch, and it covers the case where Postgres is down but
uvicorn isn't.

**Structured logs, to files, under `/opt/lily/logs`.** One line per event as
JSON, so it can be grepped now and parsed later without rewriting anything:

- a request log — method, path, status, duration, and *who* (user id, not
  name or email)
- a **request id** on every line, returned in a response header, so "it broke
  around 3am" becomes a single trace rather than an archaeology exercise
- unhandled exceptions with their traceback, which currently reach journald
  at best
- the media worker to its own file; it already logs properly and only needs
  somewhere to put it

Rotated by logrotate like nginx's, with a retention window chosen on purpose
rather than inherited.

**What must never be logged.** This is the sharp edge, given everything else
we've decided about privacy. No captions, note bodies, photo contents, file
names, email addresses, phone numbers, or child names. A log file is the
easiest place for the data we have been careful about everywhere else to leak
out sideways — into a backup, a support paste, or a screenshot. User *ids*,
birth *ids*, and paths are enough to debug with; if something needs more, it
should be looked up in the database deliberately, not left lying in a file.

**Alerting without a vendor.** Resend is already a dependency for
transactional email. A cron that reads the last few minutes of the error log
and emails a digest when there is anything in it would cover the whole need —
no new service, no account, no bill, and it fails in the safe direction (a
missed email, not a missed outage). If that ever gets noisy, it is also the
natural point to reach for something bought.

## Worth deciding early

- **Retention.** The same storage-limitation question as `page_visits`, and
  the same answer: pick a window rather than letting it grow forever.
- **Sampling.** At this size, log everything. It is worth knowing now that
  the request log is the first thing that would need thinning later.
- **Where errors go when the box is the thing that broke.** A log file on the
  machine cannot report that the machine is gone; only the external uptime
  check can. The two are not substitutes for one another.
