import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

/**
 * A small kebab (⋮) overflow menu for page headers. Mirrors
 * ThemePickerSheet's overlay/click-outside mechanics: a full-screen
 * transparent backdrop catches outside clicks, Escape closes it.
 *
 * @param {{ items: Array<{ label: string, to: string }> }} props
 */
export default function HeaderMenu({ items }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        title="Menu"
        className="p-2 rounded-lg transition-opacity hover:opacity-80"
        style={{ backgroundColor: 'var(--t-soft-bg)', color: 'var(--t-soft-text)' }}
      >
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
          <circle cx="12" cy="5" r="2" />
          <circle cx="12" cy="12" r="2" />
          <circle cx="12" cy="19" r="2" />
        </svg>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-20" onClick={() => setOpen(false)} />
          <div
            role="menu"
            className="absolute right-0 mt-2 z-30 overflow-hidden rounded-xl shadow-lg"
            style={{
              minWidth: '10rem',
              backgroundColor: 'var(--t-card-bg)',
              border: '1px solid var(--t-card-border)',
            }}
          >
            {items.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                role="menuitem"
                onClick={() => setOpen(false)}
                className="block px-4 py-2.5 text-sm transition-colors hover:opacity-80"
                style={{ color: 'var(--t-ink)' }}
              >
                {item.label}
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
