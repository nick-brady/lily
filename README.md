# Lily

A live, shared birth experience that becomes a permanent keepsake. Families
track contractions, post photos / videos / voice memos, and narrate the day
as it unfolds — while loved ones watch in real time. After the birth, the
timeline lives on as a permanent record of the day their child arrived.

See `Lily-Product-Spec.md` for the full product spec and `Lily-Personas.md`
for the customer personas.

## Stack

- **Backend:** FastAPI + SQLAlchemy + Alembic + PostgreSQL 16
- **Frontend:** React + Vite + Tailwind (PR 2 rewrites the auth + multi-tenant flow)
- **Auth:** Magic link (email) + OTP code (SMS). Identity is phone OR email,
  no passwords. The dev `Messenger` prints credentials to the backend log;
  real Resend + Twilio providers land in a follow-up.

## Quick start (Docker)

```bash
cp .env.example .env
# edit .env — at minimum set JWT_SECRET_KEY and POSTGRES_PASSWORD
docker compose up -d --build
```

The backend serves on `http://localhost:8000`, the frontend on `http://localhost:3000`.
MinIO (S3-compatible storage) serves on `http://localhost:9000` with a web
console at `http://localhost:9001`. Media files persist in `./.data/minio/`
on your machine.

Migrations are **not** run automatically. See the next section.

### Product mockups need the tunnel — run it alongside the stack

Printful photographs our artwork onto the real product by **fetching the
artwork over the internet**. It cannot reach `localhost`, so without this
every mockup in local dev fails with `Generator failed: Invalid URL` and the
gallery shows flat artwork only. Whenever you're working on anything under
the gift gallery, run this in a second terminal and leave it open:

```bash
./scripts/dev-tunnel.sh      # needs: brew install cloudflared
```

It opens a free Cloudflare quick tunnel to the frontend (`localhost:3000`,
which proxies `/api` to the backend), writes the tunnel's URL into `.env` as
`ARTWORK_PUBLIC_URL`, and recreates the backend so signed artwork links point
at it. Ctrl-C closes the tunnel, clears the variable, and puts the backend
back on localhost. A new hostname every run; nothing to configure.

`ARTWORK_PUBLIC_URL` is deliberately separate from `FRONTEND_URL`: that one
also decides cookie security and Stripe's return address, and pointing it at
a tunnel would break login.

Mockups still cost Printful's budget — **2 a minute for the whole store** —
so the app generates one per design automatically and otherwise only when
someone asks in the editor. Don't loop over them.

### Media storage (S3 / MinIO)

Uploads go to S3 via boto3 — the same code path as production. In dev,
Compose runs MinIO and points the backend at it. In prod, leave
`AWS_ENDPOINT_URL` unset and use real AWS credentials + bucket.

After bringing the stack up, migrate any legacy on-disk uploads once:

```bash
docker compose exec backend python scripts/migrate_local_to_s3.py
```

`GET /media/{id}` checks audience access, then redirects (307) to a
short-lived presigned S3 URL.

## Running migrations

```bash
docker compose exec backend alembic upgrade head
```

