import { useState, type ReactNode } from "react";

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
  online,
}: {
  name: string;
  colorKey: string;
  size?: "sm" | "md" | "lg";
  /** Shows a presence dot when set. */
  online?: boolean;
}) {
  const sizes = { sm: "size-7 text-xs", md: "size-9 text-sm", lg: "size-12 text-lg" };
  const face = (
    <span
      aria-hidden="true"
      className={`grid shrink-0 place-items-center rounded-t-full rounded-b-lg font-display font-semibold ${sizes[size]} ${hue(colorKey)}`}
    >
      {name.trim().charAt(0).toUpperCase() || "?"}
    </span>
  );
  if (online === undefined) return face;
  return (
    <span className="relative shrink-0">
      {face}
      <PresenceDot online={online} className="absolute -right-0.5 -bottom-0.5" />
    </span>
  );
}

export function PresenceDot({ online, className = "" }: { online: boolean; className?: string }) {
  return (
    <span
      role="img"
      aria-label={online ? "Online" : "Offline"}
      className={`size-2.5 shrink-0 rounded-full ring-2 ring-bg-subtle ${
        online ? "bg-presence-online" : "bg-presence-offline"
      } ${className}`}
    />
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

/**
 * A destructive button that asks once more in place instead of opening a dialog: the first
 * click turns it into "Yes, <verb>" and "Keep".
 */
export function ConfirmButton({
  label,
  confirmLabel,
  onConfirm,
  busy = false,
  icon,
}: {
  label: string;
  confirmLabel: string;
  onConfirm: () => void;
  busy?: boolean;
  /** Shown instead of the label on the first button, which keeps the label as its name. */
  icon?: ReactNode;
}) {
  const [asking, setAsking] = useState(false);
  const quiet =
    "rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none disabled:opacity-60";
  if (!asking) {
    return (
      <button
        type="button"
        aria-label={icon ? label : undefined}
        title={icon ? label : undefined}
        className={
          icon
            ? "grid size-8 place-items-center rounded-md text-text-muted transition-colors hover:bg-danger-soft hover:text-danger focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
            : `${quiet} text-danger hover:bg-danger-soft`
        }
        onClick={() => {
          setAsking(true);
        }}
      >
        {icon ?? label}
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

/** "#" for public channels, a lock for private ones, a person or two for conversations;
 * labelled for screen readers. */
export function ChannelIcon({ kind }: { kind: "public" | "private" | "direct" | "group" }) {
  if (kind === "direct" || kind === "group") {
    return (
      <svg
        viewBox="0 0 16 16"
        className="size-3.5 shrink-0"
        role="img"
        aria-label={kind === "direct" ? "Direct message" : "Group"}
      >
        <circle cx="6" cy="5.5" r="2.5" fill="none" stroke="currentColor" strokeWidth="1.4" />
        <path
          d="M1.5 13.5c.6-2.4 2.4-3.6 4.5-3.6s3.9 1.2 4.5 3.6"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.4"
        />
        {kind === "group" && (
          <path
            d="M10.5 3.2a2.5 2.5 0 0 1 0 4.6M12 10.2c1.3.5 2.1 1.6 2.5 3.3"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
          />
        )}
      </svg>
    );
  }
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
