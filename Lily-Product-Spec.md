

> The canonical product document — what Lily is, how it's priced, and the decisions behind it. Engineering details (architecture, data model, implementation gotchas) live in [[Lily-Tech-Notes]].

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

**Free for everyone (everything live is free):**
- Contraction tracking with intelligent gap detection
- Live timeline with text updates and milestones
- **Unlimited media** — photos, videos, and voice memos posted by parents
- **Unlimited family viewers** — an invite link lets anyone join; viewing is auth-gated, so every viewer signs in once with an email and is identifiable (and revocable) from then on
- Reactions on timeline events (from authenticated viewers, no payment required)
- **Comments** from authenticated family members
- **Audience groups** — parents can target individual posts to specific groups (Immediate Family, Extended Family, Friends, etc.)

> **Pricing thesis (revised 2026-07-19):** everything live/digital is free; everything permanent/physical costs money. The $12 family unlock was cut. Gating comments locked the product's best moment — Janet typing "we're praying for you sweetheart" at 2am — behind a paywall during the exact window nobody is thinking about payments, and risked the virality loop to protect a $12 line item. Free participation is not a revenue sacrifice; it's the top of the gift funnel — emotionally invested viewers buy keepsakes, spectators don't. The commercial spine is **three physical-product moments**: pre-birth (invite/shower cards), Day Two (the big one, carrying most of the monetization weight), and year one (storage gifts / memory book).

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
- Storage gifts are 1-of-1 in the registry — once the page has lifetime storage, the storage gift disappears from the catalog.

**Personalized gifts ($25–80):**
- Auto-generated from family's actual timeline data
- Examples: contraction-pattern mug with photos, framed timeline print, photo book of the first 24 hours, ornament with birth time/weight
- Fulfilled by Shutterfly / Printful / Gelato — zero inventory, no shipping work
- **Available to all families** (paying or not) — their timeline data is the seed for the merch flywheel
- Bought by family viewers as gifts to the new parents
- **"And one for me" mechanic:** at checkout, gift buyers can opt to also order a copy shipped to themselves. Three clear options on each product: *Send to the family · Get one for myself · Both*. Grandma sending the contraction mug to Sarah almost certainly wants one for her own desk too — make it a single transaction with two shipping addresses. Significant AOV uplift, near-zero added engineering cost since fulfillment partners already handle multi-address orders.
- **The Day Two prompt:** ~36-48 hours after the "Baby Born!" milestone, every viewer receives one (and only one) prompt designed to feel like a memories update, not a sales pitch. With the unlock cut, Day Two carries essentially all the monetization weight — design principles (refined 2026-07-19):
  - **Show, don't sell.** Auto-generate the artifact *before* they open it: *"[Lily]'s birth story is ready"* with a rendered preview of the actual timeline — her contraction curve, the 3:47am photo, Janet's comment overlaid. They're looking at a finished object, not a product page. The buy moment is one tap on something that already exists.
  - **Send it to the family, not just parents.** Janet is the buyer; parents are the audience. "One for me" is the default-visible option on her version.
  - **Anchor high.** Lead with the photo book or framed timeline (the $50-80 items), not mugs.
  - **Include one free thing** — a shareable digital birth announcement graphic. It's the viral hook, and it makes the message feel like a gift rather than an invoice.
  - Content: photos from the first 24 hours, voice memos, comments family members left. Storage-as-a-gift options preview alongside the physical gifts. Single touchpoint, no follow-up nags. If they engage, great. If they don't, we leave them alone.
  - Day Two can be **manual/concierge for the first ten births** — polish on the gift flow is not the critical path to validation.
- **Channel routing for the Day Two prompt:** email, for every viewer — identity is email-keyed (see Key product decisions), so an email is always on file. SMS never carries the Day Two prompt or any other gift content; texts are reserved for the birth events viewers explicitly opted into. The email is short and opens onto the memories landing page, which does the heavy lifting.
- Coordinated like a wedding registry (1-of-1 claimed mechanics) so the *gift to the family* doesn't duplicate — but "one for me" copies don't count toward the registry claim (multiple grandparents can each get their own mug).
- Parents can curate/veto specific renderings before viewers see them