For the PR 1 cutover (legacy single-tenant → multi-tenant), see
[Migrating from the legacy schema](#migrating-from-the-legacy-schema).

## The media worker

A second process makes the smaller copies of uploaded photos — a 1600px
`display` and a 320px `thumbnail`, beside the untouched original — so the
browser never downloads a 4000px photo to draw a 57px tile. It comes up with
the rest of the stack:

```bash
docker compose up -d worker           # runs already; this is just the name
docker compose logs -f worker
docker compose restart worker         # no --reload: restart to pick up edits
```

An upload never waits for it. A variant that hasn't been made yet serves the
original, so the app works with the worker stopped — it simply serves bigger
files until it catches up. Ask for a size with
`GET /media/{id}?variant=display|thumbnail`; the default is the original.

In production it is `lily-worker.service`, a sibling of `lily.service`,
installed by the same Ansible role and restarted by the same deploy.

```bash
systemctl status lily-worker
journalctl -u lily-worker -f
```

A photo Pillow can't read records `variants_error` and is not retried;
clearing that column re-queues it.

## Migrating from the legacy schema

The PR 1 cutover replaces the single-tenant `contractions` / `updates`
tables with the multi-tenant family / users / births / timeline model.
The migration is staged:

1. **Apply alembic 0002** — creates the new tables alongside the legacy
   ones:

   ```bash
   docker compose exec backend alembic upgrade 0002
   ```

2. **Run the data migration script** — backs up the legacy tables to
   `/tmp/lily_legacy_backup_<timestamp>.json`, then copies contractions
   and updates into `timeline_events` (and media into `media_assets`)
   under a seeded `The Brady Family` row with a single `births` record
   for Lily Wren:

   ```bash
   docker compose exec backend python scripts/migrate_to_multitenant.py
   ```

   Set `SEED_OWNER_EMAIL` (and optionally `_PHONE`, `_NAME`) plus the
   `SEED_COPARENT_*` equivalents in `.env` if you want the auth flow to
   recognise you immediately after migration.

3. **Apply alembic 0003** — drops the legacy `contractions` / `updates`
   tables once you've verified the migrated data:

   ```bash
   docker compose exec backend alembic upgrade head
   ```

The script refuses to run if any `families` row already exists, so it's
safe to leave 0003 unapplied while you confirm everything looks right.

## Auth flow (dev)

```bash
# 1. Request a challenge (the backend log prints the magic link + code)
curl -X POST http://localhost:8000/auth/request \
  -H 'Content-Type: application/json' \
  -d '{"identifier":"alex@example.com"}'

# 2. Read the magic link / code from the backend logs:
docker compose logs backend | tail -20

# 3. Verify with either the token from the link...
curl -X POST http://localhost:8000/auth/verify \
  -H 'Content-Type: application/json' \
  -d '{"token":"<challenge_id>.<secret>"}'

# ...or with the OTP code:
curl -X POST http://localhost:8000/auth/verify \
  -H 'Content-Type: application/json' \
  -d '{"identifier":"alex@example.com","code":"123456"}'

# 4. Use the returned access_token for subsequent calls
curl http://localhost:8000/me -H 'Authorization: Bearer <access_token>'
```

## API surface

Birth-scoped routes (under `/birth/{birth_id}`) require a `Bearer` JWT and a
family membership. The `/b/{slug}` routes are the same page addressed by its
slug and need the same membership — "public" there is a URL shape, not an
access level. The only genuinely unauthenticated birth surface is
`GET /invite/{token}`, where the token itself is the credential.

### Auth + identity

- `POST /auth/request` — request a magic link + OTP
- `POST /auth/verify` — exchange `{token}` or `{identifier, code}` for a JWT
- `GET /me` — current user, memberships, and family→births tree

### Authenticated birth routes

- `GET /birth/{birth_id}` — birth metadata
- `GET /birth/{birth_id}/timeline?after_sequence_id=N&limit=500` — timeline
  events filtered by the requester's role (parents see everything; viewers
  see public + group_targeted)
- `POST /birth/{birth_id}/event` — typed creator for `text_note` and `milestone`; accepts `audience_scope`
- `POST /birth/{birth_id}/contraction/start` — append a contraction event; accepts `audience_scope`
- `POST /birth/{birth_id}/contraction/{event_id}/stop` — close a contraction
- `POST /birth/{birth_id}/media` — multipart upload (photo / video / voice memo) with `audience_scope` field
- `PATCH /birth/{birth_id}/event/{event_id}` — edit caption / body / title
- `DELETE /birth/{birth_id}/event/{event_id}` — soft-delete an event
- `POST /birth/{birth_id}/event/{event_id}/toggle-ignore` — flip the
  `ignore_interval_before` flag on a contraction
- `GET /birth/{birth_id}/stream?token=<jwt>` — server-sent events filtered
  by role; heartbeat every 15s; supports `Last-Event-ID` for resume

### Reactions + comments

- `POST /birth/{birth_id}/event/{event_id}/reactions` — body `{kind: "love"|"wow"|"pray"}`. Idempotent: re-POSTing the same kind is a no-op.
- `DELETE /birth/{birth_id}/event/{event_id}/reactions/{kind}` — remove your own reaction of that kind. Idempotent.
- `GET /birth/{birth_id}/event/{event_id}/comments` — list comments for an event.
- `POST /birth/{birth_id}/event/{event_id}/comments` — `{body}`. Free for any authenticated viewer.
- `PATCH /birth/{birth_id}/event/{event_id}/comments/{comment_id}` — author-only edit.
- `DELETE /birth/{birth_id}/event/{event_id}/comments/{comment_id}` — author or parent.

The same routes are mirrored under `/b/{slug}/event/{event_id}/...`. They require family membership like everything else on the page — a QR-code scanner becomes a member by redeeming the invite the card carries, which is what lets them react and comment. Non-members get 404, signed in or not.

`GET /birth/{birth_id}/timeline` and `GET /b/{slug}/timeline` include per-event `reactions: { kind: { count, mine } }` and `comment_count` inline — two extra bulk queries, no N+1.

SSE adds these event kinds: `reaction_added`, `reaction_removed`, `comment_added`, `comment_updated`, `comment_deleted`.

### Invitations (parents)

- `POST /birth/{birth_id}/invitations` — create a shareable invite link
- `GET /birth/{birth_id}/invitations` — list invites for a birth
- `DELETE /birth/{birth_id}/invitations/{invitation_id}` — revoke

### Invitation redemption (public / authed)

