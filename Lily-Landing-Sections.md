# Lily — Landing Page Sections

The landing page is growing a band of full-bleed "why it's nice" sections that sit
under the hero video (see `Lily-Hero-Video-Plan.md`). Each section dramatizes one
visceral, universally-recognized benefit — shown, not explained. This doc is the
spec for that band; each section gets its own numbered entry.

Shared conventions for every section in the band:

- **Autoplay on scroll-into-view.** Sections play once when they enter the viewport
  (IntersectionObserver), hold their end state, and replay only after fully leaving
  the viewport and re-entering. No scroll-hijacking, no pinned scrubbing.
- **Real product components inside any phone render.** Same "zero drift by
  construction" decision as the hero video plan §2: the landing page lives in the
  app bundle, so phone screens mount the actual `Timeline` / `ReactionBar` /
  `CommentThread` fed by scripted fixture data. Only *other apps'* UI (generic
  messaging notifications, etc.) is hand-mocked.
- **`prefers-reduced-motion`**: every section renders a static equivalent (end
  states side by side) instead of animating.
- **Lightweight**: CSS keyframes + a few timeouts + one observer per section. No
  animation libraries.
- **Mobile-first**: single-column layouts that work at every width; desktop gets
  wider arrangements, never a separate concept.

Sections 1–3 share one section shell: **the phone carousel**
(`frontend/src/components/landing/PhoneCarouselSection.jsx`). All three dramatize
the same "Welcoming Lily Wren" page at different moments — the family's view
during labor (§1), the parent's view during labor (§2), the keepsake after (§3) —
so they read as one continuous story told on one phone. Carousel mechanics:

- Dots + chevrons below the slides, plus touch swipe. Slide track is a plain
  translateX flex row, 700ms ease-out.
- Slide 1 autoplays per the band convention. A few seconds after each slide's
  sequence completes, the carousel **auto-advances to the next** — unless the
  visitor has navigated manually, which disables auto-advance until reset.
- Fully leaving the viewport resets everything (slides remount, back to slide 1),
  matching the play-once/replay-on-reenter convention.
- Reduced motion: no autoplay, no auto-advance, no keepsake auto-scroll — a
  manual carousel of static end states.

---

## Section 1 — "One place to update, not scattered threads"

### The pain being dramatized

The product's most universal pain point is not contraction timing — it's that
during labor, the partner drowns in "any update??" texts across multiple group
chats (his parents, her parents, siblings) at exactly the moment he has the least
capacity to reply. Arrival Story's core value is replacing that chaos with one
controlled broadcast: post one update, everyone sees it, nobody has to be
individually answered. Hard to explain in words, instantly recognizable when
shown. The visitor should think "oh god, that's going to be us" within five
seconds — then feel the relief.

Tone guardrails:

- The left-side texts read as **loving-but-overwhelming, never mean**. The family
  isn't the villain; the fragmentation is.
- Nothing clinically intimate. The app-side message is a curated status update,
  not a live medical feed. The right side's tone is "keeping you close without
  burdening us."

### The concept: one phone that transforms

Two columns on desktop: the left column holds the headline + subhead at the
top with the swapping beat caption below them at mid-height; one persistent
phone frame sits to the right, slightly off-center. On mobile the column
stacks (headline, caption, phone). The phone's *contents* transform between
beats. This was chosen over a
split-screen before/after because it keeps cause-and-effect in a single frame —
chaos → one update → silence is the emotional argument, and the **stopping of the
chaos is the payoff**. Two static panels make the comparison; the transformation
makes the relief.

### Beat script

- **Beat 1 — caption: "Your family will want updates"** (~5s)
  - Generic grayed messaging notifications stack onto a dark lock screen at an
    accelerating rhythm, slightly overlapping, each with a subtle buzz on arrival,
    badge count climbing.
  - The pile: "Any update?? 😊" (Mom), "How's she doing?!" (Dad), "Anything
    yet???" (Em), "Is the baby here??" (Mom again), "Call me when you can!"
    (Aunt Linda), "Sorry, I know you're busy!! Just checking ❤️" (Grandma Janet),
    a missed call, a typing indicator.
- **Transition — the payoff beat** (~1s)
  - Caption 1 fades out; notifications freeze, desaturate, settle. A deliberate
    half-second of engineered stillness. This beat is load-bearing — do not
    simplify it away.
- **Beat 2 — caption: "Give updates in one place"** (~5s)
  - Phone contents cross-fade to the Arrival Story page ("Welcoming Lily Wren",
    Great Vibes header, live contraction banner).
  - An update posts into the real timeline: *"No big update yet — still in active
    labor. Contractions are getting closer 💜"*
  - Reactions tick up on the real `ReactionBar` (💖 ✨ 🙏), then a comment appears
    ("Thinking of you three every minute. So excited!! 💜" — Grandma Janet).
  - End state holds — one calm screen, everyone informed, nothing demanding a
    reply.

### Copy

- Section headline: **"One place to update, not scattered threads."**
- Subhead: *"Post once to your family's page — everyone follows along without
  blowing up your phone."*
- Beat captions as above.

### Implementation map

- `frontend/src/components/landing/PhoneCarouselSection.jsx` — carousel shell:
  IntersectionObserver trigger/replay, slide track, dots/chevrons/swipe,
  auto-advance after slide 1 completes.
- `frontend/src/components/landing/OnePlaceSlide.jsx` — slide 1: beat state
  machine (`idle → chaos → settle → broadcast → done`), captions, reduced-motion
  static comparison.
