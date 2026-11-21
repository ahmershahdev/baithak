import { expect, test } from "vitest";

import { emojiName, reactedByMe, whoReacted, type Reaction } from "./reactions";

const FIRE = "\u{1F525}";
const person = (id: number, username: string, display_name = "") => ({
  id,
  username,
  display_name,
});

const reaction = (users: Reaction["users"]): Reaction => ({
  emoji: FIRE,
  count: users.length,
  users,
});

test("whoReacted names me first and folds long lists", () => {
  expect(whoReacted(reaction([person(2, "bilal", "Bilal")]), 1)).toBe("Bilal reacted with fire");
  expect(whoReacted(reaction([person(2, "bilal", "Bilal"), person(1, "amna")]), 1)).toBe(
    "You and Bilal reacted with fire",
  );
  const many = [1, 2, 3, 4, 5].map((id) => person(id, `u${String(id)}`));
  expect(whoReacted(reaction(many), 9)).toBe("u1, u2, u3 and 2 more reacted with fire");
});

test("reactedByMe and emojiName", () => {
  expect(reactedByMe(reaction([person(1, "amna")]), 1)).toBe(true);
  expect(reactedByMe(reaction([person(2, "bilal")]), 1)).toBe(false);
  expect(emojiName(FIRE)).toBe("fire");
  expect(emojiName("\u{1F984}")).toBe("\u{1F984}");
});
