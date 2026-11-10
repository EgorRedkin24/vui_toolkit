interface FoxProps {
  className?: string;
}

/**
 * Минималистичный лис — маскот SiFox.
 * Плоская геометричная голова лиса, цвета берутся из дизайн-токенов,
 * поэтому талисман корректно смотрится в светлой и тёмной темах.
 */
export function Fox({ className }: FoxProps) {
  return (
    <svg viewBox="0 0 200 200" className={className} aria-hidden="true" focusable="false" style={{ overflow: "visible" }}>
      <g className="fox-idle">
        {/* голова */}
        <path
          d="M26 82 L100 62 L174 82 L100 174 Z"
          fill="var(--foreground)"
          stroke="var(--foreground)"
          strokeWidth="10"
          strokeLinejoin="round"
        />
        {/* уши */}
        <path d="M38 22 L86 64 L30 90 Z" fill="var(--foreground)" stroke="var(--foreground)" strokeWidth="8" strokeLinejoin="round" />
        <path d="M162 22 L114 64 L170 90 Z" fill="var(--foreground)" stroke="var(--foreground)" strokeWidth="8" strokeLinejoin="round" />
        {/* внутренние уши — фирменный акцент */}
        <path d="M50 42 L74 63 L46 79 Z" fill="var(--primary)" />
        <path d="M150 42 L126 63 L154 79 Z" fill="var(--primary)" />
        {/* глаза */}
        <g className="fox-blink">
          <circle cx="72" cy="98" r="5.5" fill="var(--background)" />
          <circle cx="128" cy="98" r="5.5" fill="var(--background)" />
        </g>
        {/* нос */}
        <path d="M92 150 L108 150 L100 164 Z" fill="var(--primary)" stroke="var(--primary)" strokeWidth="4" strokeLinejoin="round" />
      </g>
    </svg>
  );
}
