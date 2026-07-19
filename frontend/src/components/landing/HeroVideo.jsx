import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import Timeline from '../Timeline';
import WordmarkWriteOn from '../WordmarkWriteOn';
import PhoneFrame from './PhoneFrame';
import useHeroCueEngine from '../../hooks/useHeroCueEngine';
import {
  HERO_POSTER_SRC,
  HERO_VIDEO_SRC,
  finalHeroState,
} from './heroCues';

// The hero: a full-bleed looping video of one family's arrival story, with
// the real product UI floating over it in a phone frame, reacting in sync
// with the footage via the cue engine (Lily-Hero-Video-Plan.md §1).
//
// Desktop: video background · phone left (~150px inset) · copy center-right.
// Mobile: no video (poster + heavy scrim); the phone takes center stage and
// the same choreography runs on an internal clock.
// Reduced motion: poster + the timeline in its finished state.

const CONFETTI = ['🤍', '💛', '🎉', '👶', '✨', '🩷', '🎈'];

function InPhoneCelebration() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 z-10 overflow-hidden">
      {Array.from({ length: 14 }, (_, i) => (
        <span
          key={i}
          className="absolute bottom-0 animate-float-up select-none"
          style={{
            left: `${(i * 37) % 100}%`,
            fontSize: `${1 + ((i * 7) % 12) / 10}rem`,
            animationDelay: `${(i % 7) * 0.3}s`,
            '--float-dur': `${4 + ((i * 13) % 25) / 10}s`,
            '--float-rot': `${((i * 53) % 80) - 40}deg`,
          }}
        >
          {CONFETTI[i % CONFETTI.length]}
        </span>
      ))}
    </div>
  );
}

function ContractionTimerCard() {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 250);
    return () => clearInterval(id);
  }, []);
  const mm = Math.floor(elapsed / 60);
  const ss = String(elapsed % 60).padStart(2, '0');
  return (
    <div
      className="mx-3 mt-3 flex items-center gap-3 rounded-xl px-3 py-2"
      style={{ backgroundColor: 'var(--t-soft-bg)' }}
    >
      <span
        className="h-2.5 w-2.5 flex-shrink-0 rounded-full animate-pulse"
        style={{ backgroundColor: 'var(--t-dot)' }}
      />
      <div>
        <div className="text-[10px] t-faint">Contraction in progress</div>
        <div className="text-lg font-mono font-semibold t-ink tracking-tight leading-tight">
          {mm}:{ss}
        </div>
      </div>
    </div>
  );
}

// The phone screen: real product components fed by cue-engine state, framed
// by a miniature of the public birth page chrome.
function HeroAppScreen({ state }) {
  return (
    <div
      className="demo-phone relative h-full overflow-hidden"
      style={{ backgroundColor: 'var(--t-page-bg)' }}
    >
      {state.celebrate && <InPhoneCelebration />}
      <div
        className="px-4 pt-10 pb-3 text-center"
        style={{
          backgroundColor: 'var(--t-header-bg)',
          borderBottom: '1px solid var(--t-header-border)',
        }}
      >
        <div className="t-display text-[24px] leading-tight">Welcoming Lily Wren</div>
      </div>
      {state.contractionActive ? (
        <ContractionTimerCard />
      ) : (
        <div
          className="mx-3 mt-3 flex items-center gap-2 rounded-xl px-3 py-2"
          style={{ backgroundColor: 'var(--t-soft-bg)' }}
        >
          <span
            className="h-2 w-2 flex-shrink-0 rounded-full animate-pulse"
            style={{ backgroundColor: 'var(--t-dot)' }}
          />
          <p className="text-[11px]" style={{ color: 'var(--t-soft-text)' }}>
            {state.status}
          </p>
        </div>
      )}
      <div className="px-3 py-3">
        <div
          style={{
            transform: state.scrollTour ? 'translateY(-45%)' : 'none',
            transition: state.scrollTour ? 'transform 3.2s ease-in-out' : 'none',
          }}
        >
          <Timeline events={state.events} slug="lily-demo" />
        </div>
      </div>
    </div>
  );
}

