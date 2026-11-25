import { useEffect, useState } from 'react';

// Types, holds ~2.2s, deletes, types the next phrase. Space for the longest phrase is reserved by hidden ghosts.
// Reduced motion: the first phrase stays, with no typing and no blink (blink is also gated in CSS).
export default function Typewriter({ phrases, typeMs = 65, deleteMs = 32, holdMs = 2200, pauseMs = 380, startDelayMs = 2400 }) {
  const [text, setText] = useState(phrases[0]);
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    let idx = 0, len = phrases[0].length, deleting = true, timer;
    const tick = () => {
      const phrase = phrases[idx];
      if (!deleting) {
        len += 1; setText(phrase.slice(0, len));
        if (len >= phrase.length) { deleting = true; timer = setTimeout(tick, holdMs); return; }
        timer = setTimeout(tick, typeMs); return;
      }
      len -= 1; setText(phrase.slice(0, len));
      if (len <= 0) { deleting = false; idx = (idx + 1) % phrases.length; timer = setTimeout(tick, pauseMs); return; }
      timer = setTimeout(tick, deleteMs);
    };
    timer = setTimeout(tick, startDelayMs);
    return () => clearTimeout(timer);
  }, [phrases, typeMs, deleteMs, holdMs, pauseMs, startDelayMs]);
  return (
    <span className="rot accent" aria-hidden="true">
      {phrases.map((p) => <span className="ghost" key={p}>{p}</span>)}
      <span className="tw">{text}</span>
    </span>
  );
}