- `frontend/src/components/landing/AppScreen.jsx` — the shared miniature of the
  public birth page (pinned header, banner, real `Timeline`); exposes a
  `scrollRef` viewport for programmatic scrolls.
- `frontend/src/components/landing/PhoneFrame.jsx` — reusable device frame (the
  hero video phone will want it too).
- `frontend/src/components/landing/NotificationChaos.jsx` — beat-1 mocked
  notification stack.
- `frontend/src/components/landing/demoBirth.js` — the "Welcoming Lily Wren"
  fixture: events, reaction tick script, comment. Written to be reusable by the
  hero video cue engine later.
- `CommentThread` gained demo props (`initialComments`, `defaultExpanded`) that
  skip the API fetch and hide the composer — the same affordance the hero video's
  `addComment` cue needs.

---

## Section 2 — "It's a contraction timer"

### The promise being dramatized

Visitors who arrive thinking "contraction timer app" need to see that the pretty
family page is *also* the tool: the parent's view has a big start/stop button,
and every timed contraction lands on the timeline everyone follows. Show the
button being pressed — the state change is the explanation.

### The concept: the parent's phone, pressed

Same two-column layout; the phone shows the **parent's manage view** for the
first time — the real `ContractionButton` in its card above the real `Timeline`
of already-logged contractions (~5 minutes apart), mirroring `BirthManagePage`'s
layout in miniature.

Beat script (starts when the slide becomes active):

- **Beat 1 — caption: "A contraction starts — tap"** (~2s): idle 00:00 + START
  CONTRACTION button.
- **Beat 2 — caption: "Tap again when it ends"** (~7s): a press ripple hits the
  button; the timer runs red with STOP. Deliberate cheat: `startTime` is
  backdated ~48s at the press so the timer reads mid-contraction (00:48 →
  00:55) and the logged duration is realistic — an honest 7s demo contraction
  would log a nonsense "7s" row. One frame of cheat, hidden under the ripple.
- **Beat 3 — caption: "Timed, logged, shared — automatically"**: STOP clears,
  the new contraction row drops into the timeline at a plausible spacing.

### Copy

- Slide headline: **"And yes — it's a contraction timer."**
- Subhead: *"One tap when a contraction starts, one when it ends. Timing,
  spacing, and telling everyone — handled."*
- Beat captions as above.

### Implementation map

- `frontend/src/components/landing/TimerSlide.jsx` — slide 2: `idle → running →
  logged` cue script, press ripple, parent-screen miniature, reduced-motion
  static render (idle button above three logged rows).
- `frontend/src/components/landing/demoBirth.js` — `makeTimerBaseEvents()`,
  `makeLoggedContraction()`.
- Uses `ContractionButton` and `Timeline` untouched — the button is fully
  presentational (`onStart`/`onStop`/`startTime`), so no demo affordances were
  needed.

---

## Section 3 — "A keepsake, forever"

### The promise being dramatized

Section 1 sells the during-labor relief; this slide sells what's left afterward.
Group-chat threads scatter and scroll away; the Arrival Story page *becomes the
story* — every voice memo, photo, contraction, and comment, in order, exactly as
it happened. The visitor should feel the shift from utility to heirloom: the same
page they just watched calm the chaos is also the thing they'll reread in five
years.

Tone guardrails:

- Warm, not sentimental-syrupy. The timeline speaks for itself; the copy stays
  short.
- The story shown is the *completed* Lily Wren arc — same family, same
  active-labor update (same 12 💖 and Grandma Janet comment) seen in section 1,
  so the carousel reads as one continuous story.

### The concept: scrolling back through the finished story

Same two-column layout as slide 1 (headline left, phone right). The phone shows
the finished "Welcoming Lily Wren" page — banner now reads *"Lily is here 🤍 The
whole story, saved."* — and slowly auto-scrolls down through the timeline like a
hand idly reliving it: name announcement → first photo → born → Dad's voice memo
→ the overnight contractions → water broke → the 40-week bump photo. Newest-first
order means scrolling down is scrolling *back in time* — the "look back" made
literal. ~18s ease-in-out scroll after a ~1s hold, then it rests at the beginning
of the story.

### The keepsake fixture

`makeKeepsakeEvents()` in `demoBirth.js` — spans "Yesterday" and "Today" date
groups. Placeholder media until real assets exist: photos are soft abstract
gradient SVGs (data URIs, captions carry the meaning); the voice memo is a
runtime-generated silent WAV so the real audio player renders with a real
duration. `Timeline`'s `MediaItem` learned `payload.demo_media_url` (same
pattern as `demo_comments`) so fixtures can bundle media inline. No absolute
clock times in copy — timestamps are relative to "now".

### Copy

- Slide headline: **"A keepsake, forever."**
- Subhead: *"After the big day, the page becomes the story — every voice memo,
  photo, and contraction, kept exactly as it happened."*
- Caption: *"Look back anytime"*

### Implementation map

- `frontend/src/components/landing/KeepsakeSlide.jsx` — slide 2: headline,
  requestAnimationFrame scroll of the `AppScreen` viewport, starts once when the
  slide first becomes active.
- `frontend/src/components/landing/demoBirth.js` — `makeKeepsakeEvents()`,
  placeholder photo SVGs, `demoVoiceMemoUrl()`.
- `frontend/src/components/Timeline.jsx` — `demo_media_url` fixture affordance.
