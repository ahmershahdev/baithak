import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { meetsRules, RULES } from "./passwords";
import { renderAt } from "./test/render";
import { fakeBackend, json } from "./test/server";

const signedOut = { "GET /api/v1/auth/me/": () => new Response(null, { status: 204 }) };

describe("password rules", () => {
  test.each([
    ["Chai-At-Four-42", true],
    ["chai-at-four-42", false],
    ["CHAI-AT-FOUR-42", false],
    ["Chai-At-Four-x2", false],
    ["ChaiAtFour4242", false],
    ["Ch-4a", false],
  ])("%s meets every rule: %s", (password, expected) => {
    expect(meetsRules(password)).toBe(expected);
  });

  test("the checklist ticks rules off as they are met", async () => {
    fakeBackend(signedOut);
    renderAt("/signup");

    await userEvent.type(await screen.findByLabelText("Password"), "Chai-At-Four-42");

    const list = screen.getByRole("list", { name: "Password rules" });
    expect(within(list).getAllByText(/: done$/)).toHaveLength(RULES.length);
  });

  test("a password that misses a rule is never sent", async () => {
    const backend = fakeBackend(signedOut);
    renderAt("/signup");

    await userEvent.type(await screen.findByLabelText("Email"), "amna@example.com");
    await userEvent.type(screen.getByLabelText("Handle"), "amna");
    await userEvent.type(screen.getByLabelText("Password"), "weakpassword");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Meet every rule below first.")).toBeInTheDocument();
    expect(backend.requests.some((r) => r.url.endsWith("/signup/"))).toBe(false);
  });
});

describe("live availability", () => {
  test("a taken handle and a free email are shown as they are typed", async () => {
    fakeBackend({
      ...signedOut,
      "POST /api/v1/auth/availability/": async (request) => {
        const body = (await request.json()) as { email?: string; username?: string };
        return json(
          200,
          body.username
            ? { username: { available: false, message: "This handle is taken." } }
            : { email: { available: true, message: "" } },
        );
      },
    });
    renderAt("/signup");

    await userEvent.type(await screen.findByLabelText("Handle"), "amna");
    await userEvent.type(screen.getByLabelText("Email"), "new@example.com");

    expect(await screen.findByText("This handle is taken.")).toBeInTheDocument();
    expect(await screen.findByText("Available")).toBeInTheDocument();
    expect(screen.getByLabelText("Handle")).toHaveAttribute("aria-invalid", "true");
  });
});

describe("captcha", () => {
  test("the checkbox is on the form from the start when a v2 key is set", async () => {
    const render = vi.fn(() => 0);
    vi.stubGlobal("grecaptcha", {
      ready: (callback: () => void) => {
        callback();
      },
      execute: vi.fn(() => Promise.resolve("v3")),
      render,
      reset: vi.fn(),
    });
    fakeBackend({
      ...signedOut,
      "GET /api/v1/auth/config/": () =>
        json(200, { recaptcha_v3_site_key: "v3-site", recaptcha_v2_site_key: "v2-site" }),
    });
    renderAt("/signin");

    await waitFor(() => {
      expect(render).toHaveBeenCalledWith(
        expect.any(HTMLElement),
        expect.objectContaining({ sitekey: "v2-site" }),
      );
    });
    expect(screen.getByText(/Protected by reCAPTCHA/)).toBeInTheDocument();
  });
});

describe("contact", () => {
  test("a message is sent and thanked", async () => {
    const backend = fakeBackend({
      ...signedOut,
      "POST /api/v1/contact/": () => json(202, { detail: "Thank you." }),
    });
    renderAt("/contact");

    await userEvent.type(await screen.findByLabelText("Your name"), "Chanda");
    await userEvent.type(screen.getByLabelText("Email"), "chanda@example.com");
    await userEvent.type(screen.getByLabelText("Message"), "Can we self-host Baithak?");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));

    expect(await screen.findByRole("heading", { name: "Thank you" })).toBeInTheDocument();
    const sent = backend.requests.find((r) => r.url.endsWith("/contact/"));
    expect(await sent?.json()).toMatchObject({
      name: "Chanda",
      email: "chanda@example.com",
      message: "Can we self-host Baithak?",
      website: "",
    });
  });

  test("every sign-in page links to contact and support", async () => {
    fakeBackend(signedOut);
    renderAt("/signin");

    expect(await screen.findByRole("link", { name: "Contact" })).toHaveAttribute(
      "href",
      "/contact",
    );
    expect(screen.getByRole("link", { name: "support@ahmershah.dev" })).toHaveAttribute(
      "href",
      "mailto:support@ahmershah.dev",
    );
  });
});
