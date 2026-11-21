import type { Channel } from "../api/chat";
import type { Message } from "./timeline";

/**
 * A channel's count after one live message event. Exact for new messages and deletes; the
 * server's count replaces it whenever the channel list is fetched again (after a reconnect).
 */
export function countMessage(channel: Channel, message: Message, meId: number): Channel {
  // A reply kept in its thread has no place in the channel and doesn't count.
  if (message.seq === null) return channel;
  const isNew = message.seq > channel.last_seq;
  const lastSeq = Math.max(channel.last_seq, message.seq);
  if (channel.last_read_seq === null || channel.unread === null) {
    return { ...channel, last_seq: lastSeq };
  }
  const counts = message.author?.id !== meId && message.seq > channel.last_read_seq;
  let unread = channel.unread;
  if (counts && isNew && !message.deleted) unread += 1;
  // Each message is deleted once and its delete event is unique, so this can't count twice.
  if (counts && !isNew && message.deleted) unread = Math.max(0, unread - 1);
  return { ...channel, last_seq: lastSeq, unread };
}

/** The marker moved, here or on another device. Null when only the server can say how many
 * are left, because deleted messages between the old and new marker are not known here. */
export function applyRead(channel: Channel, lastReadSeq: number): Channel | null {
  const current = channel.last_read_seq ?? 0;
  if (lastReadSeq <= current) return channel;
  if (lastReadSeq >= channel.last_seq) return { ...channel, last_read_seq: lastReadSeq, unread: 0 };
  return null;
}

/** The first message to put the "New" line above when a channel is opened, if any. */
export function firstUnread(
  messages: Message[],
  lastReadSeq: number | null,
  meId: number,
): number | null {
  if (lastReadSeq === null) return null;
  const first = messages.find(
    (message) =>
      message.seq !== null &&
      message.seq > lastReadSeq &&
      message.author?.id !== meId &&
      !message.deleted,
  );
  return first?.seq ?? null;
}

export function badge(unread: number): string {
  return unread > 99 ? "99+" : String(unread);
}
