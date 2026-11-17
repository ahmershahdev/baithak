const KEY = "baithak:last-workspace";

export function rememberWorkspace(slug: string) {
  try {
    localStorage.setItem(KEY, slug);
  } catch {
    // Not important: home then opens the first workspace instead.
  }
}

export function lastWorkspace(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}
