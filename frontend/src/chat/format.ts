// Discord-style message formatting, parsed into a tree that React renders as elements. User text
// never becomes HTML, so nothing typed can inject markup. Code is read the same way as
// backend/apps/core/mentions.py reads it, so a handle shown as code notifies nobody.

export type Inline =
  | { type: "text"; text: string }
  | { type: "code"; text: string }
  | { type: "bold" | "italic" | "underline" | "strike" | "spoiler"; children: Inline[] }
  | { type: "link"; href: string; children: Inline[] };

export type Block =
  | { type: "paragraph"; children: Inline[] }
  | { type: "heading"; level: 1 | 2 | 3; children: Inline[] }
  | { type: "code"; lang: string; text: string }
  | { type: "quote"; children: Block[] }
  | { type: "list"; ordered: boolean; start: number; items: Inline[][] };

const FENCE = /```([\s\S]*?)```/g;
const LANG = /^[\w+#.-]{1,20}$/;
const QUOTE = /^> ?(.*)$/;
const HEADING = /^(#{1,3}) (.+)$/;
const BULLET = /^\s*[-*] (.+)$/;
const NUMBERED = /^\s*(\d{1,3})\. (.+)$/;
const ESCAPABLE = new Set(["\\", "*", "_", "~", "`", "|", "[", "]", "(", ")", ">", "#", "-"]);
const URL = /^https?:\/\/[^\s<]+/;
const MASKED = /^\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/;

/** Pairs that wrap text, longest first so "**" wins over "*". */
const WRAPS: { mark: string; type: "bold" | "italic" | "underline" | "strike" | "spoiler" }[] = [
  { mark: "**", type: "bold" },
  { mark: "__", type: "underline" },
  { mark: "~~", type: "strike" },
  { mark: "||", type: "spoiler" },
  { mark: "*", type: "italic" },
  { mark: "_", type: "italic" },
];

export function parse(body: string): Block[] {
  const blocks: Block[] = [];
  let last = 0;
  for (const match of body.matchAll(FENCE)) {
    blocks.push(...lines(body.slice(last, match.index)));
    blocks.push(fence(match[1] ?? ""));
    last = match.index + match[0].length;
  }
  blocks.push(...lines(body.slice(last)));
  return blocks;
}

function fence(inner: string): Block {
  const newline = inner.indexOf("\n");
  const first = newline === -1 ? "" : inner.slice(0, newline);
  if (LANG.test(first))
    return { type: "code", lang: first, text: trimNewlines(inner.slice(newline + 1)) };
  return { type: "code", lang: "", text: trimNewlines(inner) };
}

function trimNewlines(text: string): string {
  return text.replace(/^\n+|\n+$/g, "");
}

function lines(text: string, nested = false): Block[] {
  if (!text.trim()) return [];
  const rows = trimNewlines(text).split("\n");
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  const flush = () => {
    if (paragraph.length > 0)
      blocks.push({ type: "paragraph", children: inline(paragraph.join("\n")) });
    paragraph = [];
  };
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i] ?? "";
    if (!nested && QUOTE.test(row)) {
      flush();
      const quoted: string[] = [];
      while (i < rows.length && QUOTE.test(rows[i] ?? "")) {
        quoted.push(QUOTE.exec(rows[i] ?? "")?.[1] ?? "");
        i++;
      }
      i--;
      blocks.push({ type: "quote", children: lines(quoted.join("\n"), true) });
      continue;
    }
    const heading = HEADING.exec(row);
    if (heading) {
      flush();
      const level = (heading[1]?.length ?? 1) as 1 | 2 | 3;
      blocks.push({ type: "heading", level, children: inline(heading[2] ?? "") });
      continue;
    }
    const ordered = NUMBERED.test(row);
    if (ordered || BULLET.test(row)) {
      flush();
      const pattern = ordered ? NUMBERED : BULLET;
      const start = ordered ? Number(NUMBERED.exec(row)?.[1] ?? 1) : 1;
      const items: Inline[][] = [];
      while (i < rows.length && pattern.test(rows[i] ?? "")) {
        const item = pattern.exec(rows[i] ?? "");
        items.push(inline((ordered ? item?.[2] : item?.[1]) ?? ""));
        i++;
      }
      i--;
      blocks.push({ type: "list", ordered, start, items });
      continue;
    }
    paragraph.push(row);
  }
  flush();
  return blocks;
}

function isWordChar(char: string | undefined): boolean {
  return char !== undefined && /[\p{L}\p{N}]/u.test(char);
}

export function inline(text: string): Inline[] {
  const out: Inline[] = [];
  let plain = "";
  const push = (node: Inline) => {
    if (plain) out.push({ type: "text", text: plain });
    plain = "";
    out.push(node);
  };
  let i = 0;
  scan: while (i < text.length) {
    const char = text[i] ?? "";
    const rest = text.slice(i);

    if (char === "\\" && ESCAPABLE.has(text[i + 1] ?? "")) {
      plain += text[i + 1] ?? "";
      i += 2;
      continue;
    }
    if (char === "`") {
      const end = text.indexOf("`", i + 1);
      const code = end === -1 ? "" : text.slice(i + 1, end);
      if (code && !code.includes("\n")) {
        push({ type: "code", text: code });
        i = end + 1;
        continue;
      }
    }
    const masked = MASKED.exec(rest);
    if (masked) {
      push({ type: "link", href: masked[2] ?? "", children: inline(masked[1] ?? "") });
      i += masked[0].length;
      continue;
    }
    if ((char === "h" || char === "H") && !isWordChar(text[i - 1])) {
      const url = URL.exec(rest);
      if (url) {
        const href = trimUrl(url[0]);
        push({ type: "link", href, children: [{ type: "text", text: href }] });
        i += href.length;
        continue;
      }
    }
    for (const { mark, type } of WRAPS) {
      if (!rest.startsWith(mark)) continue;
      const end = closing(text, i + mark.length, mark);
      if (end === -1) continue;
      // "_" only at word edges, so snake_case and file_names stay as typed.
      if (mark === "_" && (isWordChar(text[i - 1]) || isWordChar(text[end + 1]))) continue;
      push({ type, children: inline(text.slice(i + mark.length, end)) });
      i = end + mark.length;
      continue scan;
    }
    plain += char;
    i += 1;
  }
  if (plain) out.push({ type: "text", text: plain });
  return out;
}

/** Where `mark` closes, or -1. The wrapped text can't be empty or start or end with a space. */
function closing(text: string, from: number, mark: string): number {
  let end = text.indexOf(mark, from);
  // "***" or "*a**": a single mark must not be the first half of a double one.
  while (end !== -1 && mark.length === 1 && text[end + 1] === mark)
    end = text.indexOf(mark, end + 2);
  if (end === -1 || end === from) return -1;
  // "***" closing a double mark: the extra one belongs to the italic inside it.
  while (mark.length === 2 && text[end + 2] === mark[0]) end += 1;
  const inner = text.slice(from, end);
  if (/^\s|\s$/.test(inner)) return -1;
  return end;
}

/** A URL at the end of a sentence or inside brackets doesn't own the punctuation after it. */
function trimUrl(url: string): string {
  let out = url.replace(/[.,;:!?'"]+$/, "");
  while (out.endsWith(")") && (out.match(/\(/g) ?? []).length < (out.match(/\)/g) ?? []).length) {
    out = out.slice(0, -1);
  }
  return out;
}
