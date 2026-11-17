// Shapes match frontend/scripts/make-brand.py; change both together.
const ARCH =
  "M30 196V100C30 62 58 44 82 30C92 24 98 16 100 6C102 16 108 24 118 30C142 44 170 62 170 100V196Z";
const LEFT_PERSON = "M42 168V140C42 123 53 116 65 116C77 116 88 123 88 140V168Z";
const RIGHT_PERSON = "M112 168V140C112 123 123 116 135 116C147 116 158 123 158 140V168Z";
const FLAME = "M100 132C106 140 107 146 100 152C93 146 94 140 100 132Z";
const BOWL = "M89 156H111C111 163 106 167 100 167C94 167 89 163 89 156Z";

export function Mark({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 200 200" className={className} aria-hidden="true">
      <path d={ARCH} className="fill-accent" />
      <g fill="#fbf8f2">
        <circle cx="68" cy="99" r="13" />
        <circle cx="132" cy="99" r="13" />
        <path d={LEFT_PERSON} />
        <path d={RIGHT_PERSON} />
      </g>
      <g fill="#e3b12c">
        <path d={FLAME} />
        <path d={BOWL} />
        <rect x="36" y="171" width="128" height="14" rx="7" />
      </g>
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <Mark className="size-8" />
      <span className="wonky font-display text-2xl font-semibold tracking-tight">baithak</span>
    </span>
  );
}

// Delays are whole class names so Tailwind finds them, and no inline style is needed (CSP).
const SAYINGS = [
  { text: "Chai at four?", delay: "[animation-delay:0s]" },
  { text: "PR #42 is merged", delay: "[animation-delay:3s]" },
  { text: "Standup moved to ten", delay: "[animation-delay:6s]" },
];

export function Scene() {
  return (
    <div className="relative mx-auto w-full max-w-[22rem]">
      <div className="absolute inset-x-0 top-0 h-12" aria-hidden="true">
        {SAYINGS.map(({ text, delay }) => (
          <p
            key={text}
            className={`bubble-say absolute top-0 left-1/2 -translate-x-1/2 rounded-2xl rounded-bl-sm bg-surface-raised px-3.5 py-2 text-sm font-medium whitespace-nowrap text-text shadow-md ${delay}`}
          >
            {text}
          </p>
        ))}
      </div>
      <svg viewBox="0 0 200 200" className="mt-20 w-full" aria-hidden="true">
        <defs>
          <radialGradient id="diya-glow">
            <stop offset="0" stopColor="#ffd98a" stopOpacity="0.9" />
            <stop offset="1" stopColor="#ffd98a" stopOpacity="0" />
          </radialGradient>
        </defs>
        <g className="arch-rise">
          <path d={ARCH} className="fill-accent" />
          <circle cx="100" cy="146" r="30" fill="url(#diya-glow)" className="diya-glow" />
        </g>
        <g fill="#fbf8f2">
          <g className="sit-down [animation-delay:500ms]">
            <circle cx="68" cy="99" r="13" />
            <path d={LEFT_PERSON} />
          </g>
          <g className="sit-down [animation-delay:700ms]">
            <circle cx="132" cy="99" r="13" />
            <path d={RIGHT_PERSON} />
          </g>
        </g>
        <g fill="#e3b12c">
          <path d={FLAME} className="diya-flame" />
          <path d={BOWL} />
          <rect x="36" y="171" width="128" height="14" rx="7" />
        </g>
      </svg>
    </div>
  );
}

export function Jaali() {
  return (
    <svg className="absolute inset-0 size-full text-border opacity-50" aria-hidden="true">
      <defs>
        <pattern id="jaali" width="56" height="56" patternUnits="userSpaceOnUse">
          <path
            d="M28 6l6.4 15.6L50 28l-15.6 6.4L28 50l-6.4-15.6L6 28l15.6-6.4zM0 0l8 8M56 0l-8 8M0 56l8-8M56 56l-8-8"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.2"
          />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#jaali)" />
    </svg>
  );
}
