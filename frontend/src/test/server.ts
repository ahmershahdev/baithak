import { vi } from "vitest";

type Handler = (request: Request) => Response | Promise<Response>;

export function json(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// Answers every test gets unless it says otherwise: no workspaces yet, reCAPTCHA off.
const DEFAULTS: Record<string, Handler> = {
  "GET /api/v1/workspaces/": () => json(200, []),
  "GET /api/v1/auth/config/": () =>
    json(200, { recaptcha_v3_site_key: "", recaptcha_v2_site_key: "" }),
};

// A stand-in for the backend: routes are "METHOD /path/", unknown routes answer 404.
export function fakeBackend(overrides: Record<string, Handler>) {
  const routes = { ...DEFAULTS, ...overrides };
  const requests: Request[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof Request ? input : new Request(input, init);
    requests.push(request);
    const key = `${request.method} ${new URL(request.url).pathname}`;
    if (key === "GET /api/v1/auth/csrf/") {
      document.cookie = "csrftoken=test-csrf-token";
      return new Response(null, { status: 204 });
    }
    const handler = routes[key];
    return handler ? handler(request) : json(404, { detail: "Not found." });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { requests };
}
