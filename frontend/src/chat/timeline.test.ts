import { describe, expect, test } from "vitest";

import {
  applyEvent,
  merge,
  startsGroup,
  updateThread,
  type Message,
  type Timeline,
} from "./timeline";

function message(seq: number, event = seq, extra: Partial<Message> = {}): Message {
  return {
    id: seq,
    seq,
    event,
    parent_seq: null,
    thread_seq: null,
    also_in_channel: false,
    reply_count: 0,
    last_reply_at: null,
    author: { id: 1, username: "amna", display_name: "Amna" },
    body: `m${String(seq)}`,
    client_id: "",
    created_at: "2026-11-17T10:00:00Z",
    edited_at: null,
    deleted: false,
    ...extra,
  };
}

const timeline = (messages: Message[], lastEvent: number): Timeline => ({
  messages,
  lastEvent,
  hasMore: false,
});

describe("merge", () => {
  test("keeps seq order and stores each message once", () => {
    const merged = merge([message(1), message(3)], [message(2), message(3)]);

    expect(merged.map((m) => m.seq)).toEqual([1, 2, 3]);
  });

  test("the copy with the newer event wins, whichever arrives last", () => {
    const edited = message(1, 5, { body: "edited" });

    expect(merge([edited], [message(1, 1)])[0]?.body).toBe("edited");
    expect(merge([message(1, 1)], [edited])[0]?.body).toBe("edited");
  });
});

describe("applyEvent", () => {
  test("the next event is applied", () => {
    const result = applyEvent(timeline([message(1)], 1), 2, message(2));

    expect(result.kind).toBe("applied");
    if (result.kind === "applied") {
      expect(result.timeline.lastEvent).toBe(2);
      expect(result.timeline.messages.map((m) => m.seq)).toEqual([1, 2]);
    }
  });

  test("an event already seen is ignored", () => {
    expect(applyEvent(timeline([message(1), message(2)], 2), 2, message(2)).kind).toBe("stale");
  });

  test("a skipped event number is a gap to catch up on", () => {
    expect(applyEvent(timeline([message(1)], 1), 3, message(3)).kind).toBe("gap");
  });
});

describe("startsGroup", () => {
  test("a new author or a five minute pause starts a group", () => {
    const first = message(1);
    const soon = message(2, 2, { created_at: "2026-11-17T10:04:00Z" });
    const later = message(3, 3, { created_at: "2026-11-17T10:10:00Z" });
    const other = message(4, 4, { author: { id: 2, username: "bilal", display_name: "" } });

    expect(startsGroup(undefined, first)).toBe(true);
    expect(startsGroup(first, soon)).toBe(false);
    expect(startsGroup(soon, later)).toBe(true);
    expect(startsGroup(later, other)).toBe(true);
  });
});

const reply = (threadSeq: number, event: number, extra: Partial<Message> = {}) =>
  message(100 + threadSeq, event, { seq: null, parent_seq: 1, thread_seq: threadSeq, ...extra });

describe("threads", () => {
  test("a reply kept in its thread advances the channel's event but is not shown there", () => {
    const result = applyEvent(timeline([message(1)], 1), 2, reply(1, 2));

    expect(result.kind).toBe("applied");
    if (result.kind === "applied") {
      expect(result.timeline.lastEvent).toBe(2);
      expect(result.timeline.messages.map((m) => m.seq)).toEqual([1]);
    }
  });

  test("a thread takes its replies in order and its parent's newer copy", () => {
    const thread = { parent: message(1), replies: [reply(2, 4)] };
    const counted = message(1, 5, { reply_count: 2 });

    const next = updateThread(thread, 1, [reply(1, 2), counted, message(2, 6)]);

    expect(next.parent.reply_count).toBe(2);
    expect(next.replies.map((r) => r.thread_seq)).toEqual([1, 2]);
  });

  test("a reply also sent to the channel is in both", () => {
    const both = reply(1, 2, { seq: 2, also_in_channel: true });

    expect(merge([message(1)], [both]).map((m) => m.seq)).toEqual([1, 2]);
    expect(updateThread({ parent: message(1), replies: [] }, 1, [both]).replies).toHaveLength(1);
  });

  test("messages for other threads change nothing", () => {
    const thread = { parent: message(1), replies: [] };

    expect(updateThread(thread, 1, [message(3), reply(1, 9, { parent_seq: 3 })])).toBe(thread);
  });
});
