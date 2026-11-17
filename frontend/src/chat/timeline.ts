import type { components } from "../api/schema";

export type Message = components["schemas"]["Message"];

/** One channel's messages as this tab knows them. */
export interface Timeline {
  messages: Message[];
  /** The newest change this tab has applied; the next live event should be lastEvent + 1. */
  lastEvent: number;
  /** Older messages exist above the first one shown. */
  hasMore: boolean;
}

/**
 * Upsert by seq and keep seq order. A message seen twice keeps the copy with the higher event,
 * so a late page can't undo an edit or delete that already arrived live.
 */
export function merge(current: Message[], incoming: Message[]): Message[] {
  const bySeq = new Map(current.map((message) => [message.seq, message]));
  for (const message of incoming) {
    const known = bySeq.get(message.seq);
    if (!known || known.event < message.event) bySeq.set(message.seq, message);
  }
  return [...bySeq.values()].sort((a, b) => a.seq - b.seq);
}

export type Applied = { kind: "applied"; timeline: Timeline } | { kind: "stale" } | { kind: "gap" };

/**
 * Apply one live event. Events arrive in order per channel; anything after a skipped number
 * means the socket missed something, and the caller catches up from lastEvent instead.
 */
export function applyEvent(timeline: Timeline, event: number, message: Message): Applied {
  if (event <= timeline.lastEvent) return { kind: "stale" };
  if (event > timeline.lastEvent + 1) return { kind: "gap" };
  return {
    kind: "applied",
    timeline: { ...timeline, messages: merge(timeline.messages, [message]), lastEvent: event },
  };
}

/** Consecutive messages from one person within five minutes are shown as one group. */
export function startsGroup(previous: Message | undefined, message: Message): boolean {
  if (!previous || previous.author?.id !== message.author?.id) return true;
  const gap = new Date(message.created_at).getTime() - new Date(previous.created_at).getTime();
  return gap > 5 * 60_000;
}
