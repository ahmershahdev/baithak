import { describe, expect, test } from "vitest";

import { linkSelection, prefixLines, wrapSelection } from "./markup";

describe("wrapSelection", () => {
  test("wraps the selection and keeps it selected", () => {
    expect(wrapSelection("say hello now", 4, 9, "**")).toEqual({
      text: "say **hello** now",
      start: 6,
      end: 11,
    });
  });

  test("puts the caret between the marks when nothing is selected", () => {
    expect(wrapSelection("ab", 1, 1, "`")).toEqual({ text: "a``b", start: 2, end: 2 });
  });

  test("takes the mark off when it is already there", () => {
    expect(wrapSelection("say **hello** now", 6, 11, "**")).toEqual({
      text: "say hello now",
      start: 4,
      end: 9,
    });
  });
});

describe("prefixLines", () => {
  test("prefixes every touched line", () => {
    expect(prefixLines("one\ntwo\nthree", 1, 6, "- ")).toEqual({
      text: "- one\n- two\nthree",
      start: 3,
      end: 10,
    });
  });

  test("removes the prefix when every line has it", () => {
    expect(prefixLines("> one\n> two", 0, 11, "> ")).toEqual({
      text: "one\ntwo",
      start: 0,
      end: 7,
    });
  });
});

describe("linkSelection", () => {
  test("turns the selection into a link and selects the address", () => {
    const edit = linkSelection("see docs", 4, 8);
    expect(edit.text).toBe("see [docs](https://)");
    expect(edit.text.slice(edit.start, edit.end)).toBe("https://");
  });

  test("inserts a placeholder label with nothing selected", () => {
    expect(linkSelection("", 0, 0).text).toBe("[text](https://)");
  });
});
