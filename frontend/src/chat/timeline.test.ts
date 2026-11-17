import { describe, expect, test } from "vitest";

import { applyEvent, merge, startsGroup, type Message, type Timeline } from "./timeline";

function message(seq: number, event = seq, extra: Partial<Message> = {}): Message {
  return {
    id: seq,
    seq,
    event,
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