**Baby shower QR cards (pre-birth):**
Cards or downloadable digital invites the parents share at their baby shower with a QR code linking to their family page. Shower guests scan, sign up as viewers with an email code (or Google), optionally opt into labor texts, and are subscribed *before* labor begins.

- **Free digital invite template** — downloadable, viral-friendly, parents can print at home or send via text/email. The free digital invite is the audience-builder — that's the growth mechanic, don't touch it.
- **Printed shower cards** — $25-40 for a stack of 30, fulfilled by Printful/Gelato
- **The shower host role (added 2026-07-19):** the card *buyer* is usually the shower host — grandma or a friend — not Sarah. You can't market shower cards to Sarah (she's not the buyer) and can't reach the host cold. The bridge: a *"someone planning your shower?"* prompt when Sarah creates the birth page, plus a shareable link she hands the host. The host gets a **real capability**, not just an email capture — manage the shower invite, see RSVPs/viewer signups, order cards — so the invite feels like delegation ("help me with the shower") rather than Sarah forwarding a sales pitch. The card upsell lives inside the host's view.
  - **Sequencing:** host's first touch is the free digital invite working beautifully, *then* "want these printed?" — same show-don't-sell logic as Day Two, rendering their actual invite as the physical card preview.
  - **Optional and skippable** at setup, with a re-prompt around week 28-30 when showers actually get planned. Don't front-load it at page creation when the birth is 5 months out.
  - Side benefit: the host is a Lisa — outer-ring, emotionally involved, and now she has an account. The role itself is a viral vector.
- Strategic value: pre-builds the viewing audience before labor. Sarah isn't scrambling to invite people in her third trimester — her audience is already there. By the time contractions begin, the family is subscribed and waiting. QR on the card enrolls viewers weeks before labor, which directly fattens the Day Two buyer pool.
- Structural value: pre-labor cards generate revenue *before* the birth even happens, de-risking the per-birth economics.
- Secondary value: the cards become miniature marketing pieces. Shower host shares them, friends scan them, the product spreads through a high-trust real-world channel before launch buzz ever fades.

