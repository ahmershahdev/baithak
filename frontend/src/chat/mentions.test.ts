import { describe, expect, test } from "vitest";

import {
  activeQuery,
  insertMention,
  mentionsMe,
  segments,
  suggest,
  type Candidate,
} from "./mentions";
import type { Message } from "./timeline";

const ME = 1;

function message(body: string, extra: Partial<Message> = {}): Message {
  return {
    id: 1,
    seq: 1,
    event: 1,
    parent_seq: null,
    thread_seq: null,
    also_in_channel: false,
    reply_count: 0,
    last_reply_at: null,
    author: { id: 2, username: "bilal", display_name: "" },
    body,
    client_id: "",
    created_at: "2026-11-17T10:00:00Z",
    edited_at: null,
    deleted: false,
    mentions: [],
    mentions_channel: false,
    reactions: [],
    attachments: [],
    issue: null,
    kind: "message",
    ...extra,
  };
}

const amna = { id: 1, username: "amna", display_name: "Amna Khan" };
const sara = { id: 3, username: "sara", display_name: "" };

describe("segments", () => {
  test("marks the mentions the server confirmed, me apart from others", () => {
    const body = "@Amna and @sara, chai? cc @nobody";
    expect(segments(message(body, { mentions: [amna, sara] }), ME)).toEqual([
      { text: "@Amna", mention: "me" },
      { text: " and " },
      { text: "@sara", mention: "person" },
      { text: ", chai? cc @nobody" },
    ]);
  });

  test("a sentence end is not part of the mention", () => {
    expect(segments(message("thanks @sara.", { mentions: [sara] }), ME)).toEqual([
      { text: "thanks " },
      { text: "@sara", mention: "person" },
      { text: "." },
    ]);
  });

  test("@channel only when the server says so", () => {
    expect(segments(message("@channel lunch"), ME)).toEqual([{ text: "@channel lunch" }]);
    expect(segments(message("@channel lunch", { mentions_channel: true }), ME)[0]).toEqual({
      text: "@channel",
      mention: "channel",
    });
  });

  test("an email address is not a mention", () => {
    expect(segments(message("amna@example.com", { mentions: [amna] }), ME)).toEqual([
      { text: "amna@example.com" },
    ]);
  });
});

test("mentionsMe covers @channel", () => {
  expect(mentionsMe(message("hi", { mentions: [amna] }), ME)).toBe(true);
  expect(mentionsMe(message("hi", { mentions_channel: true }), ME)).toBe(true);
  expect(mentionsMe(message("hi", { mentions: [sara] }), ME)).toBe(false);
});

describe("activeQuery", () => {
  test("finds the handle being typed", () => {
    expect(activeQuery("hi @am", 6)).toEqual({ start: 3, query: "am" });
    expect(activeQuery("@", 1)).toEqual({ start: 0, query: "" });
  });

  test("not inside an email, after a space, or away from the caret", () => {
    expect(activeQuery("amna@ex", 7)).toBeNull();
    expect(activeQuery("@amna done", 10)).toBeNull();
    expect(activeQuery("@am rest", 2)).toEqual({ start: 0, query: "a" });
  });
});

test("suggest puts handle matches before name matches", () => {
  const people: Candidate[] = [
    { username: "khalid", display_name: "Khalid Ahmed" },
    { username: "ahmed", display_name: "" },
    { username: "sara", display_name: "Sara Ahmed" },
  ];
  expect(suggest(people, "ahm").map((c) => c.username)).toEqual(["ahmed", "khalid", "sara"]);
  expect(suggest(people, "", 2)).toHaveLength(2);
});

test("insertMention replaces the query and puts the caret after a space", () => {
  expect(insertMention("hi @am there", 3, 6, "amna")).toEqual({
    text: "hi @amna  there",
    caret: 9,
  });
});
