import { useEffect, useRef } from 'react';

// What a dialog owes a keyboard or screen-reader user, in one place.
//
// The app has a dozen overlays — confirmations, bottom sheets, the gift
// editor, the lightbox — and until this every one of them was a dimmed
// <div> with an onClick: no dialog role, focus left on the page behind,
// nothing on Escape, Tab wandering off into the hidden page. This hook
// gives a panel all of it:
//
//   - role="dialog" and aria-modal, named by its first heading (or `label`)
//   - focus moves in when it opens and back to where it was when it closes
//   - Escape closes it (unless a nested dialog is open inside it)
//   - Tab and Shift+Tab stay inside
//   - the page behind stops scrolling
//
// Attach the returned ref to the panel element. The role and name are set on
// the DOM rather than in JSX so a sheet needs one line, not five.

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), ' +
  'textarea:not([disabled]), [tabindex]:not([tabindex="-1"]), audio[controls], video[controls]';

let dialogSerial = 0;

export default function useDialog(onClose, { label } = {}) {
  const ref = useRef(null);
  // the latest close handler, without re-running the effect (and re-stealing
  // focus) every time a parent re-renders with a fresh arrow function
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const labelRef = useRef(label);
  labelRef.current = label;

  useEffect(() => {
    const panel = ref.current;
    if (!panel) return undefined;

    const previous = document.activeElement;
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    if (!panel.hasAttribute('aria-label') && !panel.hasAttribute('aria-labelledby')) {
      const heading = panel.querySelector('h1, h2, h3');
      if (heading) {
        if (!heading.id) heading.id = `dialog-title-${(dialogSerial += 1)}`;
        panel.setAttribute('aria-labelledby', heading.id);
      } else if (labelRef.current) {
        panel.setAttribute('aria-label', labelRef.current);
      }
    }
    if (!panel.hasAttribute('tabindex')) panel.setAttribute('tabindex', '-1');

    const focusables = () =>
      [...panel.querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent !== null);

    (focusables()[0] || panel).focus({ preventScroll: true });

    const bodyOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const onKey = (e) => {
      if (e.key === 'Escape') {
        // a dialog inside this one owns Escape while it is open
        if (panel.querySelector('[role="dialog"]')) return;
        e.stopPropagation();
        closeRef.current?.();
        return;
      }
      if (e.key !== 'Tab') return;
      const list = focusables();
      if (list.length === 0) {
        e.preventDefault();
        panel.focus();
        return;
      }
      const first = list[0];
      const last = list[list.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || active === panel || !panel.contains(active))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (active === last || !panel.contains(active))) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey);

    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = bodyOverflow;
      if (previous && typeof previous.focus === 'function' && document.contains(previous)) {
        previous.focus({ preventScroll: true });
      }
    };
  }, []);

  return ref;
}
