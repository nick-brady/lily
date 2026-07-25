import { useEffect, useState } from 'react';

/**
 * Page-level dark mode: user preference persisted in localStorage, seeded
 * from the OS preference, optionally forced on by an always-dark theme.
 * Owns the `dark` class on <html>, so exactly one mounted page should use
 * it at a time (it's a per-page concern, not app-wide state).
 */
export function useDarkMode(alwaysDark = false) {
  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window === 'undefined') return false;
    return (
      localStorage.getItem('darkMode') === 'true'
      || window.matchMedia('(prefers-color-scheme: dark)').matches
    );
  });

  const effectiveDark = darkMode || Boolean(alwaysDark);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', effectiveDark);
    localStorage.setItem('darkMode', darkMode);
  }, [darkMode, effectiveDark]);

  return { darkMode, setDarkMode, effectiveDark };
}