**Birth announcement (post-birth, the parents' moment):**
~Week 2-3 post-birth, when Sarah is starting to surface from the newborn fog, the product offers her something *for her*. Auto-generated from her timeline data: the best photo, the name, weight, time, length — laid out as a beautiful announcement she can share or mail.

- **Free digital announcement** — free for every family. Shareable to Instagram, sent to anyone via link, posted anywhere. Every share is product marketing.
- **Printed announcement cards** — $35-65 for a stack with envelopes. Mailed to extended family who weren't on the page.
- **Killer feature: the printed cards have a QR code on the back linking back to the full birth page.** Aunt Linda in Ohio gets a card in the mail, scans the QR, watches the full birth experience, and becomes a viewer/buyer retroactively. The announcement product *expands the social graph of the page after the fact*.
- Same fulfillment infrastructure as the rest of the gift catalog.

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
- **Seats model dropped.** Unlimited viewers. Removes friction from the viral mechanic and grows gift revenue significantly.
- **The $12 unlock dropped (2026-07-19).** Comments and audience groups are free for everyone. Charge for permanence and physical products, never for participation — the live experience is the emotional peak and the top of the gift funnel. This also makes the model one sentence ("everything live is free, everything you can hold costs money"), easy to explain to a doula and easy for families to trust — no "wait, what's paywalled?" hesitation during a sensitive moment. *(Supersedes the earlier "reactions free, comments paid" decision; the code still gates comments behind Stripe checkout and needs to be un-gated.)*
- **Photos and videos are free, unlimited.** Charging for anything at the emotional peak felt extractive — this instinct eventually consumed the unlock itself.
- **Identity is email. Phone is a notification opt-in. Google is a convenience layer (2026-07-23).** One auth path: email OTP codes + "Continue with Google," both resolving to the same email-keyed identity — OAuth is a login method, not a separate identity. No passwords, no magic links (spam folders and cross-device breakage), no SMS login, no Facebook in v1 (Apple Sign-In arrives with the native app in v1.5; make email sends work through private-relay addresses). Every user therefore has an email, so Day Two and Year One reach 100% of viewers on the legally boring channel — CAN-SPAM wants an unsubscribe link, versus TCPA's $500–$1,500-per-text exposure for marketing SMS. The signup-friction worry was mostly illusory: signup happens months pre-labor at a calm moment, not at 2am. *(Supersedes "identity tied to phone or email" / magic-link-or-SMS-code auth.)*
- **Phone number is collected right after signup as an explicit opt-in** — *"Want a text the moment labor begins?"* Peak-intent moment, converts extremely well, and consent gathered this way is TCPA-clean. Send a confirmation text on opt-in (verifies the number, delivers STOP language). Those texts are scoped to birth events only, forever. No marketing SMS exists in v1, so the consent-checkbox/legal-review question evaporates.
- **Viewing is auth-gated; invite links grant the right to sign up, never a session.** Access via link, identity via email — a forwarded link produces a new identifiable viewer Sarah can see and revoke, not an anonymous one.
  - **v1 requirement — the unauthenticated preview.** A first-time visitor (QR scan on an announcement card, forwarded link) must see a taste of the page *before* the email ask: cover photo, the baby's name, a blurred or truncated timeline. The sign-in prompt lands after the emotional hook, not before it. The auth gate must never be the first thing a QR-scanning great-aunt sees — that's the top of the viral loop, where friction is most expensive.
- **Sessions are sacred infrastructure.** 12+ month lifetime, silently refreshed on every visit, so the one auth event happens months before the birth and never recurs during it. Design the second-device (iPad-at-2am) OTP screen deliberately and test it with someone over 60. Engineering constraints that make the promise real:
  - **Sessions live in server-set httpOnly cookies, not localStorage.** Safari's ITP deletes script-writable storage (localStorage, JS-set cookies) after ~7 days without a visit — a localStorage token silently logs out exactly the casual iPhone viewers this product serves. httpOnly cookies are exempt. *(The current code stores a bearer JWT in localStorage with a hard 30-day TTL and no refresh — both must change; see [[Spec-vs-Code-Questions]].)*
  - **Sliding refresh:** every authenticated visit re-issues the cookie, so an active viewer's session never expires. Hard caps kill the sign-up-at-week-32, deliver-at-week-40 case.
  - **Birth-event texts carry short-lived authenticated deep links.** A text goes to a phone number that was verified and bound to an identity at opt-in, so its link may log that device in directly — tapping "Sarah has started timing contractions" must never land on a login screen. This is session recovery for a known person, not an invite link; the invite-links-never-grant-sessions rule stands.
- **"Family" is the root entity, not "birth."** Supports multiple children, sibling births, multi-year engagement without rearchitecting.
- **Never delete family data.** Data is the product value. Reactivation years later is a real revenue stream.
- **Moderation matters:** parents can revoke individual viewers, mute/delete individual comments, or lock the page to invited-only at any time. Build these from v1 — unlimited viewers means abuse vectors are real.
- **The birth page is sacred.** No engagement nags, no "log a feed!" prompts, no notifications that pollute the keepsake. Once the birth is done, the page steps back and is.

---

## Technical approach (summary)

PWA for v1 (native iOS in v1.5), FastAPI + PostgreSQL + S3 + Cloudflare, live updates via SSE, Stripe for payments, Shutterfly/Printful/Gelato for fulfillment, passwordless auth (email OTP codes + Google OAuth, one email-keyed identity). Start 10DLC registration early — the transactional labor texts need it and carrier approval takes weeks; it's the only piece with a bureaucratic lead time. Full architecture, data model, and implementation gotchas: [[Lily-Tech-Notes]].

---

## Design principles & guardrails

**The two surfaces never blend.** Different routes, different views, different visual treatments. There is no scenario in v1 where a diaper count shows up on the birth page or a contraction shows up in First Days.

**Invite flow is link-based, not contact-based, in v1.** Browser contact APIs are unreliable (iOS Safari doesn't support the Contact Picker API; Android requires one-by-one selection). v1 generates shareable invite links that parents share via the OS native share sheet — iMessage, WhatsApp, email, group texts. This is the universal pattern (Calendly, Google Docs, WhatsApp group invites work this way) and it works everywhere. Manual entry of phone/email is a fallback. Real contact-list integration comes with the native app in v1.5.

**Notifications are sacred. Most product communication is not.** Push notifications and SMS are reserved for real-time birth events (labor started, baby born, major milestones) — and SMS goes only to viewers who explicitly opted in at signup. They cannot be polluted with marketing, gift prompts, or engagement nags — if family viewers stop trusting our notifications, the entire live-birth experience falls apart. Channels are separated by purpose: SMS carries only the sacred real-time moments; email carries everything else — Day Two, Year One, receipts. The product has exactly *two* automated commercial-adjacent touchpoints across the entire lifecycle: the Day Two memories prompt (emailed to all viewers ~48 hours after birth, framed as a first-day recap with gifts as the natural close) and the Year One renewal prompt (emailed only to parents ~1 week before the baby's first birthday, framed as a memory with the storage decision as the close). Both are framed as memory, not marketing. Single touchpoint each, with one gentle follow-up only on the Year One. Everything else commercial happens passively on the page itself.

**Track invitation source for every viewer.** Whether a viewer arrived via shower QR card, announcement QR card, direct invite, or the share link must be captured on signup. It's the only way to measure how much social-graph expansion the QR mechanics drive — critical for deciding whether to lean further into physical-card products, and the core instrumentation for [[../validation/free-tester-plan|free-tester validation]].

**Liability framing for clinical features:**
- First Days tracker records observations, never interprets
- No clinical-looking default prompts ("ask AI about labor progression" is a no-go)
- Aggressive disclaimers and friction at point of use
- Any AI integration must be framed as data portability, never advice — and gated behind a digital health lawyer review before shipping

---

## Open product questions (TBD)

- Exact UX for audience group selection on post creation (chips? dropdown? smart defaults?)
- ~~Whether to allow non-authenticated reactions or require auth for all reactions~~ *Resolved 2026-07-23: viewing itself is auth-gated, so all reactions and comments come from email-identified viewers.*
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

- ~1 week before the baby's first birthday: send a "Memories" email to the parents only (identity is email-keyed, so it's always on file).
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

4. **Themes belong in the free tier.** The live product is entirely free by design; themes make the free product feel personalized and strengthen the "look how beautiful, and it's free" pitch to the midwife/nurse and their audience. Charging for aesthetics would reintroduce a paywall into the live experience, which the model deliberately avoids.

**Implementation notes:**
- Each theme is a coordinated package: color palette, font pairing (one display serif + one body sans), accent treatments, how milestones/contractions render
- Themes are designed *against the merch catalog* so each one produces matching physical products
- Ship v1 with one beautifully designed default theme. Add the theme picker in v1.5 once real users signal what they want.

### Pre-birth invitation cards (v1.5)

Physical cards mailed to family before the due date, with a QR code linking to the baby's pre-birth page. Recipients scan, sign up with their email, opt into labor texts if they want them, and get notified the moment labor begins.

**Why it matters:**
- Pre-builds the viewing audience before labor — no frantic group texts at 3am
- High-margin, low-cost physical product (~$25–40 for a pack of 30–50, fulfilled by Moo/Vistaprint/Printful)
- Creates a tangible keepsake artifact families also want to keep
- Generates earlier emotional investment in the page → higher gift conversion at the actual birth
- Natural integration with existing gift catalog infrastructure
- The shower-host role mechanic (see the v1 baby shower QR cards section) is the acquisition path for these cards — the host, not Sarah, is usually the buyer

**Implementation notes:**
- Pre-birth page is a simplified version of the live timeline (announcement, due date, optional belly photos, optional registry links)
- QR code encodes a family-specific invitation token that auto-creates a viewer subscription on scan
- Could ship as standalone product or as part of a "pregnancy package" with shower-related products

### Named family roles as acquisition architecture (v1.5+)

The shower-host role generalizes: co-parent, shower host… eventually a **"grandparent" invite** could do the same job for Day Two — Janet is already onboarded before labor instead of arriving cold via a link 48 hours after the birth. Not needed now, but the pattern — **named family roles that each map to a buyer moment** — is probably the product's real acquisition architecture. Each role gives someone a genuine capability (not an email capture), pulls them into an account early, and positions them at the moment they'd naturally buy.

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
