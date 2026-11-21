export type Part = { text: string; hit: boolean };

/**
 * Mark the words a search found, the way MySQL matched them: each term as the start of a word,
 * ignoring case.
 */
export function highlight(text: string, terms: string[]): Part[] {
  if (terms.length === 0 || !text) return text ? [{ text, hit: false }] : [];
  const escaped = terms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`(?<![\\p{L}\\p{N}_])(?:${escaped.join("|")})[\\p{L}\\p{N}_]*`, "giu");
  const parts: Part[] = [];
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > last) parts.push({ text: text.slice(last, match.index), hit: false });
    parts.push({ text: match[0], hit: true });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push({ text: text.slice(last), hit: false });
  return parts;
}

/** Where a result opens: its channel, or its thread for a reply. */
export function resultHref(slug: string, channel: number, parentSeq: number | null): string {
  const base = `/w/${slug}/c/${String(channel)}`;
  return parentSeq === null ? base : `${base}?thread=${String(parentSeq)}`;
}
