import { useState, type ComponentProps, type ReactNode } from "react";

import { ROLE_LABELS, type Role } from "../roles";

// The six brand hues (docs/design.md), picked from a hash so a workspace or person keeps
// their color everywhere.
const HUES = [
  "bg-accent-soft text-accent-soft-text",
  "bg-ember-soft text-ember-soft-text",
  "bg-warning-soft text-warning-soft-text",
  "bg-success-soft text-success-soft-text",
  "bg-danger-soft text-danger-soft-text",
  "bg-info-soft text-info-soft-text",
] as const;

function hue(key: string): string {
  let hash = 0;
  for (const char of key) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return HUES[hash % HUES.length] ?? HUES[0];
}

export function Avatar({
  name,
  colorKey,
  size = "md",
}: {
  name: string;
  colorKey: string;
  size?: "sm" | "md" | "lg";
}) {
  const sizes = { sm: "size-7 text-xs", md: "size-9 text-sm", lg: "size-12 text-lg" };
  return (
    <span
      aria-hidden="true"
      className={`grid shrink-0 place-items-center rounded-t-full rounded-b-lg font-display font-semibold ${sizes[size]} ${hue(colorKey)}`}
    >
      {name.trim().charAt(0).toUpperCase() || "?"}
    </span>
  );
}

export function RoleBadge({ role }: { role: Role }) {
  const tone =
    role === "owner"
      ? "bg-accent-soft text-accent-soft-text"
      : role === "admin"
        ? "bg-info-soft text-info-soft-text"
        : role === "guest"
          ? "bg-surface-sunken text-text-muted"
          : "bg-success-soft text-success-soft-text";
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${tone}`}>
      {ROLE_LABELS[role]}
    </span>
  );
}

export function PageHeader({
  title,
  intro,
  action,
}: {
  title: string;
  intro?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <header className="settle flex flex-wrap items-end justify-between gap-4 border-b border-border pb-6">
      <div>
        <h1 className="wonky font-display text-3xl font-semibold tracking-tight sm:text-4xl">
          {title}
        </h1>
        {intro && <p className="mt-2 max-w-prose text-text-muted">{intro}</p>}
      </div>
      {action}
    </header>
  );
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-border bg-surface shadow-sm ${className}`}>
      {children}
    </section>
  );
}

export function Select({ className = "", ...props }: ComponentProps<"select">) {
  return (
    <select
      className={`h-10 rounded-lg border border-border-strong bg-bg px-3 text-sm font-medium outline-none focus-visible:border-focus-ring focus-visible:ring-4 focus-visible:ring-focus-ring/20 disabled:opacity-60 ${className}`}
      {...props}
    />
  );
}

/**
 * A destructive button that asks once more in place instead of opening a dialog: the first
 * click turns it into "Yes, <verb>" and "Keep".
 */
export function ConfirmButton({
  label,
  confirmLabel,
  onConfirm,
  busy = false,
}: {
  label: string;
  confirmLabel: string;
  onConfirm: () => void;
  busy?: boolean;
}) {
  const [asking, setAsking] = useState(false);
  const quiet =
    "rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none disabled:opacity-60";
  if (!asking) {
    return (
      <button
        type="button"
        className={`${quiet} text-danger hover:bg-danger-soft`}
        onClick={() => {
          setAsking(true);
        }}
      >
        {label}
      </button>
    );
  }
  return (
    <span className="settle flex items-center gap-1">
      <button
        type="button"
        disabled={busy}
        className={`${quiet} bg-danger-fill text-on-danger hover:opacity-90`}
        onClick={onConfirm}
      >
        {confirmLabel}
      </button>
      <button
        type="button"
        className={`${quiet} text-text-muted hover:bg-bg-subtle`}
        onClick={() => {
          setAsking(false);
        }}
      >
        Keep
      </button>
    </span>
  );
}

const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31_536_000],
  ["month", 2_592_000],
  ["week", 604_800],
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
];

export function When({ iso }: { iso: string }) {
  // Read once when shown; lists are refetched often enough that "3 minutes ago" stays honest.
  const [now] = useState(() => Date.now());
  const date = new Date(iso);
  const seconds = Math.round((date.getTime() - now) / 1000);
  const step = STEPS.find(([, size]) => Math.abs(seconds) >= size);
  const text = step ? relative.format(Math.round(seconds / step[1]), step[0]) : "now";
  return (
    <time dateTime={iso} title={date.toLocaleString("en")}>
      {text}
    </time>
  );
}

/** "#" for public channels, a lock for private ones; labelled for screen readers. */
export function ChannelIcon({ kind }: { kind: "public" | "private" }) {
  if (kind === "public") {
    return (
      <span aria-hidden="true" className="w-3.5 shrink-0 text-center text-text-subtle">
        #
      </span>
    );
  }
  return (
    <svg viewBox="0 0 16 16" className="size-3.5 shrink-0" role="img" aria-label="Private">
      <path
        d="M4.5 7V5.2a3.5 3.5 0 0 1 7 0V7M3.5 7h9v6.5h-9z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}
