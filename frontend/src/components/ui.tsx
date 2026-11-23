import { useId, type ComponentProps, type ReactNode } from "react";
import { Link } from "react-router";

import { SITE_URL, SUPPORT_EMAIL } from "../contact";
import { Breadcrumbs, type Crumb } from "./Breadcrumbs";
import { Jaali, Scene, Wordmark } from "./brand";

export function AuthLayout({
  title,
  intro,
  trail,
  children,
}: {
  title: string;
  intro?: ReactNode;
  trail?: Crumb[];
  children: ReactNode;
}) {
  return (
    <div className="grid min-h-dvh bg-bg lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      <aside className="relative hidden overflow-hidden border-r border-border bg-bg-subtle lg:flex lg:flex-col lg:justify-between lg:p-12">
        <Jaali />
        <Link
          to="/"
          className="relative self-start rounded-md focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
        >
          <Wordmark />
          <span className="sr-only">Baithak home</span>
        </Link>
        <div className="relative">
          <Scene />
        </div>
        <div className="relative max-w-md">
          <p className="wonky font-display text-5xl leading-[1.05] font-semibold tracking-tight text-balance">
            Pull up a cushion.
          </p>
          <p className="mt-4 text-lg text-text-muted">
            Your team&rsquo;s conversations and its work, in one warm room.
          </p>
        </div>
      </aside>
      <main className="flex flex-col px-5 py-8 sm:px-10 lg:justify-center lg:px-16">
        <Link to="/" className="mb-12 self-start lg:hidden">
          <Wordmark />
          <span className="sr-only">Baithak home</span>
        </Link>
        <div className="settle mx-auto w-full max-w-[25rem]">
          {trail && (
            <div className="mb-6">
              <Breadcrumbs trail={trail} />
            </div>
          )}
          <h1 className="wonky font-display text-4xl font-semibold tracking-tight">{title}</h1>
          {intro && <p className="mt-2 text-text-muted">{intro}</p>}
          <div className="mt-8">{children}</div>
          <footer className="mt-12 flex flex-wrap gap-x-4 gap-y-1 border-t border-border pt-5 text-sm text-text-subtle">
            <Link to="/contact" className="hover:text-text">
              Contact
            </Link>
            <Link to="/privacy" className="hover:text-text">
              Privacy
            </Link>
            <a href={`mailto:${SUPPORT_EMAIL}`} className="hover:text-text">
              {SUPPORT_EMAIL}
            </a>
            <a href={SITE_URL} target="_blank" rel="noreferrer" className="hover:text-text">
              ahmershah.dev
            </a>
          </footer>
        </div>
      </main>
    </div>
  );
}

interface FieldProps extends ComponentProps<"input"> {
  label: string;
  hint?: string;
  errors?: string[] | undefined;
  /** Something inside the field on the right, such as the show-password button. */
  trailing?: ReactNode;
  /** Something under the field, such as the strength meter. */
  below?: ReactNode;
}

export const inputClass =
  "h-12 w-full rounded-xl border border-border-strong bg-bg px-4 text-base outline-none transition-[border-color,box-shadow] duration-200 placeholder:text-text-subtle hover:border-text-subtle focus-visible:border-focus-ring focus-visible:ring-4 focus-visible:ring-focus-ring/20 aria-invalid:border-danger";

export function Field({
  label,
  hint,
  errors,
  trailing,
  below,
  className = "",
  ...input
}: FieldProps) {
  const generated = useId();
  const id = input.id ?? generated;
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const invalid = errors !== undefined && errors.length > 0;
  const describedBy = [hint ? hintId : null, invalid ? errorId : null].filter(Boolean).join(" ");
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-sm font-semibold">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy || undefined}
          className={`${inputClass} ${trailing ? "pr-14" : ""} ${className}`}
          {...input}
        />
        {trailing && (
          <div className="absolute inset-y-0 right-1.5 flex items-center">{trailing}</div>
        )}
      </div>
      {below}
      {hint && (
        <p id={hintId} className="text-sm text-text-subtle">
          {hint}
        </p>
      )}
      {invalid && (
        <p id={errorId} className="text-sm font-medium text-danger">
          {errors.join(" ")}
        </p>
      )}
    </div>
  );
}

function Arrow() {
  return (
    <svg viewBox="0 0 20 20" className="btn-arrow size-5" aria-hidden="true">
      <path
        d="M4 10h11m-4.5-4.5L15 10l-4.5 4.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

interface ButtonProps extends ComponentProps<"button"> {
  /** While true the button shows three people taking turns and announces `busyLabel`. */
  busy?: boolean;
  busyLabel?: string;
}

export function Button({
  busy = false,
  busyLabel,
  children,
  className = "",
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={`btn-lamp inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-accent px-5 font-semibold text-on-accent hover:bg-accent-hover focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-70 ${className}`}
      disabled={busy || disabled}
      aria-busy={busy || undefined}
      {...props}
    >
      {busy ? (
        <>
          <span className="take-turns flex items-end gap-1.5" aria-hidden="true">
            <span className="size-2 rounded-full bg-on-accent" />
            <span className="size-2 rounded-full bg-on-accent" />
            <span className="size-2 rounded-full bg-on-accent" />
          </span>
          <span className="sr-only">{busyLabel ?? "Working"}</span>
        </>
      ) : (
        <>
          {children}
          <Arrow />
        </>
      )}
    </button>
  );
}

export function QuietButton({ className = "", ...props }: ComponentProps<"button">) {
  return (
    <button
      className={`rounded-xl border border-border-strong px-4 py-2 font-semibold transition-colors hover:bg-bg-subtle focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none disabled:opacity-60 ${className}`}
      {...props}
    />
  );
}

export function TextLink({ className = "", ...props }: ComponentProps<typeof Link>) {
  return (
    <Link
      className={`font-semibold text-accent-text underline decoration-accent-text/30 decoration-2 underline-offset-4 transition-colors hover:decoration-accent-text focus-visible:rounded-sm focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none ${className}`}
      {...props}
    />
  );
}

export function ErrorMessage({ children }: { children: ReactNode }) {
  return (
    <p
      role="alert"
      className="settle rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger-soft-text"
    >
      {children}
    </p>
  );
}

export function Notice({ children }: { children: ReactNode }) {
  return (
    <p role="status" className="settle rounded-xl bg-success-soft px-4 py-3 text-success-soft-text">
      {children}
    </p>
  );
}

/**
 * A field people never see and bots fill in. Kept off screen rather than display:none, which
 * some bots skip, and out of the tab order and the accessibility tree.
 */
export function Honeypot() {
  return (
    <div aria-hidden="true" className="absolute -left-[10000px] size-px overflow-hidden">
      <label>
        Website
        <input type="text" name="website" tabIndex={-1} autoComplete="off" defaultValue="" />
      </label>
    </div>
  );
}
