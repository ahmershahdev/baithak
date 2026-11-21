import type { Message } from "./timeline";

// The same shape apps/core/mentions.py matches; the server decides who is really mentioned.
const MENTION = /(?<![\w@.])@([A-Za-z0-9][\w.-]*)/g;

export type Segment = { text: string } | { text: string; mention: "person" | "me" | "channel" };

/** Split a body so the mentions the server confirmed can be shown as such. */
export function segments(message: Message, meId: number): Segment[] {
  const people = new Map(message.mentions.map((m) => [m.username, m.id]));
  const out: Segment[] = [];
  let last = 0;
  for (const match of message.body.matchAll(MENTION)) {
    const raw = match[1] ?? "";
    const handle = raw.toLowerCase().replace(/[._-]+$/, "");
    const kind =
      handle === "channel" && message.mentions_channel
        ? "channel"
        : people.has(handle)
          ? people.get(handle) === meId
            ? "me"
            : "person"
          : null;
    if (kind === null) continue;
    const start = match.index;
    const end = start + 1 + handle.length;
    if (start > last) out.push({ text: message.body.slice(last, start) });
    out.push({ text: message.body.slice(start, end), mention: kind });
    last = end;
  }
  if (last < message.body.length) out.push({ text: message.body.slice(last) });
  return out;
}

export function mentionsMe(message: Message, meId: number): boolean {
  return message.mentions_channel || message.mentions.some((m) => m.id === meId);
}

export interface Candidate {
  username: string;
  display_name: string;
}

/** The "@query" being typed just before the caret, if any. */
export function activeQuery(text: string, caret: number): { start: number; query: string } | null {
  const before = text.slice(0, caret);
  const match = /(?:^|[^\w@.])@([\w.-]*)$/.exec(before);
  if (!match) return null;
  const query = match[1] ?? "";
  return { start: caret - query.length - 1, query: query.toLowerCase() };
}

export const CHANNEL_CANDIDATE: Candidate = {
  username: "channel",
  display_name: "Everyone in this channel",
};

/** Handles starting with the query first, then display names with a word starting with it. */
export function suggest(candidates: Candidate[], query: string, limit = 6): Candidate[] {
  const starts = candidates.filter((c) => c.username.startsWith(query));
  const named = candidates.filter(
    (c) =>
      !c.username.startsWith(query) &&
      c.display_name
        .toLowerCase()
        .split(/\s+/)
        .some((word) => word.startsWith(query)),
  );
  return [...starts, ...named].slice(0, limit);
}

/** Replace the "@query" at `start` with the chosen handle and a space. */
export function insertMention(
  text: string,
  start: number,
  caret: number,
  handle: string,
): { text: string; caret: number } {
  const inserted = `@${handle} `;
  return {
    text: text.slice(0, start) + inserted + text.slice(caret),
    caret: start + inserted.length,
  };
}
