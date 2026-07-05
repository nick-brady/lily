# Lily — Product Spec & Data Model

> Context document for development. Drop into Cursor/LLM context to bootstrap implementation work.

---

## What it is

Lily is a live, shared birth experience that becomes a permanent keepsake. Families track contractions, post photos/videos/voice memos, and narrate the day as it unfolds — while loved ones watch in real time from anywhere. After the birth, the timeline lives on as a permanent record of the day their child arrived, and family members can purchase personalized gifts (mugs, framed prints, photo books) generated from the actual timeline data.

The contraction tracker is the spine, not the product. The product is the shared family experience and the artifact it produces.

## What it is NOT

Lily is not a baby tracking app. It is not a contraction timer with sharing bolted on. It is not a generic pregnancy or postpartum tool. The product surface is *the birth and its keepsake* — full stop.

A small companion utility (**First Days**) ships alongside the birth product to help parents track diapers, feeds, and vitals during the first 30 days. **First Days is a separate, private tool — it does not appear on the birth page and is not visible to family viewers.** It exists as a gift to the parents, not as part of the public birth story.

This separation is intentional and must be preserved. The birth page is the keepsake. First Days is a utility. They share a login and a family, but they're different products living side by side.

---

## The two surfaces

### Surface 1: The Birth Page (the product)

The public, shareable, family-facing page. The thing that becomes the keepsake. The thing that gets framed and turned into mugs. The thing the gift mechanic and the partnership pitch are built around.

**Free for everyone:**
- Contraction tracking with intelligent gap detection
- Live timeline with text updates and milestones
- **Unlimited media** — photos, videos, and voice memos posted by parents
- **Unlimited family viewers** — anyone with a link can watch
- Reactions on timeline events (authenticated via phone/email, no payment required)

**$12 family unlock (binary, one-time per birth):**
Anyone in the family can pay once. Unlocks for *everyone* watching, for that birth, forever:
- **Comments** from authenticated family members
- **Audience groups** — parents can target individual posts to specific groups (Immediate Family, Extended Family, Friends, etc.)

**$3/year storage tail:**
- Free first year. Decision happens at the one-year mark, prompted by a gentle "memories" message to the parents
- Keeps the page live forever after year one
- Export option always available — families can download everything and skip the renewal without losing data
- Near-zero churn expected once they decide to renew (nobody cancels access to the day their child was born)

**Storage as a gift (the long-tail revenue unlock):**
Family members can pre-pay storage on the parents' behalf, locking in permanence as a *gift* rather than a renewal decision. This solves two problems at once: it removes the one-year-out renewal risk, and it creates a new and emotionally distinct gift tier alongside the physical merch.

- **5 years for $15** — "I've got Lily's page covered through her fifth birthday"
- **Lifetime for $59** — "I'll handle this forever. You don't need to think about it."
- Both are one-time payments. Lifetime is the headline option — most grandparents will choose it because it's a single, clean act of permanence rather than something to repeat.
- Available alongside physical gifts in the Day Two prompt and the on-page gift catalog
- Optional personalized note from the giver, surfaced to the parents when they next visit the page or receive their year-one message
- This is *also* how lifetime storage exists as a purchasable option in v1 — only as a gift mechanic, not as a primary purchase path. The parents themselves still get the $3/year renewal flow because that's the right price-anchored decision at the year-one mark.

