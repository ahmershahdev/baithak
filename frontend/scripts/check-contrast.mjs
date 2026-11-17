// Checks every foreground/background pair the UI uses against WCAG 2.2 AA, in both themes.
// Run: node frontend/scripts/check-contrast.mjs   (exits 1 on any failure)
// Thresholds: 4.5 for text, 3 for UI parts and focus rings (WCAG 1.4.3 and 1.4.11).
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../src/styles/tokens.css", import.meta.url), "utf8").replace(
  /\/\*[\s\S]*?\*\//g,
  "",
);

const raw = new Map();
for (const [, name, value] of css.matchAll(/--([\w-]+):\s*([^;]+);/g)) {
  if (!raw.has(name)) raw.set(name, value.trim());
}

function resolve(value, theme) {
  const ld = value.match(/^light-dark\((.+),\s*(.+)\)$/);
  if (ld) return resolve(theme === "light" ? ld[1].trim() : ld[2].trim(), theme);
  const ref = value.match(/^var\(--([\w-]+)\)$/);
  if (ref) {
    const next = raw.get(ref[1]);
    if (next === undefined) throw new Error(`unknown token --${ref[1]}`);
    return resolve(next, theme);
  }
  if (/^#[0-9a-f]{6}$/i.test(value)) return value.toLowerCase();
  throw new Error(`cannot resolve "${value}"`);
}

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const TEXT = 4.5;
const UI = 3;
const backgrounds = ["bg", "bg-subtle", "surface", "surface-raised", "surface-sunken"];

const pairs = [
  ...[
    "text",
    "text-muted",
    "text-subtle",
    "accent-text",
    "ember",
    "success",
    "warning",
    "danger",
    "info",
  ].flatMap((fg) => backgrounds.map((bg) => [fg, bg, TEXT])),
  ...["border-strong", "focus-ring", "accent"].flatMap((fg) =>
    ["bg", "surface"].map((bg) => [fg, bg, UI]),
  ),
  ["on-accent", "accent", TEXT],
  ["on-accent", "accent-hover", TEXT],
  ["on-danger", "danger-fill", TEXT],
  ["on-unread", "unread", TEXT],
  ["accent-soft-text", "accent-soft", TEXT],
  ["ember-soft-text", "ember-soft", TEXT],
  ["success-soft-text", "success-soft", TEXT],
  ["warning-soft-text", "warning-soft", TEXT],
  ["danger-soft-text", "danger-soft", TEXT],
  ["info-soft-text", "info-soft", TEXT],
  ["text", "mention", TEXT],
  ["selection-text", "selection", TEXT],
  ["border-strong", "warning-soft", UI],
  ["warning-soft-text", "bg-subtle", TEXT],
  ["scrollbar-thumb", "bg", UI],
  ["scrollbar-thumb", "surface", UI],
  ["scrollbar-thumb-hover", "bg", UI],
  ["presence-online", "bg-subtle", UI],
  ["presence-away", "bg-subtle", UI],
  ["presence-busy", "bg-subtle", UI],
];

let failures = 0;
for (const theme of ["light", "dark"]) {
  console.log(`\n${theme}`);
  for (const [fg, bg, min] of pairs) {
    const a = resolve(raw.get(fg), theme);
    const b = resolve(raw.get(bg), theme);
    const r = ratio(a, b);
    const ok = r >= min;
    if (!ok) failures += 1;
    console.log(
      `  ${ok ? "ok  " : "FAIL"} ${r.toFixed(2).padStart(5)}  ${fg} on ${bg} (${a} / ${b}, needs ${min})`,
    );
  }
}

if (failures) {
  console.error(`\n${failures} pair(s) below WCAG AA`);
  process.exit(1);
}
console.log("\nall pairs pass WCAG AA");
