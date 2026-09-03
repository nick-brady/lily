import { useEffect, useState } from 'react';

// A media query as state, safe to render anywhere.
//
// The public pages are pre-rendered at build time, where there is no window
// to ask. So the first render — on the server, and on the client while it
// hydrates that server markup — uses `initial`, and the real answer arrives
// in an effect a frame later. Callers pick `initial` to be the branch that
// looks right for one frame: the poster rather than the video, say.
export default function useMediaQuery(query, initial = false) {
  const [matches, setMatches] = useState(initial);

  useEffect(() => {
    const mq = window.matchMedia(query);
    setMatches(mq.matches);
    const onChange = (e) => setMatches(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [query]);

  return matches;
}

export const REDUCED_MOTION = '(prefers-reduced-motion: reduce)';