**Personalized gifts ($25–80):**
- Auto-generated from family's actual timeline data
- Examples: contraction-pattern mug with photos, framed timeline print, photo book of the first 24 hours, ornament with birth time/weight
- Fulfilled by Shutterfly / Printful / Gelato — zero inventory, no shipping work
- **Available to all families** (paying or not) — their timeline data is the seed for the merch flywheel
- Bought by family viewers as gifts to the new parents
- **"And one for me" mechanic:** at checkout, gift buyers can opt to also order a copy shipped to themselves. Three clear options on each product: *Send to the family · Get one for myself · Both*. Grandma sending the contraction mug to Sarah almost certainly wants one for her own desk too — make it a single transaction with two shipping addresses. Significant AOV uplift, near-zero added engineering cost since fulfillment partners already handle multi-address orders.
- **The Day Two prompt:** ~36-48 hours after the "Baby Born!" milestone, every viewer receives one (and only one) prompt designed to feel like a memories update, not a sales pitch. Subject framing: *"[Sarah]'s first day with [Lily]"*. Content: photos from the first 24 hours, voice memos, comments other family members left. The gift catalog sits at the bottom of the message as the natural close — *"Send Sarah and Marco something made from Lily's day"* — with previews for both physical gifts and the storage-as-a-gift options. Single touchpoint, no follow-up nags. If they engage, great. If they don't, we leave them alone.
- **Channel routing for the Day Two prompt:** prefer email if the viewer has one on file; fall back to SMS if email is null. Most family viewers will have signed up via SMS code rather than email, so SMS will likely be the dominant channel. SMS version is dramatically shorter — a short message + a single beautiful link to a memories landing page that contains everything the email would have shown. The landing page does the heavy lifting; the SMS just opens the door.
- Coordinated like a wedding registry (1-of-1 claimed mechanics) so the *gift to the family* doesn't duplicate — but "one for me" copies don't count toward the registry claim (multiple grandparents can each get their own mug). Storage gifts are also 1-of-1 — once Lily's page has lifetime storage, the storage gift disappears from the catalog.
- Parents can curate/veto specific renderings before viewers see them

**Baby shower QR cards (pre-birth):**
Cards or downloadable digital invites the parents share at their baby shower with a QR code linking to their family page. Shower guests scan, sign up as viewers via SMS or email, and are subscribed *before* labor begins.

- **Free digital invite template** — downloadable, viral-friendly, parents can print at home or send via text/email
- **Printed shower cards** — $25-40 for a stack of 30, fulfilled by Printful/Gelato
- Strategic value: pre-builds the viewing audience before labor. Sarah isn't scrambling to invite people in her third trimester — her audience is already there. By the time contractions begin, the family is subscribed and waiting.
- Secondary value: the cards become miniature marketing pieces. Shower host shares them, friends scan them, the product spreads through a high-trust real-world channel before launch buzz ever fades.

