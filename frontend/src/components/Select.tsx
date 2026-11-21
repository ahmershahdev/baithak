import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

export interface SelectOption<T extends string = string> {
  value: T;
  label: string;
}

interface SelectProps<T extends string> {
  options: SelectOption<T>[];
  /** Controlled when set; otherwise starts at defaultValue (or the first option). */
  value?: T;
  defaultValue?: T;
  onChange?: (value: T) => void;
  /** Sent with the form through a hidden input, as a native select would be. */
  name?: string;
  id?: string;
  "aria-label"?: string;
  disabled?: boolean;
  /** Fill the width at every size, for selects in a form column. */
  full?: boolean;
  large?: boolean;
}

/**
 * A select whose open list follows the theme. A native select's list is drawn by the browser
 * and the OS, so it can't be. Keyboard use follows the WAI-ARIA select-only combobox pattern
 * (https://www.w3.org/WAI/ARIA/apg/patterns/combobox/examples/combobox-select-only/).
 */
export function Select<T extends string>({
  options,
  value,
  defaultValue,
  onChange,
  name,
  id,
  "aria-label": ariaLabel,
  disabled = false,
  full = false,
  large = false,
}: SelectProps<T>) {
  const fallbackId = useId();
  const buttonId = id ?? fallbackId;
  const listId = `${buttonId}-list`;
  const [inner, setInner] = useState<T | undefined>(defaultValue ?? options[0]?.value);
  const current = value ?? inner;
  const selectedIndex = Math.max(
    0,
    options.findIndex((option) => option.value === current),
  );
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(selectedIndex);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const outside = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", outside);
    return () => {
      document.removeEventListener("mousedown", outside);
    };
  }, [open]);

  function show() {
    setActive(selectedIndex);
    setOpen(true);
  }

  function choose(index: number) {
    const option = options[index];
    setOpen(false);
    button.current?.focus();
    if (!option || option.value === current) return;
    setInner(option.value);
    onChange?.(option.value);
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const last = options.length - 1;
    if (!open) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) {
        event.preventDefault();
        show();
      }
      return;
    }
    const moves: Record<string, number> = {
      ArrowDown: Math.min(last, active + 1),
      ArrowUp: Math.max(0, active - 1),
      Home: 0,
      End: last,
    };
    const move = moves[event.key];
    if (move !== undefined) {
      event.preventDefault();
      setActive(move);
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      choose(active);
    } else if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
    } else if (event.key === "Tab") {
      choose(active);
    } else if (event.key.length === 1) {
      // Type to jump: the next option starting with that letter.
      const key = event.key.toLowerCase();
      const order = [...options.keys()].map((i) => (active + 1 + i) % options.length);
      const found = order.find((i) => options[i]?.label.toLowerCase().startsWith(key));
      if (found !== undefined) setActive(found);
    }
  }

  return (
    <div ref={root} className={`relative inline-flex w-full ${full ? "" : "sm:w-auto"}`}>
      {name !== undefined && <input type="hidden" name={name} value={current ?? ""} />}
      <button
        ref={button}
        id={buttonId}
        type="button"
        role="combobox"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open ? `${listId}-${String(active)}` : undefined}
        disabled={disabled}
        onClick={() => {
          if (open) setOpen(false);
          else show();
        }}
        onKeyDown={onKeyDown}
        onBlur={(event) => {
          if (!root.current?.contains(event.relatedTarget)) setOpen(false);
        }}
        className={`flex w-full cursor-pointer items-center justify-between gap-3 rounded-lg border border-border-strong bg-bg pr-3 pl-3 text-left text-sm font-semibold text-text transition-colors outline-none hover:border-text-subtle focus-visible:border-focus-ring focus-visible:ring-4 focus-visible:ring-focus-ring/20 disabled:cursor-not-allowed disabled:opacity-60 ${
          large ? "h-12" : "h-10"
        }`}
      >
        <span className="truncate">{options[selectedIndex]?.label}</span>
        <svg
          viewBox="0 0 20 20"
          className={`size-4 shrink-0 text-text-subtle transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden="true"
        >
          <path d="M5 8l5 5 5-5" fill="none" stroke="currentColor" strokeWidth="1.8" />
        </svg>
      </button>
      {open && (
        <ul
          id={listId}
          role="listbox"
          aria-labelledby={buttonId}
          className="settle absolute inset-x-0 top-full z-30 mt-1 min-w-max overflow-hidden rounded-xl border border-border bg-surface-raised p-1 shadow-lg"
        >
          {options.map((option, index) => (
            <li
              key={option.value}
              id={`${listId}-${String(index)}`}
              role="option"
              aria-selected={option.value === current}
              data-active={index === active || undefined}
              onMouseDown={(event) => {
                // Keep focus on the button so its blur doesn't close the list first.
                event.preventDefault();
              }}
              onMouseEnter={() => {
                setActive(index);
              }}
              onClick={() => {
                choose(index);
              }}
              className="flex cursor-pointer items-center justify-between gap-4 rounded-lg px-3 py-2 text-sm data-active:bg-bg-subtle aria-selected:font-semibold"
            >
              {option.label}
              {option.value === current && (
                <svg viewBox="0 0 20 20" className="size-4 text-accent-text" aria-hidden="true">
                  <path d="M4 10.5l4 4 8-9" fill="none" stroke="currentColor" strokeWidth="2" />
                </svg>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
