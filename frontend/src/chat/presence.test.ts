import { describe, expect, test } from "vitest";

import {
  activeTypers,
  addTyper,
  applyPresence,
  clearTyper,
  placeKey,
  TYPING_SHOWN_MS,
  typingText,
} from "./presence";

const bilal = { id: 2, username: "bilal", display_name: "Bilal" };
const sara = { id: 3, username: "sara", display_name: "" };
const zain = { id: 4, username: "zain", display_name: "Zain" };

describe("typing", () => {
  const key = placeKey(5, null);

  test("a notice shows for a few seconds, and a new one from the same person replaces it", () => {
    let state = addTyper({}, key, bilal, 1_000);
    state = addTyper(state, key, bilal, 3_000);

    expect(state[key]).toHaveLength(1);
    expect(activeTypers(state, key, 3_000 + TYPING_SHOWN_MS - 1)).toEqual([bilal]);
    expect(activeTypers(state, key, 3_000 + TYPING_SHOWN_MS)).toEqual([]);
  });

  test("places are kept apart: a channel and each of its threads", () => {
    const state = addTyper({}, placeKey(5, 7), bilal, 0);

    expect(activeTypers(state, key, 1)).toEqual([]);
    expect(activeTypers(state, placeKey(5, 7), 1)).toEqual([bilal]);
  });

  test("their message clears them", () => {
    const state = addTyper(addTyper({}, key, bilal, 0), key, sara, 0);

    expect(activeTypers(clearTyper(state, key, bilal.id), key, 1)).toEqual([sara]);
    expect(clearTyper(state, key, 99)).toBe(state);
  });

  test("the line reads naturally", () => {
    expect(typingText([])).toBeNull();
    expect(typingText([bilal])).toBe("Bilal is typing");
    expect(typingText([bilal, sara])).toBe("Bilal and sara are typing");
    expect(typingText([bilal, sara, zain])).toBe("Several people are typing");
  });
});

test("applyPresence adds and removes once", () => {
  expect(applyPresence([1, 2], 3, true)).toEqual([1, 2, 3]);
  expect(applyPresence([1, 2, 3], 3, true)).toEqual([1, 2, 3]);
  expect(applyPresence([1, 2, 3], 2, false)).toEqual([1, 3]);
});
