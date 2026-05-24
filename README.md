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

Migrations are **not** run automatically. See the next section.

## Running migrations

```bash
docker compose exec backend alembic upgrade head
```

For the PR 1 cutover (legacy single-tenant → multi-tenant), see
[Migrating from the legacy schema](#migrating-from-the-legacy-schema).

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

## API surface (PR 1)

All birth-scoped routes require a `Bearer` JWT and a family membership.

- `POST /auth/request` — request a magic link + OTP
- `POST /auth/verify` — exchange a token or `{identifier, code}` for a JWT
- `GET /me` — current user + family memberships
- `GET /birth/{birth_id}` — birth metadata
- `GET /birth/{birth_id}/timeline?after_sequence_id=N&limit=500` — timeline events
- `POST /birth/{birth_id}/event` — typed creator for `text_note` and `milestone`
- `POST /birth/{birth_id}/contraction/start` — append a contraction event
- `POST /birth/{birth_id}/contraction/{event_id}/stop` — close a contraction
- `POST /birth/{birth_id}/media` — multipart upload (photo / video / voice memo)

Live updates (SSE) land in PR 2.
