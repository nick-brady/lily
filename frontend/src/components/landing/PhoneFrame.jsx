import { useEffect, useState } from 'react';

// Reusable device frame for demo phone renders (landing sections, hero
// video). Children fill the screen; position layers absolutely inside for
// cross-fades.
//
// The screen is empty until the component has mounted. The demo timelines
// are built from Date.now() and the visitor's locale, so what the build
// machine would render could never match what the browser renders; the
// frame itself pre-renders at its full size so nothing moves when the
// screen fills in.
//
// The screen interior is 280px wide — too narrow for the product's real
// typography. Children render on a true-device-width (375px) surface scaled
// down to fit, so text wraps exactly like it does on an actual phone.
const SCREEN_W = 280;
const SCREEN_H = 600;
const DESIGN_W = 375;
const SCALE = SCREEN_W / DESIGN_W;

export default function PhoneFrame({ children, className = '' }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return (
    <div
      className={`relative w-[300px] rounded-[2.75rem] bg-gray-900 dark:bg-gray-700 p-[10px] shadow-2xl ${className}`}
    >
      <div className="relative h-[600px] overflow-hidden rounded-[2.15rem] bg-white dark:bg-gray-900">
        <div className="absolute top-2.5 left-1/2 -translate-x-1/2 h-[22px] w-[92px] rounded-full bg-gray-900 z-20" />
        <div
          style={{
            width: `${DESIGN_W}px`,
            height: `${Math.round(SCREEN_H / SCALE)}px`,
            transform: `scale(${SCALE})`,
            transformOrigin: 'top left',
          }}
        >
          {mounted ? children : null}
        </div>
      </div>
    </div>
  );
}
