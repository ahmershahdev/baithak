import { describe, expect, test } from "vitest";

import { inline, parse } from "./format";

const text = (value: string) => ({ type: "text", text: value });

describe("inline", () => {
  test("bold, italic, underline, strike and spoiler", () => {
    expect(inline("**b** *i* _i_ __u__ ~~s~~ ||x||")).toEqual([
      { type: "bold", children: [text("b")] },
      text(" "),
      { type: "italic", children: [text("i")] },
      text(" "),
      { type: "italic", children: [text("i")] },
      text(" "),
      { type: "underline", children: [text("u")] },
      text(" "),
      { type: "strike", children: [text("s")] },
      text(" "),
      { type: "spoiler", children: [text("x")] },
    ]);
  });

  test("marks nest", () => {
    expect(inline("**bold *and italic***")).toEqual([
      {
        type: "bold",
        children: [text("bold "), { type: "italic", children: [text("and italic")] }],
      },
    ]);
  });

  test("code is taken as typed, marks and all", () => {
    expect(inline("run `npm **run** dev` now")).toEqual([
      text("run "),
      { type: "code", text: "npm **run** dev" },
      text(" now"),
    ]);
  });

  test("snake_case, lone marks, spaced marks and unclosed marks stay plain", () => {
    for (const plain of ["file_name_here", "2 * 3 * 4", "a ** b ** c", "**open", "~~ x ~~", "``"]) {
      expect(inline(plain)).toEqual([text(plain)]);
    }
  });

  test("a backslash keeps a mark as typed", () => {
    expect(inline("\\*not italic\\*")).toEqual([text("*not italic*")]);
  });

  test("bare URLs link and leave the punctuation after them", () => {
    expect(inline("see https://example.com/a_b, (https://x.dev/p) or http://y.io.")).toEqual([
      text("see "),
      {
        type: "link",
        href: "https://example.com/a_b",
        children: [text("https://example.com/a_b")],
      },
      text(", ("),
      { type: "link", href: "https://x.dev/p", children: [text("https://x.dev/p")] },
      text(") or "),
      { type: "link", href: "http://y.io", children: [text("http://y.io")] },
      text("."),
    ]);
  });

  test("masked links need http or https", () => {
    expect(inline("[docs](https://ahmershah.dev) [bad](javascript:alert(1))")).toEqual([
      { type: "link", href: "https://ahmershah.dev", children: [text("docs")] },
      text(" [bad](javascript:alert(1))"),
    ]);
  });

  test("HTML is just text", () => {
    expect(inline("<img src=x onerror=alert(1)>")).toEqual([text("<img src=x onerror=alert(1)>")]);
  });
});

describe("parse", () => {
  test("a plain message is one paragraph, line breaks kept", () => {
    expect(parse("hello\nthere")).toEqual([
      { type: "paragraph", children: [text("hello\nthere")] },
    ]);
  });

  test("code blocks, with or without a language", () => {
    expect(parse("before\n```py\nprint('@amna')\n```\nafter")).toEqual([
      { type: "paragraph", children: [text("before")] },
      { type: "code", lang: "py", text: "print('@amna')" },
      { type: "paragraph", children: [text("after")] },
    ]);
    expect(parse("```one line```")).toEqual([{ type: "code", lang: "", text: "one line" }]);
  });

  test("an unclosed fence is plain text", () => {
    expect(parse("``` not closed")).toEqual([
      { type: "paragraph", children: [text("``` not closed")] },
    ]);
  });

  test("quotes, headings and lists", () => {
    expect(parse("# Title\n> quoted\n> **lines**\n- one\n- two\n3. three\n4. four")).toEqual([
      { type: "heading", level: 1, children: [text("Title")] },
      {
        type: "quote",
        children: [
          {
            type: "paragraph",
            children: [text("quoted\n"), { type: "bold", children: [text("lines")] }],
          },
        ],
      },
      { type: "list", ordered: false, start: 1, items: [[text("one")], [text("two")]] },
      { type: "list", ordered: true, start: 3, items: [[text("three")], [text("four")]] },
    ]);
  });

  test("a '#' with no space, or four of them, is not a heading", () => {
    expect(parse("#general\n#### four")).toEqual([
      { type: "paragraph", children: [text("#general\n#### four")] },
    ]);
  });
});
