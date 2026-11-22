import { describe, expect, test } from "vitest";

import type { Channel } from "../api/chat";
import type { Message } from "./timeline";
import { applyRead, badge, countMessage, firstUnread } from "./unread";

const ME = 1;

const channel: Channel = {
  id: 5,
  name: "general",
  kind: "public",
  topic: "",
  is_default: true,
  archived: false,
  is_member: true,
  last_seq: 4,
  last_read_seq: 2,
  unread: 2,
  people: [],
  created_at: "2026-11-01T10:00:00Z",
};

function message(seq: number, authorId: number, deleted = false): Message {
  return {
    id: seq,
    seq,
    event: seq,
    parent_seq: null,
    thread_seq: null,
    also_in_channel: false,
    reply_count: 0,
    last_reply_at: null,
    mentions: [],
    mentions_channel: false,
    reactions: [],
    attachments: [],
    issue: null,
    author: { id: authorId, username: `u${String(authorId)}`, display_name: "" },
    body: deleted ? "" : "text",
    client_id: "",
    created_at: "2026-11-17T10:00:00Z",
    edited_at: null,
    deleted,
  };
}

describe("countMessage", () => {
  test("a new message from someone else counts", () => {
    expect(countMessage(channel, message(5, 2), ME)).toMatchObject({ last_seq: 5, unread: 3 });
  });

  test("my own message does not", () => {
    expect(countMessage(channel, message(5, ME), ME)).toMatchObject({ last_seq: 5, unread: 2 });
  });

  test("deleting an unread message takes it off", () => {
    expect(countMessage(channel, message(3, 2, true), ME).unread).toBe(1);
  });

  test("deleting a message already read changes nothing", () => {
    expect(countMessage(channel, message(1, 2, true), ME).unread).toBe(2);
  });

  test("an edit changes nothing", () => {
    expect(countMessage(channel, message(3, 2), ME)).toEqual(channel);
  });

  test("the count never goes below zero", () => {
    const empty = { ...channel, unread: 0 };
    expect(countMessage(empty, message(3, 2, true), ME).unread).toBe(0);
  });

  test("without a marker only last_seq moves", () => {
    const outside = { ...channel, is_member: false, last_read_seq: null, unread: null };
    expect(countMessage(outside, message(5, 2), ME)).toEqual({ ...outside, last_seq: 5 });
  });
});

describe("applyRead", () => {
  test("reading to the end clears the count", () => {
    expect(applyRead(channel, 4)).toMatchObject({ last_read_seq: 4, unread: 0 });
  });

  test("an older marker is ignored", () => {
    expect(applyRead(channel, 1)).toBe(channel);
  });

  test("reading part of the way leaves the count to the server", () => {
    expect(applyRead(channel, 3)).toBeNull();
  });
});

describe("firstUnread", () => {
  const messages = [
    message(1, 2),
    message(2, 2),
    message(3, ME),
    message(4, 2, true),
    message(5, 2),
  ];

  test("skips my own and deleted messages", () => {
    expect(firstUnread(messages, 2, ME)).toBe(5);
  });

  test("nothing new, no line", () => {
    expect(firstUnread(messages, 5, ME)).toBeNull();
  });

  test("no marker, no line", () => {
    expect(firstUnread(messages, null, ME)).toBeNull();
  });
});

test("badge caps at 99+", () => {
  expect([badge(7), badge(99), badge(100)]).toEqual(["7", "99", "99+"]);
});
