const weekday = new Intl.DateTimeFormat("en", { weekday: "long", month: "long", day: "numeric" });
const withYear = new Intl.DateTimeFormat("en", {
  weekday: "long",
  month: "long",
  day: "numeric",
  year: "numeric",
});

/** The local calendar day of a time, as a key that compares equal for the same day. */
export function dayKey(iso: string): string {
  const date = new Date(iso);
  return `${String(date.getFullYear())}-${String(date.getMonth())}-${String(date.getDate())}`;
}

export function dayLabel(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
  if (dayKey(iso) === dayKey(now.toISOString())) return "Today";
  if (dayKey(iso) === dayKey(yesterday.toISOString())) return "Yesterday";
  return date.getFullYear() === now.getFullYear() ? weekday.format(date) : withYear.format(date);
}

export function startsDay(previous: { created_at: string } | undefined, iso: string): boolean {
  return previous === undefined || dayKey(previous.created_at) !== dayKey(iso);
}
