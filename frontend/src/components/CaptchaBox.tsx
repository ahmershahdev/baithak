import type { RefObject } from "react";

/** Where the reCAPTCHA checkbox appears when the API asks for it. Empty until then. */
export function CaptchaBox({
  box,
  challenged,
  solved,
}: {
  box: RefObject<HTMLDivElement | null>;
  challenged: boolean;
  solved: boolean;
}) {
  return (
    <div className={challenged ? "flex flex-col gap-2" : "hidden"}>
      {challenged && !solved && (
        <p className="text-sm text-text-muted">Tick the box below, then send the form again.</p>
      )}
      <div ref={box} />
    </div>
  );
}
