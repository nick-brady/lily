# Arrival Story — Hero Video Plan

The landing page hero: a full-bleed, muted, looping background video of one family's
arrival story, with a real (not baked-into-video) phone UI floating over it. As moments
happen in the video — a bump selfie, a contraction, a grandmother typing — the app on
the phone reacts in perfect sync: the photo drops into the timeline, the timer logs,
the comment pops in. The video carries the emotion; the phone carries the product.

This doc covers: how the mechanism works, how the app layer stays up to date, the cast,
the scene-by-scene storyboard with cue points, the Seedance production plan, and the
open decisions we still need to make together.

---

## 1. How it works — the layer stack

Three layers, bottom to top:

```
┌────────────────────────────────────────────────────────┐
│  Layer 3 — Phone mockup (real DOM)                     │
│     device frame + live app UI, floating left,         │
│     driven by the cue engine                           │
│  Layer 2 — Scrim (CSS gradient overlay)                │
│     dims/tints the video so UI + copy stay readable;   │
│     fades per scene, fades heavy at the loop seam      │
│  Layer 1 — Background video (<video>)                  │
│     muted · playsinline · loop · ~25-30s · 3-5 MB      │
└────────────────────────────────────────────────────────┘
```

**Layer 1 — the video.** Compressed hard (it's a background; faces can be soft, screens
never readable). Encoded as AV1/H.265 with H.264 fallback, `preload="metadata"` +
lazy-start so it never blocks LCP. A poster frame (best still from Scene 1) shows
instantly and for `prefers-reduced-motion` users.

**Layer 2 — the scrim.** A gradient overlay (dark-to-transparent, tinted toward the
brand fuchsia) that keeps headline copy and the phone legible over any footage. It
breathes: slightly lighter during bright scenes, heavier during the night-labor scene,
and it fades nearly opaque for ~1s at the loop point — which is also when the phone UI
quietly resets to its start state, so the loop seam is invisible.

**Layer 3 — the phone.** A CSS device frame (iPhone outline, notch, shadow) positioned
left-of-center, overlapping the video. Inside it: the app UI (see §2). It is *never*
part of the video — that's what keeps it razor sharp at any compression level and
always current with the real product.

### Reference implementation: natrx.io

