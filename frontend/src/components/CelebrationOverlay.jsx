import { useEffect } from 'react';
import useDialog from '../hooks/useDialog';

const EMOJI = ['🤍', '💛', '🎉', '👶', '✨', '🩷', '🎈'];

// Deterministic per-index placement — no Math.random so renders are stable.
const PIECES = Array.from({ length: 28 }, (_, i) => ({
  emoji: EMOJI[i % EMOJI.length],
  left: (i * 37) % 100,
  delay: (i % 9) * 0.32,
  duration: 4.5 + ((i * 13) % 30) / 10,
  size: 1.4 + ((i * 7) % 16) / 10,
  rot: ((i * 53) % 80) - 40,
}));

/**
 * Full-screen celebratory burst for the Baby Born! moment. Plays once,
 * auto-dismisses, and is tap-to-dismiss. Purely decorative — pointer
 * events pass through except on the dismiss layer.
 *
 * @param {{ childName?: string, onDone: () => void }} props
 */
export default function CelebrationOverlay({ childName, onDone }) {
  useEffect(() => {
    const t = setTimeout(onDone, 7000);
    return () => clearTimeout(t);
  }, [onDone]);

  const panelRef = useDialog(onDone, { label: childName ? `${childName} is here!` : 'Baby is here!' });

  return (
    <div
      ref={panelRef}
      className="fixed inset-0 z-50 overflow-hidden flex items-center justify-center outline-none"
      onClick={onDone}
      style={{ backgroundColor: 'rgba(0,0,0,0.18)' }}
    >
      {PIECES.map((p, i) => (
        <span
          key={i}
          className="absolute bottom-0 animate-float-up select-none"
          style={{
            left: `${p.left}%`,
            fontSize: `${p.size}rem`,
            animationDelay: `${p.delay}s`,
            '--float-dur': `${p.duration}s`,
            '--float-rot': `${p.rot}deg`,
          }}
        >
          {p.emoji}
        </span>
      ))}

      <div
        className="animate-celebrate-pop relative text-center px-8 py-6 rounded-3xl shadow-2xl"
        style={{ backgroundColor: 'var(--t-card-bg)', border: '1px solid var(--t-card-border)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-5xl mb-2">👶</div>
        <div className="t-display" style={{ fontSize: '2rem', lineHeight: 1.1 }}>
          {childName ? `${childName} is here!` : 'Baby is here!'}
        </div>
        <p className="text-sm t-muted mt-2">Welcome to the world 🤍</p>
      </div>
    </div>
  );
}
