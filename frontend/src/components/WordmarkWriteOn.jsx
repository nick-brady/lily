import { useEffect, useId, useRef, useState } from 'react';
import trace from '../assets/wordmark-trace.json';

// The wordmark writes itself once per page load, then stays static. The trace
// data is a real hand-tracing of the wordmark (see tools/wordmark-tracer.html):
// pen strokes in writing order — ending with dotting the i and crossing the t —
// each a polyline of [x, y, tMs] points in the SVG's coordinate space.
// Playback reveals the filled text through a fat round-capped stroke mask, so
// the hand's own rhythm (speed changes mid-stroke, pen-lift pauses) survives;
// only the clock is compressed from the multi-minute tracing to WRITE_MS.

const WRITE_MS = 2800;
const START_DELAY_MS = 250;

// Written once per page load: a refresh replays it, but navigating away and
// back within the SPA does not — the wordmark never re-animates mid-visit.
let hasWritten = false;

// Inter-stroke pauses in the recording are thinking time, not rhythm — clamp
// them to a natural pen-lift beat. Within-stroke timing is kept verbatim.
// Each stroke gets a `shift` that moves its raw timestamps onto the clamped
// timeline. (The tracer's preview clamps identically, so what was approved
// there is what plays here.)
const MIN_GAP_MS = 60;
const MAX_GAP_MS = 600;

let prevRawEnd = null;
let prevNewEnd = 0;
const STROKES = trace.strokes.map(({ points }) => {
  let len = 0;
  const cumLen = points.map((p, i) => {
    if (i) len += Math.hypot(p[0] - points[i - 1][0], p[1] - points[i - 1][1]);
    return len;
  });
  const t0 = points[0][2];
  const t1 = points[points.length - 1][2];
  const gap =
    prevRawEnd === null
      ? 0
      : Math.min(Math.max(t0 - prevRawEnd, MIN_GAP_MS), MAX_GAP_MS);
  const shift = prevNewEnd + gap - t0;
  prevRawEnd = t1;
  prevNewEnd = t1 + shift;
  return {
    d: points.map((p, i) => `${i ? 'L' : 'M'}${p[0]} ${p[1]}`).join(''),
    points,
    cumLen,
    total: len,
    t0,
    t1,
    shift,
  };
});
const RAW_TOTAL_MS = prevNewEnd;

// Arc length the pen had covered at raw-recording time t
function lengthAt(stroke, t) {
  if (t <= stroke.t0) return 0;
  if (t >= stroke.t1) return stroke.total;
  const { points, cumLen } = stroke;
  let lo = 0;
  let hi = points.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (points[mid][2] < t) lo = mid + 1;
    else hi = mid;
  }
  const a = points[lo - 1];
  const b = points[lo];
  const k = (t - a[2]) / (b[2] - a[2] || 1);
  return cumLen[lo - 1] + k * (cumLen[lo] - cumLen[lo - 1]);
}

export default function WordmarkWriteOn({ className = '', onComplete }) {
  const maskId = useId();
  const pathRefs = useRef([]);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const [staticRender] = useState(
    () =>
      window.matchMedia('(prefers-reduced-motion: reduce)').matches || hasWritten
  );

  useEffect(() => {
    if (staticRender) {
      onCompleteRef.current?.();
      return undefined;
    }
    let raf;
    let cancelled = false;

    // Don't put pen to paper until the script face is actually loaded,
    // or the mask would trace glyphs that aren't there yet.
    document.fonts.load(`${trace.fontSize}px '${trace.font}'`).then(() => {
      if (cancelled) return;
      const scale = WRITE_MS / RAW_TOTAL_MS;
      const begin = performance.now() + START_DELAY_MS;
      const tick = (now) => {
        const rawT = (now - begin) / scale;
        let done = true;
        STROKES.forEach((s, i) => {
          const el = pathRefs.current[i];
          if (!el) return;
          const drawn = lengthAt(s, rawT - s.shift);
          el.setAttribute('stroke-dashoffset', s.total - drawn);
          if (drawn < s.total) done = false;
        });
        if (!done) raf = requestAnimationFrame(tick);
        else {
          hasWritten = true;
          onCompleteRef.current?.();
        }
      };
      raf = requestAnimationFrame(tick);
    });

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
    };
  }, [staticRender]);

  return (
    <svg
      viewBox="116 30 784 244"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {!staticRender && (
        <defs>
          <mask id={maskId} maskUnits="userSpaceOnUse">
            <rect x="0" y="0" width="1000" height="320" fill="black" />
            {/* Each dash gap is longer than its path: with round linecaps, a
                dash pattern that wraps around paints a stray dot at the
                stroke's endpoint before the pen ever gets there. */}
            <g
              fill="none"
              stroke="white"
              strokeWidth={trace.maskWidth}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              {STROKES.map((s, i) => (
                <path
                  key={i}
                  ref={(el) => {
                    pathRefs.current[i] = el;
                  }}
                  d={s.d}
                  strokeDasharray={`${s.total} ${s.total + trace.maskWidth * 2}`}
                  strokeDashoffset={s.total}
                />
              ))}
            </g>
          </mask>
        </defs>
      )}
      <text
        x="500"
        y="200"
        textAnchor="middle"
        fontFamily={`'${trace.font}', cursive`}
        fontSize={trace.fontSize}
        transform={trace.transform ?? undefined}
        fill="currentColor"
        mask={staticRender ? undefined : `url(#${maskId})`}
      >
        {trace.text}
      </text>
    </svg>
  );
}
