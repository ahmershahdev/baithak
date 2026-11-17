import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

export type User = components["schemas"]["User"];

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

function csrfToken(): string | undefined {
  return document.cookie
    .split("; ")
    .find((part) => part.startsWith("csrftoken="))
    ?.slice("csrftoken=".length);
}

// Django checks CSRF on every unsafe request, signed in or not. The cookie is set by the csrf
// endpoint the first time it is needed and echoed back in the header Django reads.
const csrf: Middleware = {
  async onRequest({ request }) {
    if (SAFE_METHODS.has(request.method)) return request;
    if (csrfToken() === undefined) {
      await fetch(new URL("/api/v1/auth/csrf/", window.location.origin), {
        credentials: "same-origin",
      });
    }
    const token = csrfToken();
    if (token !== undefined) request.headers.set("X-CSRFToken", token);
    return request;
  },
};

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  credentials: "same-origin",
  // Looked up on every call rather than captured once, so tests can stub fetch.
  fetch: (request) => globalThis.fetch(request),
});
api.use(csrf);

export interface ApiErrors {
  detail?: string;
  fields: Record<string, string[]>;
  /** The API wants the reCAPTCHA checkbox solved before it tries again. */
  captcha?: boolean;
}

// DRF answers 400 with either {"detail": "..."} or {"field": ["...", ...]}.
export function readErrors(error: unknown): ApiErrors {
  const result: ApiErrors = { fields: {} };
  if (typeof error !== "object" || error === null) {
    result.detail = "Something went wrong. Try again.";
    return result;
  }
  for (const [key, value] of Object.entries(error)) {
    if (key === "detail" && typeof value === "string") result.detail = value;
    else if (key === "captcha") result.captcha = value === "v2";
    else if (key === "non_field_errors" && Array.isArray(value))
      result.detail = value.map(String).join(" ");
    else if (Array.isArray(value)) result.fields[key] = value.map(String);
  }
  return result;
}
