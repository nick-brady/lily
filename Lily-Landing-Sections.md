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

- `frontend/src/components/landing/OnePlaceSection.jsx` — section shell, beat
  state machine (`idle → chaos → settle → broadcast → done`), captions,
  IntersectionObserver trigger/replay, reduced-motion static fallback.
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