**Birth announcement (post-birth, the parents' moment):**
~Week 2-3 post-birth, when Sarah is starting to surface from the newborn fog, the product offers her something *for her*. Auto-generated from her timeline data: the best photo, the name, weight, time, length — laid out as a beautiful announcement she can share or mail.

- **Free digital announcement** — included with the unlocked tier. Shareable to Instagram, sent to anyone via link, posted anywhere. Every share is product marketing.
- **Printed announcement cards** — $35-65 for a stack with envelopes. Mailed to extended family who weren't on the page.
- **Killer feature: the printed cards have a QR code on the back linking back to the full birth page.** Aunt Linda in Ohio gets a card in the mail, scans the QR, watches the full birth experience, and becomes a viewer/buyer retroactively. The announcement product *expands the social graph of the page after the fact*.
- Same fulfillment infrastructure as the rest of the gift catalog. Same data model. Just additional `product_kind` values: `shower_invite_cards`, `birth_announcement_cards`, `birth_announcement_digital`.

### Surface 2: First Days (the companion utility)

A separate, private tool for the parents only. Not visible to family viewers. Does not appear on the birth page. Lives at a different route and has a different visual identity (utility, not keepsake).

Offered to parents as a gentle, optional thing once the baby is born: *"If you'd rather not use the hospital's tracking sheet, we've got you covered. Tap to track diapers, feeds, and bilirubin from your phone."*

**Free for 30 days post-birth:**
- Diapers (wet, dirty, both)
- Feeds (breast L/R/bottle/formula, duration, time)
- Vitals (temperature, bilirubin, weight)
- Sleep (start/stop, where)
- Pediatrician handoff: one-tap summary view for sharing with the doctor

After 30 days the tool becomes read-only unless the family subscribes to **First Year** (v2 — see Future Ideas). First Year is not part of v1.

**Critical design principle:** First Days data NEVER appears on the birth page. They are different products that share an account. The birth page is the artifact; First Days is a utility. Conflating them would dilute the keepsake.

---

## Key product decisions

- **Two surfaces, one account.** The birth page and First Days are deliberately separate products that share a family and login. The birth page is the keepsake; First Days is a utility. This separation must be preserved across the data model, the UX, and the messaging.
- **v1 is the birth keepsake.** First Days ships in v1 as a companion, but it's a supporting actor. The product *is* the birth experience and its artifact. Don't let First Days, First Year, milestone tracking, or anything else dilute that.
- **Seats model dropped.** Unlimited viewers. Unlock is binary per birth (paid / not paid). Removes friction from the viral mechanic and grows gift revenue significantly.
- **Photos and videos are free, unlimited.** The unlock pays for the *interactive layer* (comments, audience groups), not for media access. Charging for media at the emotional peak felt extractive; charging for participation feels generous.
- **Parents see everything regardless of unlock status.** Comments from any authenticated user are visible to parents, even if the unlock hasn't been purchased yet.
- **Reactions free, comments paid.** Reactions keep the page feeling alive for everyone; comments are the participation gate.
- **Identity tied to phone or email.** Used as persistent identity for reactions and comments.
- **"Family" is the root entity, not "birth."** Supports multiple children, sibling births, multi-year engagement without rearchitecting.
- **Soft delete everywhere.** Data is the product value. Reactivation years later is a real revenue stream.
- **Moderation matters:** parents can revoke individual viewers, mute/delete individual comments, or lock the page to invited-only at any time.
- **The birth page is sacred.** No engagement nags, no "log a feed!" prompts, no notifications that pollute the keepsake. Once the birth is done, the page steps back and is.



---

## Architecture

- **Frontend:** PWA for v1 (already partially built — see arrivalstory.com). Native iOS planned for v1.5.
- **Backend:** FastAPI + PostgreSQL + S3 + Cloudflare.
- **Live updates: SSE, not WebSockets.**
  - Messages are *notifications*, not data payloads. Client receives "event X changed for birth Y", then fetches via normal HTTP API.
  - Replay-from-cursor via `Last-Event-ID` header for connection resilience.
  - Heartbeats every 15–30s to keep connections alive through Cloudflare/mobile carriers.
  - Cloudflare config: `Cache-Control: no-cache, no-transform` on SSE endpoints.
- **Storage lifecycle:** S3 standard for first 90 days post-birth (hot path), then transition to S3 Infrequent Access. Video transcoded on upload (200MB iPhone original → ~8MB streaming version).
- **Post-birth viewing:** Pre-render static pages, serve from CloudFront. Most viewing is async and doesn't need live connections.
- **Payments:** Stripe (one-time for unlock, subscriptions for storage tail and First Year).
- **Fulfillment:** Shutterfly / Printful / Gelato APIs.
- **Auth:** Magic link via email or SMS code. No passwords. Identity is phone OR email.

---

## Data model

PostgreSQL. All tables have `id`, `created_at`, `updated_at` unless noted. Use `deleted_at` for soft deletes.

### Core entities

```sql
families
  id
  primary_owner_user_id           -- the user who created the family
  display_name                    -- "The Brady Family"
  created_at, updated_at

users
  id
  email                           -- nullable; users may auth via phone only
  phone                           -- nullable; users may auth via email only
  display_name
  avatar_url
  created_at, updated_at
  -- a user may belong to many families across different roles

family_memberships
  id
  family_id
  user_id
  role                            -- 'owner' | 'co_parent' | 'family_viewer'
  joined_at
  -- owners and co_parents have full edit access; family_viewers have read + comment/react (if unlocked)

births
  id
  family_id
  child_name
  child_dob                       -- nullable until born
  status                          -- 'preparing' | 'in_labor' | 'born' | 'archived'
  birth_started_at                -- first contraction
  birth_completed_at              -- when 'Baby Born!' milestone logged
  storage_tier                    -- 'active' | 'cold' | 'archived'
  is_unlocked                     -- boolean: has anyone purchased the family unlock?
  unlocked_at                     -- when the unlock was purchased
  unlocked_by_user_id             -- who paid (for receipts, attribution)
  is_locked_to_invited            -- moderation flag: only invited viewers can see
```

### Birth timeline (Surface 1 — the public birth page)

These events appear on the public birth page. They are the keepsake content.

```sql
timeline_events
  id
  birth_id
  event_type                      -- 'contraction' | 'milestone' | 'text_note' | 'photo' | 'video' | 'voice_memo'
  sequence_id                     -- monotonically increasing per birth, used for SSE replay
  occurred_at                     -- when the event happened (parents can backfill)
  posted_at                       -- when added to the timeline
  posted_by_user_id
  payload                         -- JSONB, type-specific
  audience_scope                  -- 'public' | 'group_targeted' | 'parents_only'
  deleted_at

  -- payload examples by event_type:
  --   contraction:  { duration_seconds: 45, intensity: null, gap_before_seconds: 240 }
  --   milestone:    { kind: 'baby_born' | 'water_broke' | 'first_feed' | etc., title, body }
  --   photo:        { media_id, caption }
  --   voice_memo:   { media_id, duration_seconds, transcript_optional }
  --   text_note:    { body }

  -- NOTE: diaper, feed, and vital events are NOT in this table.
  -- They live in first_days_events (Surface 2) and never appear on the birth page.

media_assets
  id
  family_id                       -- denormalized for storage lifecycle management
  birth_id
  uploaded_by_user_id
  kind                            -- 'photo' | 'video' | 'voice_memo'
  original_s3_key
  hot_s3_key                      -- transcoded/optimized
  cold_s3_key                     -- archived after 90 days
  storage_tier                    -- 'hot' | 'cold'
  width, height, duration_seconds -- nullable based on kind
  bytes
  mime_type
  is_visible_to_viewers           -- false = parents-only, true = part of public/group-targeted timeline
  created_at, archived_at
```

### First Days (Surface 2 — the private companion utility)

These events live in a completely separate table and are never rendered on the birth page. Visible only to family members with `owner` or `co_parent` roles. No SSE broadcast, no audience scoping needed — they're private by default.

```sql
first_days_events
  id
  family_id                       -- belongs to a family, not a specific birth (a family has a baby; First Days follows the baby)
  birth_id                        -- which birth/baby this is tracking
  event_type                      -- 'diaper' | 'feed' | 'vital' | 'sleep' | 'note'
  occurred_at
  logged_at
  logged_by_user_id               -- must be 'owner' or 'co_parent' on the family
  payload                         -- JSONB, type-specific
  deleted_at

  -- payload examples:
  --   diaper:  { type: 'wet' | 'dirty' | 'both', notes }
  --   feed:    { method: 'breast_left' | 'breast_right' | 'bottle' | 'formula', duration_minutes, amount_ml? }
  --   vital:   { metric: 'temp_f' | 'bili_mg_dl' | 'weight_g', value, source: 'home' | 'pediatrician' | 'hospital' }
  --   sleep:   { duration_minutes, location: 'bassinet' | 'parent' | 'crib' | 'other' }
  --   note:    { body }

-- For visualizations (wet-diaper-count-by-day, weight curve, etc.), precompute rollups:
first_days_daily_rollups
  id
  birth_id
  date
  feed_count
  total_feed_minutes
  wet_diaper_count
  dirty_diaper_count
  total_sleep_minutes
  latest_weight_g
  -- regenerated nightly or on-demand from first_days_events
```

### Audience groups (paid feature, available after unlock)

```sql
audience_groups
  id
  birth_id
  name                            -- 'Immediate Family' | 'Extended Family' | 'Friends' | custom
  is_default                      -- true for system-created defaults
  sort_order
  created_at

audience_group_memberships
  id
  audience_group_id
  user_id                         -- a viewer can be in multiple groups
  added_by_user_id
  added_at

timeline_event_audiences
  id
  timeline_event_id
  audience_group_id
  -- Many-to-many: a post can be sent to multiple groups.
  -- If timeline_events.audience_scope = 'public', no rows here (visible to all).
  -- If 'parents_only', no rows here either (enforced in code).
  -- If 'group_targeted', rows here define which groups see it.
```

The schema supports per-post group targeting (Option A). UX can present this as toggles, dropdown chips, etc.

### Unlock, comments, reactions

```sql
unlock_purchases
  id
  birth_id
  purchased_by_user_id
  amount_cents
  currency
  stripe_payment_intent_id
  purchased_at
  -- only one successful purchase per birth (idempotency)

comments
  id
  timeline_event_id               -- comments attach to events
  birth_id                        -- denormalized for query simplicity
  author_user_id                  -- must be authenticated
  body
  created_at, edited_at, deleted_at
  -- gated: only insertable if births.is_unlocked = true

reactions
  id
  timeline_event_id
  author_user_id                  -- must be authenticated
  reaction_type                   -- 'heart' | 'celebrate' | 'love' | etc.
  created_at
  -- NOT gated by unlock — free to all authenticated viewers
  -- unique constraint on (timeline_event_id, author_user_id, reaction_type)

viewer_invitations
  id
  birth_id
  invited_user_id                 -- nullable until claimed
  invited_phone                   -- nullable
  invited_email                   -- nullable
  invitation_token                -- unique, used in invite link
  invited_by_user_id
  status                          -- 'pending' | 'claimed' | 'revoked'
  claimed_at, revoked_at, created_at
```

### Gifts (registry mechanic)

The catalog supports three kinds of gifts: **physical** (mugs, prints, books, announcement cards, shower cards — fulfilled by Shutterfly/Printful/Gelato), **digital** (storage gifts that activate permanence on the family's behalf), and **free_digital** (digital downloadable announcements and shower invites included with the unlocked tier). The schema handles all three uniformly so the registry, ordering, and "and-one-for-me" mechanics work consistently.

```sql
gift_catalog_items
  id
  kind                            -- 'physical' | 'storage_gift' | 'free_digital'
  product_kind                    -- physical: 'mug' | 'framed_print' | 'photo_book' | 'ornament' |
                                  --           'birth_announcement_cards' | 'shower_invite_cards'
                                  -- storage_gift: 'storage_5yr' | 'storage_lifetime'
                                  -- free_digital: 'birth_announcement_digital' | 'shower_invite_digital'
  base_price_cents                -- 0 for free_digital
  fulfillment_partner             -- physical: 'shutterfly' | 'printful' | 'gelato'; null otherwise
  fulfillment_sku                 -- null for non-physical
  template_metadata               -- JSONB: design template config (physical and free_digital)
  storage_years_granted           -- null except for storage_gift; 5 or 999 (lifetime)
  surfaces_in                     -- JSONB array: which moments this item surfaces in
                                  -- e.g. ['day_two_prompt', 'on_page_catalog', 'parent_dashboard_post_birth']
                                  -- shower invite cards surface in 'parent_dashboard_pre_birth'
                                  -- birth announcement surfaces in 'parent_dashboard_post_birth'

gift_renderings
  id
  birth_id
  gift_catalog_item_id
  rendered_preview_url            -- physical: pre-generated preview with family's actual data
                                  -- storage_gift: a beautiful "preview" of the gift itself (e.g. a card design)
  rendering_metadata              -- JSONB: which photos/data were used (physical only)
  is_visible_to_viewers           -- parents can hide specific renderings
  is_claimed                      -- registry coordination
  claimed_by_order_id             -- nullable
  created_at

gift_orders
  id
  gift_rendering_id
  purchased_by_user_id            -- the family viewer who bought it
  total_amount_cents
  stripe_payment_intent_id
  gift_message                    -- optional personal note from giver, shown to parents
  purchased_at

gift_shipments
  id
  gift_order_id
  kind                            -- 'physical' | 'storage_gift'
  recipient_kind                  -- physical: 'family' | 'self'; storage_gift: always 'family'
  recipient_address               -- physical only; null for storage_gift
  amount_cents                    -- per-shipment amount (order total = sum of shipments)
  -- physical fulfillment fields:
  fulfillment_order_id            -- from Shutterfly/Printful/Gelato; null for storage_gift
  fulfillment_status              -- 'pending' | 'shipped' | 'delivered'; null for storage_gift
  counts_toward_registry_claim    -- true for family-bound physical; true for storage_gift
  shipped_at, delivered_at        -- physical only

  -- When a storage_gift shipment is inserted, also:
  --   1. Create or update a subscription record for the family with tier='storage_gifted'
  --      and an expires_at = now() + storage_years_granted years (or null for lifetime)
  --   2. Notify the parents via in-app message (or email/SMS if they have notifications enabled)
  --      with the gift_message attached
  --   3. Mark the storage_gift rendering as claimed so it disappears from the catalog
```

**Subscription model extension for storage gifts:**

The `subscriptions` table now handles three storage states:

```sql
subscriptions
  id
  family_id                       -- family-level, not birth-level
  tier                            -- 'storage' (paid by parents) | 'storage_gifted' (paid by family member as gift)
  status                          -- 'active' | 'paused' | 'cancelled' | 'past_due'
  current_period_start            -- when this storage period started
  current_period_end              -- when it expires (null = lifetime)
  stripe_subscription_id          -- null for storage_gifted (one-time payment, not a recurring sub)
  amount_cents, currency, interval_unit  -- interval_unit null for one-time/lifetime
  gifted_by_user_id               -- only set when tier = 'storage_gifted'
  created_at, cancelled_at
```

A family's effective storage state at any time = whichever subscription is active and has the latest `current_period_end` (or null for lifetime). If a parent later wants to also pay $3/year on top of a 5-year gift, that's fine — both records exist; the latest expiration wins.

---

## Design notes & gotchas

**The two surfaces never blend.** Birth page renders from `timeline_events`. First Days renders from `first_days_events`. Different routes, different views, different visual treatments. There is no scenario in v1 where a diaper count shows up on the birth page or a contraction shows up in First Days.

**Invite flow is link-based, not contact-based, in v1.** Browser contact APIs are unreliable (iOS Safari doesn't support the Contact Picker API; Android requires one-by-one selection). v1 should generate shareable invite links that parents share via the OS native share sheet — iMessage, WhatsApp, email, group texts. This is the universal pattern (Calendly, Google Docs, WhatsApp group invites work this way) and it works everywhere. Manual entry of phone/email is a fallback. Real contact-list integration comes with the native app in v1.5.

**Notifications are sacred. Most product communication is not.** Push notifications and SMS are reserved for real-time birth events (labor started, baby born, major milestones). They cannot be polluted with marketing, gift prompts, or engagement nags — if family viewers stop trusting our notifications, the entire live-birth experience falls apart. The product has exactly *two* automated commercial-adjacent touchpoints across the entire lifecycle: the Day Two memories prompt (sent to all viewers ~48 hours after birth, framed as a first-day recap with gifts as the natural close) and the Year One renewal prompt (sent only to parents ~1 week before the baby's first birthday, framed as a memory with the storage decision as the close). Both are framed as memory, not marketing. Single touchpoint each, with one gentle follow-up only on the Year One. Everything else commercial happens passively on the page itself.

**`sequence_id` is critical for SSE.** Use it as the value of `Last-Event-ID` headers. Per-birth, not global. Use a Postgres sequence per birth, or a global sequence with an indexed ordering query.

**`audience_scope` on `timeline_events` is intentionally denormalized.** Avoids forced joins through `timeline_event_audiences` for the common case (public posts during active birth). The cheap path stays cheap.

**`media_assets` separate from `timeline_events`.** A photo may be referenced from multiple places (timeline post + gift book + future milestone post). Storage lifecycle is media-specific.

**JSONB payloads on events.** Trades referential rigor for schema flexibility. New event types are code changes, not migrations. Validate strictly at the API layer (Pydantic discriminated unions).

**Soft delete is the default.** Never hard-delete content unless the user explicitly requests it. Years-later reactivation is a real revenue stream.

**Authentication via phone OR email.** Magic links / SMS codes only. No passwords. The user record stores whichever identifier they used; both can be added later.

**Unlock is binary, idempotent.** Only one successful unlock per birth. UI must handle the race condition of two family members trying to pay simultaneously (refund the second, show a friendly "already unlocked" message).

**Track invitation source for every viewer.** When a viewer signs up via shower QR card, post-birth announcement QR card, direct SMS invite from a parent, or the universal share link, capture which path they took. The `viewer_invitations` table should include an `invitation_source` field with values like `direct_sms`, `direct_email`, `shower_qr`, `announcement_qr`, `share_link`. This is the only way to measure how much of the social graph expansion is driven by the QR mechanics — and it's critical data for deciding whether to lean further into physical-card products.

**Moderation primitives:**
- Parents can revoke a `viewer_invitation` (soft-delete it)
- Parents can soft-delete any comment
- Parents can toggle `births.is_locked_to_invited` to switch from "open link" to "invited-only" at any time
- Build these from v1 since unlimited viewers means abuse vectors are real

**Storage cost discipline:**
- Lifecycle policy: hot → cold at 90 days post-birth
- Transcode video on upload, keep original cold-tier only
- Never delete; the cold-storage cost is rounding error vs. goodwill loss

**Liability framing for clinical features:**
- First Days tracker records observations, never interprets
- No clinical-looking default prompts ("ask AI about labor progression" is a no-go)
- Aggressive disclaimers and friction at point of use
- Any AI integration must be framed as data portability, never advice — and gated behind a digital health lawyer review before shipping

---

## Open product questions (TBD)

- Exact UX for audience group selection on post creation (chips? dropdown? smart defaults?)
- Whether to allow non-authenticated reactions or require auth for all reactions
- How the unlock prompt surfaces in the family viewer experience — when do non-unlocked viewers see "unlock to leave a comment"? Probably contextually, on tap of a comment field.
- Whether to ship comment quoting/threading or keep flat for v1
- Whether the contraction-pattern mug, framed timeline, and photo book are sufficient for the v1 gift catalog or whether to launch with more variety

---

## Out of scope for v1

- Native iOS app (planned v1.5 — unlocks Apple Watch contraction tracking, Live Activities, lock screen integration, and native contacts access for the invite flow)
- Apple Watch integration (v1.5+)
- MCP / AI integration (v2, after legal review)
- Multi-language support
- White-label / clinic-deployment versions
- Real-time video streaming (separate problem; not what the product is about)

---

## Future ideas & revenue streams (post-v1 roadmap)

### Year-one renewal flow (v1)

**Note:** This was originally scoped as v1.5 but moved into v1 since the $3/year storage tail depends on a graceful renewal mechanic to actually convert. Without this flow, the storage tail is theoretical revenue.

When a family's free storage period approaches expiration (one year post-birth), gracefully prompt them to keep the page live or export their data — without nagging.

**The mechanic:**

- ~1 week before the baby's first birthday: send a "Memories" message to the parents only — email if available, SMS link if not.
- The message itself is short and framed as memory, not renewal. Subject/preview: *"One year ago this week."* The landing page does the heavy lifting.
- The landing page is a curated recap: photos, voice memos, family comments from labor day. Beautiful, emotional, not transactional.
- At the bottom, two quiet options: *Keep [Baby name]'s page live forever — $3/year* and *Download everything as a zip*.
- If no action, one gentle follow-up on the actual birthday: *"Happy first birthday, [Baby name] 🤍"* with the same options.
- After that, silence. The page moves to archived storage (still preserved, just not publicly accessible). Family can reactivate any time for $3/year.

**For family viewers:** No automated message at the one-year mark. They're not the decision-makers; the parents are. If the parents post a birthday update after renewing, viewers get the standard "Sarah posted to Lily's page" notification through normal product behavior. Organic, not orchestrated.

**Why this matters:**

- A "your card will be charged" reminder primes families to cancel. A "here are your memories" message is celebratory and gives them agency. Verb shifts from "stopping" to "preserving."
- The export option removes the "you're holding our memories hostage" feeling that kills emotional products. Most families who can export *will also pay* because the export is a clunky zip and the live page is beautiful. Giving them the option costs nothing and earns significant goodwill.
- High emotional moment is also a natural opportunity to surface a year-one photo book as a one-time upsell, though that's optional and shouldn't crowd the renewal decision.

### Multi-year keepsake experience (v2+)

The long-term vision: families come back to the page on birthdays, anniversaries, and milestone moments throughout the child's life. Storage tail funds it; product is designed for *moments of return*, not daily engagement.

**Possible features:**
- Future-sibling onboarding under the same family — second child gets their own birth page but shares the family's audience and storage
- "Memories" emails on birthdays with year-over-year highlights
- One-tap reactivation if a family has let storage lapse
- Anniversary photo books generated automatically

**Important:** Don't build engagement-driving features for post-year-one. No daily prompts, no nagging notifications, no "tap to view memories" pings. The dignity of the keepsake comes from it *not* demanding attention. Build the renewal flow and the memories email. Leave families alone otherwise.

This entire surface is **out of scope for v1**. v1 is a birth app, not a child-lifecycle platform. The keepsake nature emerges naturally from the storage tail; we don't have to build features for it yet.

### Page themes / aesthetic customization (v1.5)

A small, curated set of designed themes (4–6 presets) that families can apply to their birth page. Available to all families, free.

**Examples of themes:**
- **Soft & Sage** — calm, intentional, midwifery-coded (default)
- **Warm Cream** — buttery, cozy, golden-hour
- **Deep Garden** — moody florals, jewel tones, more dramatic
- **Quiet Modern** — minimal, off-white, single accent
- **Hand-Drawn** — illustrated, warm script accents, whimsical
- **Twilight** — dark mode, navy and gold, late-night birth energy

**Why themes (curated) and not full customization (font picker / color picker / etc.):**

1. **Keepsake quality depends on the page being beautiful in 20 years.** Letting a sleep-deprived dad pick Comic Sans because it "felt fun in the moment" undermines what the product is. The brand is design-led; the customization shouldn't break that.

2. **Merch catalog must coordinate with page design.** The framed timeline print, the photo book, the contraction mug — these are designed against an implicit visual standard. If the page can look like anything, the merch has to either track every user's customization (massive design+engineering overhead) or ignore it (jarring inconsistency between "my page" and "my book"). Themed presets let the merch render in matching themes naturally.

3. **Support and design surface area.** "The font I want isn't here," "colors look wrong on my phone," "I broke something" — pure support cost. As a side business, this matters.

4. **Customization works better in the free tier than as an unlock perk.** The unlock value prop is *interactive layer* (comments, audience groups). Adding aesthetic customization to the unlock muddies the pitch. Themes in the free tier make the *free product* feel personalized — strengthens the "look how beautiful, and it's free" pitch to the midwife/nurse and their audience.

**Implementation notes:**
- Each theme is a coordinated package: color palette, font pairing (one display serif + one body sans), accent treatments, how milestones/contractions render
- Themes are designed *against the merch catalog* so each one produces matching physical products
- Ship v1 with one beautifully designed default theme. Add the theme picker in v1.5 once real users signal what they want. Data model: just a `theme_id` on `births` referencing a theme catalog table.

### Pre-birth invitation cards (v1.5)

Physical cards mailed to family before the due date, with a QR code linking to the baby's pre-birth page. Recipients scan, subscribe via phone/email, and get notified the moment labor begins.

**Why it matters:**
- Pre-builds the viewing audience before labor — no frantic group texts at 3am
- High-margin, low-cost physical product (~$25–40 for a pack of 30–50, fulfilled by Moo/Vistaprint/Printful)
- Creates a tangible keepsake artifact families also want to keep
- Generates earlier emotional investment in the page → higher unlock and gift conversion at the actual birth
- Natural integration with existing gift catalog infrastructure

**Implementation notes:**
- Pre-birth page is a simplified version of the live timeline (announcement, due date, optional belly photos, optional registry links)
- QR code encodes a family-specific invitation token that auto-creates a viewer subscription on scan
- Could ship as standalone product or as part of a "pregnancy package" with shower-related products

### Baby shower integration (v2)

Expand the product backward from "day of birth" to "the entire arrival journey."

**Possible features:**
- Shower invitations with QR codes (same mechanic as birth-announcement cards)
- Digital guestbook tied to baby's page — shower attendees leave messages, photos, well-wishes
- Pre-birth photo timeline (shower photos, sonograms, gender reveal, belly photos by week)
- Registry integration (Babylist, Amazon, Target) linked from the page
- "Shower aggregator" — collect photos from multiple attendees into one shared album

**Strategic value:**
- Extends the engagement window from "the day" to "the whole pregnancy and arrival"
- Adds another physical product revenue stream (shower invitations)
- Captures content from a much wider social graph (shower attendees, not just birth viewers)
- Positions the product as *the canonical record of the entire arrival*, not just one day

### First Year extension expansion (v2)

Beyond simple milestone tracking, the First Year subscription could include:
- Monthly photo prompts ("first month photo" reminders)
- Auto-generated month-by-month photo books at the end of year one
- Sleep / feeding / development pattern visualizations
- Pediatrician appointment tracking with photo + notes
- Vaccination records
- Smart "memory replay" — "one year ago today, Lily had her first feed" notifications

### Sibling and family-tree expansion (v3+)

The family-as-root data model already supports this — second and third children join the same family entity automatically. Future features could include:
- Cross-child comparison ("Lily at 3 months vs. James at 3 months")
- Sibling milestone tracking
- Multi-generational family tree integration
- "Year in review" family annual reports

### Other physical product ideas

- **Birth announcement cards** post-birth (vs. pre-birth invitations)
- **Holiday card integration** — auto-generate annual holiday cards using the year's photos
- **Custom birth posters** — typographic posters with name, date, time, weight, length
- **Birth stat ornaments** — annual ornaments with that year's photos and milestones
- **Family wall art** — large-format prints, canvas wraps, framed multi-photo collages
- **Memorial / loss support** — sensitive, optional feature set for pregnancy loss and infant loss families. Significant product care required; consult with bereavement specialists before designing.

### Clinical / professional integrations (v3+, requires careful legal review)

- Midwife and doula tools for tracking multiple clients
- Pediatrician dashboard for the First Year data
- Birth center / hospital integration for clinical hand-off
- Insurance / FSA-HSA eligibility for certain features

### B2B / partnership opportunities (longer-term)

- Birth centers and midwifery practices offering Lily as a client perk
- Doula network partnerships
- Hospital labor and delivery unit integrations
- Maternal health publication / brand co-marketing (beyond the founding partnership)