- `GET /invite/{token}` — public lookup of invite context (family + birth name)
- `POST /invite/{token}/redeem` — authed-user path, attaches caller as family_viewer
- New-user path: include `invite_token` in the body of `POST /auth/verify` and
  the user is created + attached atomically with sign-in

### Slug-addressed birth routes

Members only — a non-member gets the same 404 as an unused slug, whether or
not they have a session. Auth is *optional* on these rather than required so
that a caller without one falls through to that 404 instead of a 401, which
would advertise that something is here worth signing in for.

- `GET /b/{slug}` — birth metadata
- `GET /b/{slug}/timeline?after_sequence_id=N&limit=500` — timeline, filtered
  to the audience scopes the requester's role grants.
- `GET /b/{slug}/stream` — same as `/timeline` but SSE. Sending `?token=<jwt>`
  widens visibility for signed-in viewers.
- `GET /media/{media_id}` — gated by audience scope, then 307 redirect to a
  presigned S3 URL (MinIO in dev, AWS in prod). Legacy `local:` keys still
  stream from disk until `migrate_local_to_s3.py` has been run.

## Audience scopes

A birth page is private. Every `/b/{slug}` surface — the birth, the
timeline, the stream, reactions and comments — requires membership in the
family, and everyone else gets the same 404 as a slug nobody has taken.
Being signed in is not a relationship to a page; the way in is an invite
link, which is also where the preview of a birth lives (`/invite/{token}`).

Within the page, posts carry one of two audience scopes:

| Scope            | Non-member | family_viewer | owner / co_parent |
|------------------|------------|---------------|-------------------|
| `group_targeted` | 404        | yes           | yes               |
| `parents_only`   | 404        |               | yes               |

`group_targeted` is the "Family" tier and the default — visible to anyone
who's redeemed an invitation. Sub-grouping (close family vs extended
family) is a future PR; today every invited viewer sees every
`group_targeted` post.

A third scope, `public`, is **retired** (migration `0026`). It meant
"visible to any signed-in person holding the link, invited or not", and
being the default it collected every post anyone ever made. Existing rows
were backfilled to `group_targeted`; the enum value survives so old rows
parse, and `family_viewer` is still granted it so nothing the backfill
missed disappears from a family's own timeline.

## Frontend routes

- `/` — redirects to the default birth's public page (`VITE_DEFAULT_BIRTH_SLUG`,
  defaults to `lily-wren`)
- `/login?next=/path` — email OTP form + "Continue with Google" (identity is email; sessions ride an httpOnly cookie). The `next` param lets guarded actions come back to where the user was after sign-in.
- `/invite/:token` — viewer invitation redeem page (email code or Google, then the birth-alerts phone opt-in, attaches as family_viewer)
- `/b/:slug` — THE birth page, for every role that can see it: invited viewers get the audience-scoped timeline with reactions + comments, parents additionally the inline tooling (contraction button, post composer, Baby Born, stats tab) rendered by role. Everyone else — signed in or not — gets a plain "page not found"; the preview of a birth lives on the invite page.
- `/b/:slug/manage` — legacy URL; client-redirects to `/b/:slug` (the manage page merged into the birth page)

## Production deployment (single instance, bare-metal)

One EC2/droplet runs everything except object storage: nginx (TLS via
certbot) serves the built SPA and proxies `/api/*` to a single-process
uvicorn (systemd); Postgres is installed on the box via apt (deliberately no
RDS, no containers in prod); media and gift artwork live in real S3 through
the instance's IAM role; a nightly `pg_dump` ships to S3.

```
deploy/
  playbook.yml          # full provision + deploy
  deploy-code.yml       # code-only update (rsync, uv sync, migrate, build, restart)
  group_vars/all.yml    # domain, ports, bucket — edit before first run
  group_vars/secrets.yml.example   # copy to secrets.yml (gitignored) and fill in
```

First deploy:

1. Provision AWS: t3.small (Ubuntu 24.04, 30GB), Elastic IP, security group
   22/80/443, an IAM instance role with access to the S3 bucket, and the
   bucket itself (private). Point the domain's A record at the Elastic IP.
2. Edit `deploy/inventory.ini` (host/IP/key) and `group_vars/all.yml`
   (domain, bucket, region); `cp group_vars/secrets.yml.example
   group_vars/secrets.yml` and fill it in.
3. `cd deploy && ansible-playbook playbook.yml`
4. Post-deploy: create the Stripe webhook endpoint pointing at
   `https://<domain>/api/webhooks/stripe` and put its `whsec_` in secrets;
   verify the domain in Resend and set `resend_from`.

Subsequent deploys: `cd deploy && ansible-playbook deploy-code.yml`.

The backend intentionally runs ONE uvicorn worker: the SSE broker
(`backend/events.py`) is in-process, and the Stripe webhook's live
broadcasts assume they land on the same process as the subscribers. Scale-out
requires moving the broker to Redis/NATS first.