The [natrx.io](https://natrx.io/) hero is Layers 1+2 of this exact pattern:
`<video autoplay playsinline loop muted>` with `object-fit: cover` in a fixed-height
section, and the "overlay" achieved by giving the section a near-black background
(`#221f20`) and drawing the video at `opacity: 0.6` — a uniform dark scrim by
subtraction. We do the same, with two upgrades: a gradient scrim that can shift per
scene (and cover the loop-seam reset), plus the synced phone layer on top.

One lesson *not* to copy: their background video is a 115 MB raw `.mov`. The 3-5 MB
encode target in §5 buys the same visual for ~4% of the bandwidth.

### The sync engine

A cue table maps video timestamps to UI events:

```js
const CUES = [
  { t: 3.2,  event: 'photo:snap' },       // flash in video → shutter in UI
  { t: 3.6,  event: 'timeline:addPhoto' } // photo card drops into timeline
  // ...
];
```

A `requestAnimationFrame` loop reads `video.currentTime` every frame and fires any cue
the playhead has crossed. **Never `setTimeout`** — background videos buffer, tabs get
backgrounded, autoplay gets delayed; wall-clock timers drift out of sync in seconds,
`currentTime` cannot. When `currentTime` wraps (loop), all cues re-arm and the UI
resets behind the scrim fade. Scrubbing/seeking is also free: the engine just replays
cues up to the new position, which makes development and QA trivial.

---

## 2. What's inside the phone — keeping it always up to date

Key realization: **the landing page already lives inside the product's React app**
(`frontend/src/pages/LandingPage.jsx`). So we don't need an iframe at all.

| Option | What it is | Verdict |
|---|---|---|
| A. Hand-built replica | Static HTML/CSS copy of the timeline | Fast to demo, but drifts out of date — exactly what you don't want |
| B. **Real components, demo-driven** | Mount the actual `Timeline`, `CommentThread`, `ReactionBar`, `ContractionButton` components in the hero with scripted fixture data; the cue engine dispatches events that mutate that fixture state | **Recommended** |
| C. iframe of the live app | A real public birth page in an iframe | Truly live, but un-choreographable (real data, no cue control), auth/seed-data headaches, fragile |

Option B gives you the "always up to date" property you want — when the timeline design
changes, the hero changes with it — while staying fully scriptable. The cue engine just
calls state setters (`addEntry(photoEntry)`, `addComment(janetComment)`,
`incrementReaction('❤️')`) and the real components animate exactly as they do in
production, because they *are* production.

If the marketing site ever moves off the app bundle (static Astro/Next site, etc.),
Option B converts cleanly to an iframe: the app exposes a `/demo/hero` route rendering
the same demo-driven components, and the marketing page drives it via `postMessage`
cues. Same cue table, one extra hop.

**Demo fixture:** one scripted birth — "Welcoming Lily Wren" (already the mock name on
the landing page) — with a fixed entry set that the cues reveal progressively.

---

## 3. The cast

Straight from `Lily-Personas.md`, so the video sells to exactly the people the product
serves. For Seedance consistency, each character gets a **character sheet**: 3-5
generated reference stills (front, 3/4, in-scene) locked before any video generation,
then attached as reference images to every shot they appear in.

### Sarah — the expecting parent
- **Role in video:** the center of gravity. Bump selfie in Scene 1; laboring
  (abstractly — breathing, gripping Marco's hand, never in distress-closeup) in
  Scene 2; resting with the baby *implied, never shown in closeup* at the end.
- **Look (consistency anchor):** early 30s, shoulder-length dark hair loosely tied
  back, warm undertone, oversized cream cardigan over a ribbed sage tank (pregnancy
  scenes), hospital gown + the same cardigan over shoulders (labor scenes).
- **Persona truth to honor:** during labor, **Sarah never touches the phone.** The
  product is *around* her, not in her hands. Marco runs the page.

### Marco — the partner
- **Role:** the operator. His hands and phone are the bridge between the room and the
  family. Taps the contraction timer, posts "water broke — game time", takes the
  photos, hits the "Baby Born" milestone.
- **Look:** mid 30s, short dark hair, stubble, olive henley (pre-labor), gray tee +
  hospital wristband (labor). Wedding band — helps hand-closeup continuity, and hand
  closeups are most of his screen time.

### Janet — the grandmother in Phoenix
- **Role:** the emotional receiver. Scene 3 is hers: lamp-lit living room, reading
  glasses, tea, typing a comment with two index fingers. Later, the slow scroll back
  through the finished timeline.
- **Look:** mid 60s, silver bob, reading glasses on a chain, terracotta cardigan,
  southwestern-warm living room (adobe tones, evening lamp light).

### Emma — Sarah's sister in Seattle
- **Role:** the far-away sibling who's *there anyway*. Checks the page on a bus / in a
  gray-drizzle kitchen. Hers is the comment that makes Sarah cry:
  *"We're with you. We're so proud."*
- **Look:** late 20s, dark hair like Sarah's (family resemblance helps the story read
  without dialogue), rust beanie + rain jacket, transit/urban Seattle palette (cool
  blues — deliberate contrast with Janet's warm Phoenix).

### Lisa — the friend
- **Role:** one quick beat in the reaction montage — reacts 🤩 from her office desk,
  grinning at her phone. (Her gift-buying arc is a different video.)
- **Look:** early 30s, curly auburn hair, blazer over tee, bright workplace.

**Baby Lily:** never shown as a rendered face. A swaddle from behind, a tiny hand
gripping a finger, out-of-focus warmth. AI newborn closeups are the highest
uncanny-valley risk in the whole project and suggestion is more powerful anyway.
The baby's face lives *in the app UI* as the timeline photo — and that photo can be a
real (licensed stock or your own) photograph, not AI.

---

## 4. Storyboard — scenes + cue table

Target: **~28s loop**, six scenes. Every scene = one Seedance generation (4-6s each),
cut together with 8-12 frame cross-dissolves. Color grade shifts warm→cool→warm to
mark place changes without any captions.

> Timings below are the working draft — they'll shift once real footage exists. The cue
> table is the contract between the edit and the UI; it's the one artifact both sides
> maintain.

### Scene 1 — "The first entry" (0:00–0:05) · bedroom, golden hour
Two shots:
- **Shot A (~3s):** from behind Sarah, facing a full-body mirror — clearly a bedroom,
  warm evening light. In the mirror: she's smiling, one hand holding her belly, phone
  raised in the other. *(Production note: mirror reflections are a known weak spot for
  video models — keep this shot short, favor the back-of-Sarah framing, and let the
  reflection sit soft/slightly out of focus.)*
- **Shot B (~2s):** cut to a direct view of Sarah looking at the photo on her phone,
  its light putting a soft glow on her face. She smiles and taps out the message —
  and on that tap, the photo pops into the timeline.
- **Phone UI:** starts **empty** — what a brand-new timeline looks like, no entries
  yet. At her tap: **the first photo card pops in** with the caption
  "36 weeks. Getting so close 🌸". The story literally begins on screen.
- **Cues:** `0:03.6 timeline:addPhoto` — single cue; her tap in Shot B is the trigger.

### Scene 2 — "Game time" (0:05–0:11) · hospital room, night
Cut to night. Handheld-feel closeup: Marco's thumb taps the phone; behind him,
soft-focus, Sarah on a birthing ball, breathing. No distress, no medical detail —
low warm light, calm intensity.
- **Phone UI:** the live contraction timer counting (`0:42…0:43…`), pulsing dot. At the
  tap: contraction logs → **"5 min apart" stat updates** → milestone entry appears:
  "Water broke — game time 💪"
- **Cues:** `0:07.5 contraction:stop` → `0:08.0 stats:update` → `0:09.0 timeline:addMilestone`

### Scene 3 — "Janet is typing…" (0:11–0:17) · Phoenix living room
Warm lamp light, Janet with tea, glasses low on her nose, typing carefully on her
phone. She smiles at something on the screen.
- **Phone UI:** viewer's perspective now (same page — that's the product point: *one
  page, everyone's window*). Typing indicator appears ("Mom is typing…"), then Emma's
  comment **pops in**: "We're with you. We're so proud. 💕" — then Janet's lands right
  after: "Praying for all three of you ❤️"
- **Cues:** `0:12.0 comments:typing` → `0:14.0 comments:add(emma)` → `0:16.0 comments:add(janet)`

### Scene 4 — "Everyone, everywhere" (0:17–0:21) · rapid montage
Three quick shots, ~1.3s each: Emma on a Seattle bus (cool blue, rain on glass) ·
Lisa at her desk, hand over mouth, grinning · Janet's finger tapping a heart.
- **Phone UI:** **reactions pour in** — ❤️ 14→23, 🙏 8→15, 🤩 5→11, counters ticking
  with tiny pops, a couple of floating hearts.
- **Cues:** `0:17.5 reactions:burst(start)` … eased random ticks … `0:21.0 reactions:burst(end)`

### Scene 5 — "She's here" (0:21–0:26) · the arrival
The most suggestion-driven scene: Marco's hand taps the phone once; light blooms;
a tiny hand grips his finger (macro, shallow focus); Sarah's exhausted-happy profile,
soft. **No rendered newborn face.**
- **Phone UI:** the page transforms — celebration animation (the product's real
  `CelebrationOverlay` / floating hearts), header becomes the birth announcement:
  **"Lily Wren · 4:47 AM · 7 lb 2 oz"**, first photo entry appears (real photograph,
  see §3), comments accelerate underneath.
- **Cues:** `0:22.0 birth:announce` → `0:22.5 celebration:play` → `0:24.0 timeline:addPhoto(lily)`

### Scene 6 — "The keepsake" (0:26–0:28) · quiet close
Janet again, later, scrolling slowly. Or simply the nursery from Scene 1, now with a
bassinet. The scrim deepens to near-opaque…
- **Phone UI:** slow auto-scroll up the *finished* timeline — the whole story at a
  glance — then, behind the darkened scrim, **reset to Scene 1 state**.
- **Cues:** `0:26.0 timeline:scrollTour` → `0:27.5 ui:reset` → loop

### Cue table (single source of truth)

| t | Video moment | UI event |
|------|---|---|
| 3.6 | Sarah's tap (Shot B) | `timeline:addPhoto(bump)` |
| 7.5 | Marco's tap | `contraction:stop` |
| 8.0 | — | `stats:update('5 min apart')` |
| 9.0 | — | `timeline:addMilestone('Water broke — game time 💪')` |
| 12.0 | Janet starts typing | `comments:typing` |
| 14.0 | — | `comments:add(emma)` |
| 16.0 | Janet smiles | `comments:add(janet)` |
| 17.5–21.0 | montage | `reactions:burst` |
| 22.0 | Marco's single tap | `birth:announce` |
| 22.5 | light bloom | `celebration:play` |
| 24.0 | tiny hand grips finger | `timeline:addPhoto(lily)` |
| 26.0 | Janet scrolls | `timeline:scrollTour` |
| 27.5 | scrim near-opaque | `ui:reset` → loop |

**Choreography rule:** the UI reacts 100–200ms *after* the on-screen gesture — that
tiny lag is what makes it read as cause-and-effect ("boom") rather than coincidence.

---

## 5. Producing the video (Seedance)

**Order of operations:**
1. **Character sheets first.** Generate stills of each character until the look locks
   (3-5 keepers each). These become reference images for every video shot. Do not
   generate a single second of video before the cast is locked — consistency is won or
   lost here.
2. **Location plates.** One still per location (nursery, hospital room, Phoenix living
   room, Seattle bus, office) — same idea, locks the set.
3. **Shots.** One generation per scene, 4-6s each, using character + location
   references. Expect 5-10 takes per shot; pick for *motion quality* over frame beauty
   (a background video's individual frames are never studied, its motion always is).
4. **Edit.** Assemble to the storyboard timings, grade for cohesion (single LUT,
   slightly lifted blacks — helps both mood and compression), export master.
5. **Lock the cue table** against the final edit's actual timestamps.

**Rules that protect the concept:**
- Phone screens in the video are always **dim, dark, or angled away**. The real UI
  lives only in the overlay. (This also makes every shot dramatically easier to
  generate.)
- No rendered newborn faces, no medical detail, no distress closeups.
- Stylize slightly — cinematic grade, shallow depth of field, lifted contrast — so the
  footage reads as intentional art direction, not failed photorealism.
- Silent by design (autoplay requires `muted` anyway).

**Delivery targets:** 1920×1080 master → web encodes ~1600px wide, AV1 + H.264
fallback, target **3-5 MB** for the loop; poster JPEG from Scene 1.

---

## 6. Page behavior details

**Wordmark write-on (separate PR, ships first).** The "Arrival Story" wordmark gets a
cursive write-on animation as a page-load overture — it plays once per visit, before
anything else moves (scrim heavy → wordmark writes ~1.5s → tagline/CTA fade up → video
brightens → phone choreography starts), never re-animates on loop, and falls back to
the static wordmark under `prefers-reduced-motion`. It's being implemented in its own
PR in parallel and will be live before the video; this hero simply slots in *after* it
in the load sequence.

- **Autoplay:** `muted playsinline loop` + poster. Start playback via
  IntersectionObserver when the hero is on screen.
- **Mobile:** side-by-side doesn't fit. The phone mockup takes center stage over a
  heavier scrim (or the poster image), and the cue engine runs the same choreography
  against an invisible clock (`requestAnimationFrame` accumulator standing in for
  `currentTime`) so mobile users still see the app *perform* even without the video.
- **Reduced motion / data-saver:** poster + static timeline in its finished state.
- **Loop seam:** handled by the Scene 6 scrim fade + `ui:reset` (see storyboard).
- **Perf:** video lazy-loaded after LCP; the hero headline + CTA render immediately
  and never depend on the video.

---

## 7. Open decisions (to work through together)

1. **Scene 1 protagonist** — ✅ resolved in PR review: Sarah, two-shot structure
   (mirror wide → phone-glow closeup), empty timeline, single `addPhoto` cue on her tap.
2. **The baby photo in the app** — real licensed photo, your own photo, or none
   (announcement card with name/weight/time only, no photo). Recommend a real photo;
   the announcement-only variant is the safe fallback.
3. **Comment copy** — the lines above are drafts pulled from the personas. Worth one
   pass together; these words are the emotional payload of the whole hero.
4. **Loop length** — 28s as drafted, or a tighter 18-20s (drop Scene 4 montage,
   fold reactions into Scene 3)? Shorter loops repeat more visibly but cost less to
   produce and load.
5. **Whether Scene 6 exists** — ending on the birth (Scene 5) and looping straight
   from the celebration is punchier; Scene 6 is the "keepsake forever" brand message.
   Both defensible.
6. **Seedance tier/version** — affects per-shot cost and how many takes are realistic.
   Worth a small test batch (one character sheet + one 5s shot) before committing to
   the full board.

## 8. Suggested build order

1. ✅ This plan.
2. **Prototype the mechanism now with a placeholder video** (ffmpeg-generated scene
   cards standing in for real footage) — proves the sync engine, the scrim, the loop
   reset, and lets us tune choreography timing before any Seedance spend.
3. Lock characters + comment copy (§7.1–.3) → generate character sheets.
4. Test batch: one shot end-to-end (Scene 1) → judge quality → go/no-go on full board.
5. Generate remaining shots, edit, grade, encode.
6. Wire the real components (Option B) into the hero, swap placeholder for final
   video, lock cue table.
