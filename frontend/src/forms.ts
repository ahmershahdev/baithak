import { ApiError } from "./api/workspaces";

export function textField(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value : "";
}

export function honeypot(form: FormData): { website: string } {
  return { website: textField(form, "website") };
}

/** What to show for a failed call: the API's own words, or that it could not be reached. */
export function errorText(error: unknown): string | null {
  if (!error) return null;
  if (!(error instanceof ApiError)) return "Could not reach Baithak. Try again.";
  return (
    Object.values(error.problems.fields).flat().join(" ") ||
    (error.problems.detail ?? error.message)
  );
}
