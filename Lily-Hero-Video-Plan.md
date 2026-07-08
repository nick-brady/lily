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
│     muted · playsinline · loop · ~41s · 3-5 MB         │
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

## 2. What's inside the phone — real components, demo-driven

**Decision: the phone runs the real product components.** The landing page already
lives inside the product's React app (`frontend/src/pages/LandingPage.jsx`), so the
hero mounts the actual `Timeline`, `CommentThread`, `ReactionBar`, and
`ContractionButton` components directly — no iframe, no replica — fed with scripted
fixture data. The cue engine dispatches events that mutate that fixture state
(`addEntry(photoEntry)`, `addComment(janetComment)`, `incrementReaction('❤️')`) and
the components animate exactly as they do in production, because they *are*
production. When the timeline design changes, the hero changes with it — zero drift
by construction.

If the marketing site ever moves off the app bundle (static Astro/Next site, etc.),
this converts cleanly to an iframe: the app exposes a `/demo/hero` route rendering
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
  (abstractly — breathing, gripping Marco's hand, never in distress-closeup) through
  the labor arc; and the closing beat — baby asleep on her chest (no face shown),
  scrolling her own finished story.
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
- **Role:** the emotional receiver — and the *first* responder. Scene 3 is her quick
  cutaway: delighted gasp at the live contraction timer, hand to chest, a rapid
  tap-tap-tap comment. She reappears tapping a heart in the montage flicker, and
  anchors the split-screen finale: gasping, hands to face.
- **Look:** mid 60s, silver bob, reading glasses on a chain, terracotta cardigan,
  southwestern-warm living room (adobe tones, evening lamp light).

### Emma — Sarah's sister in Seattle
- **Role:** the far-away sibling who's *there anyway*. Scene 8 is hers: gray-drizzle
  Seattle kitchen, typing slowly and meaning it. Hers is the comment that makes Sarah
  cry: *"We're with you. We're so proud."* Laugh-crying in her split-screen panel.
- **Look:** late 20s, dark hair like Sarah's (family resemblance helps the story read
  without dialogue), rust beanie + rain jacket, transit/urban Seattle palette (cool
  blues — deliberate contrast with Janet's warm Phoenix).

### Lisa — the friend
- **Role:** three quick beats — a 1s cutaway right after the hospital-arrival
  milestone (eyes wide at her desk, can't sit still), a 🤩 reaction in the montage
  flicker, and mid-cheer in her split-screen panel. (Her gift-buying arc is a
  different video.)
- **Look:** early 30s, curly auburn hair, blazer over tee, bright workplace.

**Baby Lily:** never shown as a rendered face. A swaddle from behind, a tiny hand
gripping a finger, out-of-focus warmth. AI newborn closeups are the highest
uncanny-valley risk in the whole project and suggestion is more powerful anyway.
The baby's face lives *in the app UI* as the timeline photo — and that photo can be a
real (licensed stock or your own) photograph, not AI.

---

## 4. Storyboard — scenes + cue table

Target: **~41.5s loop**, twelve scenes plus one phone-only interstitial. Most scenes =
one Seedance generation (1-5s each); the decision triptych, the montage flicker, and
the split-screen finale are separate short generations composited in the edit. Color
grade shifts warm→cool→warm to mark place changes without any captions. The labor arc
runs as a four-beat journey (home → decision → arrival → active labor) so the
contraction timer gets a real introduction and "5 min apart" is *demonstrated*, not
asserted. Birth payoff lands at ~0:31; the split-screen "one moment, everywhere"
finale is the thesis shot.

> Timings below are the working draft — they'll shift once real footage exists. The cue
> table is the contract between the edit and the UI; it's the one artifact both sides
> maintain.

### Scene 1 — "The first entry" (0:00–0:05) · bedroom, golden hour
Two shots:
- **Shot A (~2s max):** from behind Sarah, facing a full-body mirror — clearly a
  bedroom, warm evening light. In the mirror: she's smiling, one hand holding her
  belly, phone raised in the other. *(Production note: mirror reflections are a known
  weak spot for video models — the short duration helps; favor the back-of-Sarah
  framing and let the reflection sit soft/slightly out of focus.)*
- **Shot B (~2s + ~1s hold):** cut to a direct view of Sarah looking at the photo on
  her phone, its light putting a soft glow on her face. She smiles and taps out the
  message — on that tap, the photo pops into the timeline — then the shot holds a
  beat on her afterglow while the viewer's eye jumps to the phone.
- **Phone UI:** starts **empty** — what a brand-new timeline looks like, no entries
  yet. At her tap: **the first photo card pops in** with the caption
  "36 weeks. Getting so close 🌸". The story literally begins on screen.
- **Cues:** `0:03.6 timeline:addPhoto` — single cue; her tap in Shot B is the trigger.

### Scene 2 — "Labor begins" (0:05–0:09) · living room, daytime — energetic
The mood is excited, almost giddy: *this is the day.* Sarah bounces gently on an
exercise ball, laughing between breaths. A contraction starts — she holds her belly
with one hand and puts her head down, steadying. Marco, grinning, taps a button on
the phone. No fear anywhere in this scene; it's game-day energy.
- **Phone UI:** the contraction timer gets its proper introduction — the timer card
  **activates at Marco's tap** and starts counting (`0:01…0:02…`), pulsing dot alive.
- **Cues:** `0:07.0 contraction:start`

### Scene 3 — "Janet's first look" (0:09–0:11.5) · Phoenix, quick cut
Brief cutaway: Janet sees the live contraction on her phone — a delighted gasp, hand
to chest, then a quick two-finger tap-tap-tap of a comment. Pure excitement, ~2.5s.
- **Phone UI:** Janet's comment **pops in**: "It's happening!! We love you three so
  much ❤️❤️" — while the timer is still counting. The post→family-lights-up loop is
  now established grammar, ready to pay off later.
- **Cues:** `0:10.0 comments:add(janet)`

### Interstitial — time passes (0:11.5–0:13.5) · phone-only
No new footage: Scene 3 slow-fades toward Scene 4 (scrim dips to carry the gap in
time). The storytelling happens entirely on the phone: the running contraction logs,
then **entries flood in, in clusters** — a few measured close together, a gap, a few
more — hours compressed into two seconds, and the gaps quietly say *not every
contraction needs to be measured*.
- **Cues:** `0:11.6 contraction:stop` → `0:11.9–0:13.3 timeline:contractionFlood`

### Scene 4 — "The decision" (0:13.5–0:16.5) · home, dusk — three quick shots
- **Shot A (~1s):** closeup — the hospital bag zips shut by the door.
- **Shot B (~1.2s):** the look between Sarah and Marco — determined, but excited.
- **Shot C (~0.8s):** Marco's hand slides across the table and grabs the keys.
Shots A and C are faceless closeups — cheap to generate, zero consistency risk — and
C is the perfect last image of home: decision → resolve → action.
- **Phone UI:** on the shared look, the stat line updates: **"5 min apart"**. The
  number is the *reason they're leaving*, and the viewer just watched it become true.
- **Cues:** `0:14.5 stats:update('5 min apart')`

### Scene 5 — "Arrival" (0:16.5–0:18.5) · hospital doors
Sliding doors, Marco wheeling Sarah in — the color grade shifts warm home → cool
clinical-but-comforting hospital. The location change is told in light; the check-in
is told by the phone, not the footage.
- **Phone UI:** milestone pops: **"Arrived at the hospital 🏥"** — no need to show
  Marco entering it.
- **Cues:** `0:17.5 timeline:addMilestone('Arrived at the hospital 🏥')`

### Scene 6 — "Lisa can't sit still" (0:18.5–0:19.5) · quick cut
One second: Lisa at her desk sees the arrival milestone — eyes wide, grabs a
coworker's arm / bounces in her chair. Super excited.
- **Phone UI:** **quiet — the rest beat.** The milestone just landed; let it breathe
  so the next hit lands harder.
- **Cues:** *none*

### Scene 7 — "Game time" (0:19.5–0:24.5) · hospital room, night
Handheld-feel closeup: Marco's thumb taps the phone; behind him, soft-focus, Sarah
on a birthing ball, breathing. No distress, no medical detail — low warm light, calm
intensity. This lands as the *culmination* of the journey, not the opener.
- **Phone UI:** milestone entry appears: **"Water broke — game time 💪"**
- **Cues:** `0:21.0 timeline:addMilestone`

### Scene 8 — "We're with you" (0:24.5–0:29) · Seattle, gray drizzle
Emma in her kitchen, rain on the window, cool blue light — deliberate contrast with
Janet's warm Phoenix. She types slowly, meaning it. A soft smile as she hits send.
- **Phone UI:** no typing indicator (the app doesn't have one — the video carries the
  typing); her comment **pops in when she hits send**: "We're with you. We're so
  proud. 💕" — the line that makes Sarah cry in the personas doc.
- **Cues:** `0:27.5 comments:add(emma)`

### Scene 9 — "Everyone, everywhere" (0:29–0:30.5) · montage flicker
Compressed to a ~1.5s flicker — three beats of ~0.5s: Lisa hand-over-mouth · Janet's
finger tapping a heart · Emma smiling down at her phone. It reads as texture, not a
sequence; the *real* ensemble moment is saved for the split-screen finale.
- **Phone UI:** **reactions pour in** — ❤️ 14→23, 🙏 8→15, 🤩 5→11, counters ticking
  with tiny pops, a couple of floating hearts.
- **Cues:** `0:29.0 reactions:burst(start)` … eased random ticks … `0:30.5 reactions:burst(end)`

### Scene 10 — "She's here" (0:30.5–0:35.5) · the arrival
The most suggestion-driven scene: Marco's hand taps the phone once; light blooms;
a tiny hand grips his finger (macro, shallow focus); Sarah's exhausted-happy profile,
soft. **No rendered newborn face.**
- **Phone UI:** the page transforms — celebration animation (the product's real
  `CelebrationOverlay` / floating hearts), header becomes the birth announcement:
  **"Lily Wren · 4:47 AM · 7 lb 2 oz"**, first photo entry appears (real photograph,
  see §3).
- **Cues:** `0:31.0 birth:announce` → `0:31.5 celebration:play` → `0:33.5 timeline:addPhoto(lily)`

### Scene 11 — "One moment, everywhere" (0:35.5–0:39.5) · split-screen finale
The thesis shot. The announcement has just published — and the screen splits into
three diagonal panels ( / / / ) that **slam in staggered**, ~0.2s apart, like the
notification hitting phone after phone: Janet gasping hands-to-face → Emma
laugh-crying → Lisa mid-cheer. Three ordinary shots, generated separately, composited
into panels in the edit. One second, three living rooms: everyone sees it the moment
it happens.
- **Framing:** each shot tight, centered, portrait-ish with generous headroom —
  diagonal slices crop hard. The **left panel is the most atmospheric** (silhouette +
  phone glow) since the phone mockup partially covers it.
- **Phone UI:** their comments pop in one after another as each panel reacts —
  Janet: "SHE'S HERE!! 😭❤️" · Emma: "Welcome to the world, Lily 🌎💕" · Lisa:
  "I can't stop crying!! CONGRATULATIONS 🎉" — with the reaction counters spiking
  underneath. Three comments in ~3s is the readability ceiling; the counters do the
  "everyone" work.
- **Cues:** panels land 0:35.6/0:35.8/0:36.0 (video-side) →
  `0:36.2 comments:add(janet)` → `0:37.2 comments:add(emma)` →
  `0:38.2 comments:add(lisa)` + `reactions:spike`

### Scene 12 — "The keepsake" (0:39.5–0:41.5) · quiet close
**Sarah**, later — dim room, baby asleep on her chest (swaddle from behind, no face),
phone glow soft on her face as she scrolls slowly back through her own finished
story. The author reading the book. The scrim deepens to near-opaque…
- **Phone UI:** slow auto-scroll up the *finished* timeline — the whole story at a
  glance — then, behind the darkened scrim, **reset to Scene 1 state**.
- **Cues:** `0:39.5 timeline:scrollTour` → `0:41.0 ui:reset` → loop

### Cue table (single source of truth)

| t | Video moment | UI event |
|------|---|---|
| 3.6 | Sarah's tap (Shot B) | `timeline:addPhoto(bump)` |
| 7.0 | Marco's tap as her head drops | `contraction:start` — timer card activates, counting |
| 10.0 | Janet's quick tap-tap-tap | `comments:add(janet)` |
| 11.6 | slow fade begins | `contraction:stop` — entry logs |
| 11.9–13.3 | crossfade carries the time gap | `timeline:contractionFlood` — clustered entries: a few, a gap, a few more |
| 14.5 | the shared look (Shot B) | `stats:update('5 min apart')` |
| 17.5 | doors slide open | `timeline:addMilestone('Arrived at the hospital 🏥')` |
| 18.5–19.5 | Lisa beams | *quiet — rest beat, no event* |
| 21.0 | Marco's tap | `timeline:addMilestone('Water broke — game time 💪')` |
| 27.5 | Emma hits send | `comments:add(emma)` |
| 29.0–30.5 | montage flicker | `reactions:burst` |
| 31.0 | Marco's single tap | `birth:announce` |
| 31.5 | light bloom | `celebration:play` |
| 33.5 | tiny hand grips finger | `timeline:addPhoto(lily)` |
| 35.6/35.8/36.0 | split panels slam in (Janet→Emma→Lisa) | *video-side; UI holds a beat* |
| 36.2 | Janet's panel reacts | `comments:add(janet)` — "SHE'S HERE!! 😭❤️" |
| 37.2 | Emma's panel | `comments:add(emma)` — "Welcome to the world, Lily 🌎💕" |
| 38.2 | Lisa's panel | `comments:add(lisa)` + `reactions:spike` |
| 39.5 | Sarah scrolls, baby on chest | `timeline:scrollTour` |
| 41.0 | scrim near-opaque | `ui:reset` → loop |

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
3. **Shots.** Roughly 15 generations across twelve scenes, 1-5s each — the decision
   triptych, montage flicker, and split-screen finale are separate short shots
   composited in the edit; the quick cuts are mostly faceless and cheap; the
   interstitial needs no footage at all. Use character + location references
   throughout. Expect 5-10 takes per shot; pick for *motion quality* over frame beauty
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
4. **Loop length** — ✅ resolved in review: ~41.5s, twelve scenes + a phone-only
   interstitial, four-beat labor arc (home → decision → arrival → active labor) with
   Janet's cutaway between beats 1-2, Lisa's after the arrival milestone, and the
   split-screen "one moment, everywhere" finale between the birth and the keepsake.
   Birth payoff at ~0:31. Since the video starts at 0:00 on page load for every
   visitor, loop length costs little; shot count (~15 generations) is the real spend.
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
6. Wire the real components (§2) into the hero, swap placeholder for final
   video, lock cue table.
