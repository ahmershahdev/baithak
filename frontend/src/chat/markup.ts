export interface Edit {
  text: string;
  start: number;
  end: number;
}

/**
 * Puts a mark around the selection, or takes it off when the selection is already wrapped in
 * it. With nothing selected the caret lands between the two marks.
 */
export function wrapSelection(text: string, start: number, end: number, mark: string): Edit {
  const before = text.slice(0, start);
  const inside = text.slice(start, end);
  const after = text.slice(end);
  if (before.endsWith(mark) && after.startsWith(mark)) {
    return {
      text: before.slice(0, -mark.length) + inside + after.slice(mark.length),
      start: start - mark.length,
      end: end - mark.length,
    };
  }
  return {
    text: before + mark + inside + mark + after,
    start: start + mark.length,
    end: end + mark.length,
  };
}

/** Starts every line the selection touches with a prefix such as "> " or "- ". */
export function prefixLines(text: string, start: number, end: number, prefix: string): Edit {
  const from = text.lastIndexOf("\n", start - 1) + 1;
  const lines = text.slice(from, end).split("\n");
  const all = lines.every((line) => line.startsWith(prefix));
  const changed = lines.map((line) => (all ? line.slice(prefix.length) : prefix + line));
  const shift = all ? -prefix.length : prefix.length;
  return {
    text: text.slice(0, from) + changed.join("\n") + text.slice(end),
    start: Math.max(from, start + shift),
    end: end + shift * lines.length,
  };
}

/** Makes the selection a link; with nothing selected, inserts one ready for its text. */
export function linkSelection(text: string, start: number, end: number): Edit {
  const label = text.slice(start, end) || "text";
  const inserted = `[${label}](https://)`;
  const urlAt = start + label.length + 3;
  return {
    text: text.slice(0, start) + inserted + text.slice(end),
    start: urlAt,
    end: urlAt + "https://".length,
  };
}
