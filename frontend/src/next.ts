// Where to go after signing in, for example back to an invitation. Kept in sessionStorage so it
// survives the trip through sign-up and the confirmation email in the same tab.
const KEY = "baithak:next";

/** Only paths on this site: "/x" but not "//evil.example" or "https://...". */
export function safePath(value: string | null): string | null {
  if (!value?.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return null;
  return value;
}

export function rememberNext(value: string | null) {
  const path = safePath(value);
  try {
    if (path) sessionStorage.setItem(KEY, path);
  } catch {
    // Storage can be blocked; the person just lands on home instead.
  }
}

export function takeNext(): string {
  try {
    const path = safePath(sessionStorage.getItem(KEY));
    sessionStorage.removeItem(KEY);
    return path ?? "/";
  } catch {
    return "/";
  }
}
