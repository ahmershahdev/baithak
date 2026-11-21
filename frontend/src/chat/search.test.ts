import { describe, expect, test } from "vitest";

import { highlight, resultHref } from "./search";

describe("highlight", () => {
  test("marks whole words that start with a term, any case", () => {
    expect(highlight("Deployment done; redeploy later", ["deploy"])).toEqual([
      { text: "Deployment", hit: true },
      { text: " done; redeploy later", hit: false },
    ]);
  });

  test("several terms, and text from other scripts", () => {
    expect(highlight("chai سلام time", ["chai", "سل"])).toEqual([
      { text: "chai", hit: true },
      { text: " ", hit: false },
      { text: "سلام", hit: true },
      { text: " time", hit: false },
    ]);
  });

  test("terms are matched literally, not as patterns", () => {
    expect(highlight("aab a+b", ["a+"])).toEqual([
      { text: "aab ", hit: false },
      { text: "a+b", hit: true },
    ]);
  });

  test("nothing to mark", () => {
    expect(highlight("plain", [])).toEqual([{ text: "plain", hit: false }]);
    expect(highlight("", ["x"])).toEqual([]);
  });
});

test("resultHref opens the thread for a reply", () => {
  expect(resultHref("team", 5, null)).toBe("/w/team/c/5");
  expect(resultHref("team", 5, 12)).toBe("/w/team/c/5?thread=12");
});