function HeroCopy() {
  return (
    <div className="flex flex-col items-center text-center max-w-md">
      <h1 className="mb-6">
        <span className="sr-only">Arrival Story</span>
        <WordmarkWriteOn className="w-[290px] sm:w-[430px] max-w-full text-white" />
      </h1>
      <div className="flex flex-col items-center motion-safe:animate-fade-up">
        <p className="text-2xl font-light text-white mb-3 leading-snug drop-shadow">
          The birth story your whole family lives together
        </p>
        <p className="text-base text-white/80 mb-10 max-w-sm drop-shadow">
          Set up in 2 minutes. Share a link. Everyone follows in real time.
        </p>
        <Link to="/setup" className="btn-primary text-base px-8 py-4 shadow-xl">
          Create your baby's page →
        </Link>
      </div>
    </div>
  );
}

export default function HeroVideo() {
  const sectionRef = useRef(null);
  const videoRef = useRef(null);
  const [visible, setVisible] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);

  const [reducedMotion] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );
  const [isDesktop, setIsDesktop] = useState(
    () => window.matchMedia('(min-width: 1024px)').matches,
  );

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)');
    const onChange = (e) => setIsDesktop(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => setVisible(entry.intersectionRatio >= 0.2),
      { threshold: [0, 0.2] },
    );
    observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  const useVideo = isDesktop && !reducedMotion && !videoFailed;
  const { state } = useHeroCueEngine({
    videoRef,
    clockMode: !useVideo,
    running: visible && !reducedMotion,
  });

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (visible) video.play().catch(() => {});
    else video.pause();
  }, [visible, useVideo]);

  const phoneState = reducedMotion ? finalHeroState(Date.now()) : state;

  return (
    <section
      ref={sectionRef}
      className="relative overflow-hidden bg-gray-950 min-h-[640px] lg:h-[85vh] lg:max-h-[860px]"
    >
      {/* Layer 1 — background video (desktop) / poster (mobile + reduced motion) */}
      {useVideo ? (
        <video
          ref={videoRef}
          className="absolute inset-0 h-full w-full object-cover"
          src={HERO_VIDEO_SRC}
          poster={HERO_POSTER_SRC}
          muted
          playsInline
          loop
          preload="metadata"
          onError={() => setVideoFailed(true)}
        />
      ) : (
        <img
          src={HERO_POSTER_SRC}
          alt=""
          aria-hidden="true"
          className="absolute inset-0 h-full w-full object-cover"
        />
      )}

      {/* Layer 2 — scrim: dark-to-transparent, tinted toward the brand
          fuchsia (plan §1) — keeps copy + phone legible over any footage */}
      <div
        className={`absolute inset-0 bg-gradient-to-r from-[#2a0a3d]/75 via-gray-950/30 to-gray-950/50 ${
          useVideo ? '' : 'bg-gray-950/55'
        }`}
      />
      <div className="absolute inset-0 bg-primary-800/10" />
      {/* Loop-seam cover: goes near-opaque as the video wraps and the UI resets */}
      <div
        className={`absolute inset-0 bg-gray-950 transition-opacity duration-700 ${
          state.seam && useVideo ? 'opacity-90' : 'opacity-0'
        }`}
      />

      {/* Layer 3 — content */}
      <div className="relative z-10 flex h-full min-h-[640px] flex-col items-center justify-center gap-10 px-6 py-14 lg:flex-row lg:gap-0 lg:py-0">
        {/* Phone — left on desktop (~150px inset), centered on mobile */}
        <div className="order-2 lg:order-1 lg:absolute lg:left-[150px] lg:top-1/2 lg:-translate-y-1/2">
          <PhoneFrame>
            <div aria-hidden="true" className="pointer-events-none absolute inset-0 select-none overflow-hidden">
              <HeroAppScreen state={phoneState} />
            </div>
          </PhoneFrame>
        </div>

        {/* Copy — center-right on desktop */}
        <div className="order-1 lg:order-2 flex w-full justify-center lg:ml-auto lg:w-[55%] lg:justify-center lg:pr-[6%]">
          <HeroCopy />
        </div>
      </div>
    </section>
  );
}
