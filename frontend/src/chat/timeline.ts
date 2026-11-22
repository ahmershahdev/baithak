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

/** A thread as this tab knows it. Kept current by the channel's events, not by its own. */
export interface Thread {
  parent: Message;
  replies: Message[];
}

function mergeBy(
  current: Message[],
  incoming: Message[],
  key: (message: Message) => number | null,
): Message[] {
  const byKey = new Map<number, Message>();
  for (const message of [...current, ...incoming]) {
    const k = key(message);
    if (k === null) continue;
    const known = byKey.get(k);
    if (!known || known.event < message.event) byKey.set(k, message);
  }
  return [...byKey.values()].sort((a, b) => (key(a) ?? 0) - (key(b) ?? 0));
}

/**
 * Upsert by seq and keep seq order. A message seen twice keeps the copy with the higher event,
 * so a late page can't undo an edit or delete that already arrived live. Thread replies not
 * sent to the channel have no seq and are left out.
 */
export function merge(current: Message[], incoming: Message[]): Message[] {
  return mergeBy(current, incoming, (message) => message.seq);
}

export function mergeReplies(current: Message[], incoming: Message[]): Message[] {
  return mergeBy(current, incoming, (message) => message.thread_seq);
}

/** Bring a thread up to date with messages from the channel: its replies and its parent. */
export function updateThread(thread: Thread, seq: number, incoming: Message[]): Thread {
  let parent = thread.parent;
  for (const message of incoming) {
    if (message.seq === seq && message.parent_seq === null && message.event > parent.event) {
      parent = message;
    }
  }
  const replies = incoming.filter((message) => message.parent_seq === seq);
  if (parent === thread.parent && replies.length === 0) return thread;
  return { parent, replies: mergeReplies(thread.replies, replies) };
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

function sender(message: Message): string | null {
  if (message.author) return `user:${String(message.author.id)}`;
  return message.sender_name ? `app:${message.sender_name}` : null;
}

/** Consecutive messages from one person within five minutes are shown as one group. */
export function startsGroup(previous: Message | undefined, message: Message): boolean {
  // Deleted accounts all look alike, so their messages are never run together.
  const who = previous && sender(previous);
  if (!who || who !== sender(message)) return true;
  // An issue update is its own line; the author's next message shows their name again.
  if (previous.kind === "activity") return true;
  const gap = new Date(message.created_at).getTime() - new Date(previous.created_at).getTime();
  return gap > 5 * 60_000;
}

/** client_ids of `me`'s messages: a composer's pending send is done once its id is here. */
export function storedIds(messages: Message[] | undefined, meId: number): Set<string> {
  return new Set(messages?.filter((m) => m.author?.id === meId).map((m) => m.client_id));
}
