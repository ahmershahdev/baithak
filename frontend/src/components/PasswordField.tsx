import { useEffect, useId, useState, type ComponentProps } from "react";

import { measure, type Strength } from "../strength";
import { Field } from "./ui";

function PardaToggle({
  shown,
  controls,
  onToggle,
}: {
  shown: boolean;
  controls: string;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-controls={controls}
      aria-label={shown ? "Hide password" : "Show password"}
      data-shown={shown}
      className="grid size-10 place-items-center rounded-lg text-text-muted transition-colors hover:bg-bg-subtle hover:text-text focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
    >
      <svg viewBox="0 0 24 24" className="size-6" aria-hidden="true">
        <defs>
          <clipPath id={`${controls}-window`}>
            <path d="M4 21V11.5C4 7.5 7.5 5.4 12 3C16.5 5.4 20 7.5 20 11.5V21Z" />
          </clipPath>
        </defs>
        <g clipPath={`url(#${controls}-window)`}>
          <path
            d="M5.5 14C7.4 11.4 9.6 10.2 12 10.2S16.6 11.4 18.5 14C16.6 16.6 14.4 17.8 12 17.8S7.4 16.6 5.5 14Z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          />
          <circle className="parda-pupil" cx="12" cy="14" r="2.1" fill="currentColor" />
          <path className="parda-curtain parda-left fill-accent" d="M4 2H12.2V22H4Z" />
          <path className="parda-curtain parda-right fill-accent" d="M11.8 2H20V22H11.8Z" />
        </g>
        <path
          d="M4 21V11.5C4 7.5 7.5 5.4 12 3C16.5 5.4 20 7.5 20 11.5V21Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <g className="parda-tieback" fill="#e3b12c">
          <circle cx="5.2" cy="14" r="1.1" />
          <circle cx="18.8" cy="14" r="1.1" />
        </g>
      </svg>
    </button>
  );
}

const LEVELS = [
  { label: "Too easy to guess", fill: "bg-danger", segments: 1 },
  { label: "Weak", fill: "bg-danger", segments: 1 },
  { label: "Fair", fill: "bg-warning", segments: 2 },
  { label: "Good", fill: "bg-success", segments: 3 },
  { label: "Strong", fill: "bg-success", segments: 4 },
] as const;

const SEGMENTS = ["scale-x-0", "scale-x-100"] as const;

function StrengthMeter({ password, related }: { password: string; related: string[] }) {
  const [strength, setStrength] = useState<Strength | null>(null);
  const relatedKey = related.join("\u0000");

  useEffect(() => {
    if (!password) return;
    let current = true;
    const timer = window.setTimeout(() => {
      void measure(password, relatedKey.split("\u0000")).then((result) => {
        if (current) setStrength(result);
      });
    }, 120);
    return () => {
      current = false;
      window.clearTimeout(timer);
    };
  }, [password, relatedKey]);

  // An empty field shows nothing, even if an older score is still in state.
  const shown = password ? strength : null;
  const level = shown ? LEVELS[shown.score] : null;
  const advice = shown?.warning ?? shown?.suggestion;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="grid grid-cols-4 gap-1.5" aria-hidden="true">
        {[1, 2, 3, 4].map((segment) => (
          <span key={segment} className="h-1.5 overflow-hidden rounded-full bg-surface-sunken">
            <span
              className={`meter-fill block h-full rounded-full ${level?.fill ?? "bg-transparent"} ${
                SEGMENTS[level && segment <= level.segments ? 1 : 0]
              }`}
            />
          </span>
        ))}
      </div>
      <p className="min-h-5 text-sm text-text-muted" aria-live="polite">
        {level && (
          <>
            <span className="font-semibold text-text">Password strength: {level.label}.</span>
            {advice && ` ${advice}`}
          </>
        )}
      </p>
    </div>
  );
}

interface PasswordFieldProps extends Omit<ComponentProps<"input">, "type"> {
  label: string;
  hint?: string;
  errors?: string[] | undefined;
  /** Show the strength meter, scoring against these words (email, handle, name). */
  meterWith?: string[];
}

export function PasswordField({ meterWith, onChange, ...props }: PasswordFieldProps) {
  const id = useId().replaceAll(":", "");
  const [shown, setShown] = useState(false);
  const [value, setValue] = useState("");
  return (
    <Field
      {...props}
      id={id}
      type={shown ? "text" : "password"}
      autoCapitalize="none"
      autoCorrect="off"
      spellCheck={false}
      onChange={(event) => {
        setValue(event.target.value);
        onChange?.(event);
      }}
      trailing={
        <PardaToggle
          shown={shown}
          controls={id}
          onToggle={() => {
            setShown((now) => !now);
          }}
        />
      }
      below={meterWith ? <StrengthMeter password={value} related={meterWith} /> : undefined}
    />
  );
}
