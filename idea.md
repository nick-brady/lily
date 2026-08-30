# Image variants, and a worker to make them

*Written 2026-08-29. Not built. Come back to this.*

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
