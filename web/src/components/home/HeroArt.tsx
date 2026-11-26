/** Three hatched database discs joined by a key line, drawn as line art. */
export function HeroArt() {
  const discs = [210, 130, 50]
  return (
    <svg viewBox="0 0 320 320" className="h-full w-full text-brand-600 dark:text-brand-300" aria-hidden="true">
      <defs>
        <pattern id="hero-hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(-38)">
          <line x1="0" y1="0" x2="0" y2="5" stroke="currentColor" strokeWidth="1.3" />
        </pattern>
      </defs>
      {discs.map((y) => (
        <g key={y} fill="none" stroke="currentColor" strokeWidth="1.4">
          <path d={`M40 ${y} v54 a120 34 0 0 0 240 0 v-54`} fill="url(#hero-hatch)" />
          <ellipse cx="160" cy={y} rx="120" ry="34" className="fill-brand-50 dark:fill-slate-900" />
          <ellipse cx="160" cy={y} rx="92" ry="25" strokeWidth="1" />
          <ellipse cx="160" cy={y} rx="62" ry="16.5" strokeWidth="1" />
          <ellipse cx="160" cy={y} rx="30" ry="8" strokeWidth="1" />
        </g>
      ))}
      <g stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
        <path d="M252 58 C 300 70, 300 128, 252 140" fill="none" strokeDasharray="2 5" />
        <path d="M68 138 C 20 150, 20 208, 68 220" fill="none" strokeDasharray="2 5" />
      </g>
      {[
        [252, 58],
        [252, 140],
        [68, 138],
        [68, 220],
      ].map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="4.5" className="fill-brand-300 dark:fill-brand-600" stroke="currentColor" strokeWidth="1.4" />
      ))}
    </svg>
  )
}
