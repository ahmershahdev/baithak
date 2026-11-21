import { expect, test } from "vitest";

import type { Notification } from "../api/notifications";
import { describe as describeNotification, preview } from "./notifications";

function notification(kind: Notification["kind"]): Notification {
  return {
    id: 1,
    kind,
    channel: 5,
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
