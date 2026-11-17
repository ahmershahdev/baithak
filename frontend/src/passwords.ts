// Mirrors backend/apps/core/passwords.py; the API still decides.
export const MIN_LENGTH = 12;
export const MAX_LENGTH = 128;

function count(text: string, test: (c: string) => boolean): number {
  let found = 0;
  for (const char of text) if (test(char)) found += 1;
  return found;
}
const isLower = (c: string) => c !== c.toUpperCase() && c === c.toLowerCase();
const isUpper = (c: string) => c !== c.toLowerCase() && c === c.toUpperCase();
const isDigit = (c: string) => c >= "0" && c <= "9";
const isSymbol = (c: string) => !isLower(c) && !isUpper(c) && !isDigit(c) && c.trim() !== "";

export const RULES: { label: string; met: (password: string) => boolean }[] = [
  {
    label: `${String(MIN_LENGTH)} to ${String(MAX_LENGTH)} characters`,
    met: (p) => p.length >= MIN_LENGTH && p.length <= MAX_LENGTH,
  },
  { label: "2 lowercase letters", met: (p) => count(p, isLower) >= 2 },
  { label: "2 uppercase letters", met: (p) => count(p, isUpper) >= 2 },
  { label: "2 digits", met: (p) => count(p, isDigit) >= 2 },
  { label: "1 symbol, like - ! # or @", met: (p) => count(p, isSymbol) >= 1 },
];

export function meetsRules(password: string): boolean {
  return RULES.every((rule) => rule.met(password));
}
