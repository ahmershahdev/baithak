import type { RefObject } from "react";

// The widget is a fixed 304 x 78 px iframe, hence the scale-down on narrow phones.
export function CaptchaBox({
  box,
  challenged,
  solved,
  failed,
}: {
  box: RefObject<HTMLDivElement | null>;
  challenged: boolean;
  solved: boolean;
  failed: boolean;
}) {
  return (
    <div
      className={
        challenged
          ? "settle flex flex-col items-center gap-3 rounded-xl border border-border bg-surface px-3 py-4"
          : "hidden"
      }
    >
      <p className="text-center text-sm text-text-muted" aria-live="polite">
        {failed
          ? "The check could not load. Check your connection and try again."
          : solved
            ? "Thanks. Now send the form again."
            : "One quick check: tick the box, then send the form again."}
      </p>
      <div className="flex min-h-[78px] w-full justify-center overflow-hidden">
        <div ref={box} className="origin-top max-[360px]:scale-[0.88]" />
      </div>
    </div>
  );
}

/**
 * Google allows hiding the floating v3 badge only if this notice is on the page instead
 * (reCAPTCHA FAQ). The badge itself is hidden in index.css.
 */
export function CaptchaNotice() {
  return (
    <p className="text-xs leading-relaxed text-text-subtle">
      Protected by reCAPTCHA. Google&rsquo;s{" "}
      <a
        className="underline underline-offset-2 hover:text-text"
        href="https://policies.google.com/privacy"
        target="_blank"
        rel="noreferrer"
      >
        Privacy Policy
      </a>{" "}
      and{" "}
      <a
        className="underline underline-offset-2 hover:text-text"
        href="https://policies.google.com/terms"
        target="_blank"
        rel="noreferrer"
      >
        Terms of Service
      </a>{" "}
      apply.
    </p>
  );
}
