const PATHS = {
  smile:
    "M10 17.5a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15z M7 11.8c.7.9 1.8 1.4 3 1.4s2.3-.5 3-1.4 M7.5 8h.01 M12.5 8h.01",
  reply: "M8 5 3.5 9.5 8 14 M3.5 9.5H12a4.5 4.5 0 0 1 4.5 4.5v1",
  issue: "M10 17.5a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15z M10 10.5h.01",
  pencil: "M13.5 3.5l3 3L7 16H4v-3z M11.5 5.5l3 3",
  trash: "M4 5.5h12 M8 5.5V3.5h4v2 M5.5 5.5l.8 11h7.4l.8-11 M8.5 8.5v5 M11.5 8.5v5",
  paperclip:
    "M15.5 9.5l-5.6 5.6a3.5 3.5 0 0 1-5-5l6.4-6.4a2.3 2.3 0 0 1 3.3 3.3l-6.3 6.3a1.2 1.2 0 0 1-1.7-1.7l5.5-5.5",
  send: "M3.5 10 16.5 3.5 13 16.5l-3-5.5z M10 11l6.5-7.5",
  bold: "M6 4h5a3 3 0 0 1 0 6H6z M6 10h6a3 3 0 0 1 0 6H6z",
  italic: "M12 4H8.5 M11.5 16H8 M11 4 9 16",
  strike:
    "M4 10h12 M13.5 6.5C13 5 11.7 4 10 4 8 4 6.5 5 6.5 6.7c0 1.2.8 2 2.2 2.6 M7 14c.6 1.3 1.8 2 3.4 2 2.1 0 3.6-1 3.6-2.8",
  code: "M7 6 3 10l4 4 M13 6l4 4-4 4",
  link: "M8.5 11.5a3 3 0 0 0 4.2 0l2.6-2.6a3 3 0 0 0-4.2-4.2l-.8.8 M11.5 8.5a3 3 0 0 0-4.2 0l-2.6 2.6a3 3 0 0 0 4.2 4.2l.8-.8",
  quote: "M5 5v10 M8.5 7h7 M8.5 10h7 M8.5 13h5",
  list: "M7.5 5.5h9 M7.5 10h9 M7.5 14.5h9 M3.5 5.5h.01 M3.5 10h.01 M3.5 14.5h.01",
  search: "M9 15.5a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13z M13.7 13.7 17 17",
  down: "M10 4v12 M5 11l5 5 5-5",
  close: "M5 5l10 10 M15 5 5 15",
  people:
    "M7.5 9a2.75 2.75 0 1 0 0-5.5 2.75 2.75 0 0 0 0 5.5z M2.5 16c.6-2.6 2.6-4 5-4s4.4 1.4 5 4 M13 4a2.6 2.6 0 0 1 0 5 M14.5 12.3c1.4.5 2.4 1.7 2.9 3.7",
  thread: "M4 4.5h12v8H9l-4 3.5v-3.5H4z",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, className = "size-4" }: { name: IconName; className?: string }) {
  return (
    <svg
      viewBox="0 0 20 20"
      className={`shrink-0 ${className}`}
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
