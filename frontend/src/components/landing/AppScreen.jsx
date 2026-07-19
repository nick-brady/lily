import Timeline from '../Timeline';

// The Arrival Story screen inside landing demo phones: real product
// components fed by scripted fixture data, framed by a miniature of the
// public birth page chrome. The header stays pinned; `scrollRef` exposes the
// content viewport so a slide can drive a programmatic scroll (the keepsake
// slide's look-back). overflow-hidden still honors scrollTop, so visitors
// can't grab the demo but the animation can move it.
export default function AppScreen({ events, banner, bannerPulse = true, scrollRef }) {
  return (
    <div
      className="demo-phone flex h-full flex-col overflow-hidden"
      style={{ backgroundColor: 'var(--t-page-bg)' }}
    >
      <div
        className="px-4 pt-10 pb-3 text-center"
        style={{
          backgroundColor: 'var(--t-header-bg)',
          borderBottom: '1px solid var(--t-header-border)',
        }}
      >
        <div className="t-display text-[24px] leading-tight">Welcoming Lily Wren</div>
      </div>
      <div ref={scrollRef} className="flex-1 overflow-hidden">
        <div
          className="mx-3 mt-3 flex items-center gap-2 rounded-xl px-3 py-2"
          style={{ backgroundColor: 'var(--t-soft-bg)' }}
        >
          <span
            className={`h-2 w-2 flex-shrink-0 rounded-full ${bannerPulse ? 'animate-pulse' : ''}`}
            style={{ backgroundColor: 'var(--t-dot)' }}
          />
          <p className="text-[11px]" style={{ color: 'var(--t-soft-text)' }}>
            {banner}
          </p>
        </div>
        <div className="px-3 py-3">
          <Timeline events={events} slug="lily-demo" isUnlocked />
        </div>
      </div>
    </div>
  );
}
