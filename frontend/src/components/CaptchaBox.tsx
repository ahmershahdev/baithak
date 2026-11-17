import type { RefObject } from "react";

// The widget is a fixed 304 x 78 px iframe, hence the scale-down on narrow phones.
export function CaptchaBox({
  box,
  shown,
  challenged,
  solved,
  failed,
}: {
  box: RefObject<HTMLDivElement | null>;
  shown: boolean;
  challenged: boolean;
  solved: boolean;
  failed: boolean;
}) {
  const note = failed
    ? "The check could not load. Check your connection and try again."
    : challenged && !solved
      ? "Please tick the box, then send the form again."
      : null;
  return (
    <div
      className={
        shown
          ? "flex flex-col items-center gap-2 rounded-xl border border-border bg-surface px-3 py-3"
          : "hidden"
      }
    >
      {note && (
        <p className="text-center text-sm text-danger" role="status">
          {note}
        </p>
      )}
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
