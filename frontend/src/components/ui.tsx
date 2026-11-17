import { useId, type ComponentProps, type ReactNode } from "react";

export function AuthCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-6 px-4 py-12">
      <p className="text-lg font-semibold tracking-tight text-accent-text">Baithak</p>
      <div className="rounded-lg border border-border bg-surface p-6 shadow-sm">
        <h1 className="mb-5 text-xl font-semibold">{title}</h1>
        {children}
      </div>
    </main>
  );
}

interface FieldProps extends ComponentProps<"input"> {
  label: string;
  hint?: string;
  errors?: string[] | undefined;
}

export function Field({ label, hint, errors, ...input }: FieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const invalid = errors !== undefined && errors.length > 0;
  const describedBy = [hint ? hintId : null, invalid ? errorId : null].filter(Boolean).join(" ");
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy || undefined}
        className="rounded-md border border-border-strong bg-bg px-3 py-2 outline-none focus-visible:ring-2 focus-visible:ring-focus-ring aria-invalid:border-danger"
        {...input}
      />
      {hint && (
        <p id={hintId} className="text-sm text-text-subtle">
          {hint}
        </p>
      )}
      {invalid && (
        <p id={errorId} className="text-sm text-danger">
          {errors.join(" ")}
        </p>
      )}
    </div>
  );
}

export function Button({ className = "", ...props }: ComponentProps<"button">) {
  return (
    <button
      className={`rounded-md bg-accent px-4 py-2 font-medium text-on-accent hover:bg-accent-hover focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2 focus-visible:ring-offset-surface focus-visible:outline-none disabled:opacity-60 ${className}`}
      {...props}
    />
  );
}

export function QuietButton({ className = "", ...props }: ComponentProps<"button">) {
  return (
    <button
      className={`rounded-md border border-border-strong px-4 py-2 font-medium hover:bg-bg-subtle focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none disabled:opacity-60 ${className}`}
      {...props}
    />
  );
}

export function ErrorMessage({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-text">
      {children}
    </p>
  );
}

export function Notice({ children }: { children: ReactNode }) {
  return (
    <p
      role="status"
      className="rounded-md bg-success-soft px-3 py-2 text-sm text-success-soft-text"
    >
      {children}
    </p>
  );
}
