import { expect, test } from "vitest";

import type { Notification } from "../api/notifications";
import {
  describe as describeNotification,
  notificationHref,
  notificationText,
  preview,
} from "./notifications";

function notification(kind: Notification["kind"]): Notification {
  return {
    id: 1,
    kind,
    channel: 5,
    issue: null,
    actor: null,
    created_at: "2026-11-21T10:00:00Z",
    read: false,
    message: {
      id: 9,
      seq: 9,
      event: 9,
      parent_seq: null,
      thread_seq: null,
      also_in_channel: false,
      reply_count: 0,
      last_reply_at: null,
      author: { id: 2, username: "bilal", display_name: "Bilal" },
      body: "hi",
      client_id: "",
      created_at: "2026-11-21T10:00:00Z",
      edited_at: null,
      deleted: false,
      mentions: [],
      mentions_channel: false,
      reactions: [],
      attachments: [],
      issue: null,
      kind: "message",
      sender_name: "",
    },
  };
}

test("each kind reads naturally", () => {
  expect(describeNotification(notification("mention"), "general")).toBe(
    "Bilal mentioned you in general",
  );
  expect(describeNotification(notification("direct"), "Bilal")).toBe("Bilal wrote to you");
  expect(describeNotification(notification("channel"), "general")).toBe(
    "Bilal wrote to everyone in general",
  );
});

test("preview flattens and shortens", () => {
  expect(preview("one\n\ntwo   three")).toBe("one two three");
  expect(preview("a".repeat(200), 10)).toBe(`${"a".repeat(9)}…`);
});

test("an assigned issue names who assigned it and links to the issue", () => {
  const assigned: Notification = {
    ...notification("assigned"),
    channel: null,
    message: null,
    issue: { ref: "BAI-7", project: "BAI", number: 7, title: "Fix uploads" },
    actor: { id: 1, username: "amna", display_name: "Amna Khan" },
  };

  expect(describeNotification(assigned, "a channel")).toBe("Amna Khan assigned you BAI-7");
  expect(notificationHref("team", assigned)).toBe("/w/team/projects/BAI/issues/7");
  expect(notificationText(assigned)).toBe("Fix uploads");
});

test("a message notice links into its thread and previews its text", () => {
  const reply = notification("mention");
  const inThread: Notification = {
    ...reply,
    message: reply.message && { ...reply.message, parent_seq: 3, body: "" },
  };

  expect(notificationHref("team", inThread)).toBe("/w/team/c/5?thread=3");
  expect(notificationText(inThread)).toBe("Shared a file");
});
