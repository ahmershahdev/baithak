import { expect, test } from "vitest";

import type { Channel } from "../api/chat";
import { channelTitle, isConversation, matches } from "./conversations";

const base: Channel = {
  id: 9,
  name: "~1-2-3",
  kind: "group",
  topic: "",
  is_default: false,
  archived: false,
  is_member: true,
  last_seq: 0,
  last_read_seq: 0,
  unread: 0,
  people: [
    { id: 1, username: "amna", display_name: "Amna Khan" },
    { id: 2, username: "bilal", display_name: "Bilal Ahmed" },
    { id: 3, username: "sara", display_name: "" },
  ],
  created_at: "2026-11-01T10:00:00Z",
};

test("a conversation is titled by the other people in it", () => {
  expect(channelTitle(base, 1)).toBe("Bilal Ahmed, sara");
  expect(channelTitle({ ...base, people: base.people.slice(0, 1) }, 1)).toBe("Just you");
});

test("a channel keeps its name", () => {
  const general = { ...base, name: "general", kind: "public" as const, people: [] };
  expect(channelTitle(general, 1)).toBe("general");
  expect(isConversation(general)).toBe(false);
  expect(isConversation(base)).toBe(true);
});

test("matches handles and the start of any name", () => {
  const bilal = { username: "bilal", display_name: "Bilal Ahmed" };
  expect(matches(bilal, "")).toBe(true);
  expect(matches(bilal, "@bil")).toBe(true);
  expect(matches(bilal, "ahm")).toBe(true);
  expect(matches(bilal, "med")).toBe(false);
});
