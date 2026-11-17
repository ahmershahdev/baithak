import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { App } from "./App";

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(body), { status }))),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

test("shows every service running when the health check passes", async () => {
  mockFetch(200, { status: "ok", database: "ok", redis: "ok" });
  renderApp();

  expect(await screen.findAllByText("Running")).toHaveLength(3);
});

test("shows which service is down when the health check is 503", async () => {
  mockFetch(503, { status: "error", database: "ok", redis: "error" });
  renderApp();

  expect(await screen.findByText("Not reachable")).toBeInTheDocument();
  expect(screen.getAllByText("Running")).toHaveLength(2);
});

test("tells the person how to start the backend when it does not answer", async () => {
  mockFetch(502, "Bad Gateway");
  renderApp();

  expect(await screen.findByRole("alert")).toHaveTextContent("docker compose up -d");
});
