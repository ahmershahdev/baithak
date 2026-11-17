import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test } from "vitest";

import type { User } from "./api/client";
import { renderAt } from "./test/render";
import { fakeBackend, json } from "./test/server";

const amna: User = {
  id: 1,
  email: "amna@example.com",
  username: "amna",
  display_name: "Amna Khan",
  email_verified: true,
};

const signedOut = { "GET /api/v1/auth/me/": () => json(403, { detail: "Not signed in." }) };

describe("home", () => {
  test("sends a signed-out visitor to sign in", async () => {
    fakeBackend(signedOut);
    renderAt("/");

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  test("greets a signed-in person", async () => {
    fakeBackend({ "GET /api/v1/auth/me/": () => json(200, amna) });
    renderAt("/");

    expect(await screen.findByRole("heading", { name: "Welcome, Amna Khan" })).toBeInTheDocument();
  });

  test("asks an unverified person to confirm and can resend the link", async () => {
    const backend = fakeBackend({
      "GET /api/v1/auth/me/": () => json(200, { ...amna, email_verified: false }),
      "POST /api/v1/auth/verify-email/resend/": () => json(202, { detail: "ok" }),
    });
    renderAt("/");

    await userEvent.click(await screen.findByRole("button", { name: "Send the link again" }));

    expect(await screen.findByRole("status")).toHaveTextContent("A new link is on its way");
    expect(backend.requests.some((r) => r.url.endsWith("/verify-email/resend/"))).toBe(true);
  });

  test("signing out returns to sign in", async () => {
    let signedIn = true;
    fakeBackend({
      "GET /api/v1/auth/me/": () => (signedIn ? json(200, amna) : json(403, {})),
      "POST /api/v1/auth/signout/": () => {
        signedIn = false;
        return new Response(null, { status: 204 });
      },
    });
    renderAt("/");

    await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  test("says so when the backend does not answer", async () => {
    fakeBackend({ "GET /api/v1/auth/me/": () => json(502, {}) });
    renderAt("/");

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not reach Baithak");
  });
});

describe("sign in", () => {
  test("signs in and opens home, sending the CSRF token", async () => {
    const backend = fakeBackend({
      ...signedOut,
      "POST /api/v1/auth/signin/": () => json(200, amna),
    });
    renderAt("/signin");

    await userEvent.type(await screen.findByLabelText("Email"), "amna@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "a-long-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Welcome, Amna Khan" })).toBeInTheDocument();
    const signIn = backend.requests.find((r) => r.url.endsWith("/signin/"));
    expect(signIn?.headers.get("X-CSRFToken")).toBe("test-csrf-token");
  });

  test("shows the error from the API", async () => {
    fakeBackend({
      ...signedOut,
      "POST /api/v1/auth/signin/": () => json(400, { detail: "The email or password is wrong." }),
    });
    renderAt("/signin");

    await userEvent.type(await screen.findByLabelText("Email"), "amna@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "nope");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The email or password is wrong.");
  });

  test("a signed-in person is sent home", async () => {
    fakeBackend({ "GET /api/v1/auth/me/": () => json(200, amna) });
    renderAt("/signin");

    expect(await screen.findByRole("heading", { name: "Welcome, Amna Khan" })).toBeInTheDocument();
  });
});

describe("sign up", () => {
  async function fillAndSubmit() {
    await userEvent.type(await screen.findByLabelText("Email"), "amna@example.com");
    await userEvent.type(screen.getByLabelText("Handle"), "amna");
    await userEvent.type(screen.getByLabelText("Password"), "a-long-password");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  }

  test("asks the person to check their email", async () => {
    fakeBackend({ ...signedOut, "POST /api/v1/auth/signup/": () => json(202, { detail: "ok" }) });
    renderAt("/signup");

    await fillAndSubmit();

    expect(await screen.findByRole("heading", { name: "Check your email" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("amna@example.com");
  });

  test("shows field errors next to their field", async () => {
    fakeBackend({
      ...signedOut,
      "POST /api/v1/auth/signup/": () => json(400, { username: ["This handle is taken."] }),
    });
    renderAt("/signup");

    await fillAndSubmit();

    const handle = screen.getByLabelText("Handle");
    expect(await screen.findByText("This handle is taken.")).toBeInTheDocument();
    expect(handle).toHaveAttribute("aria-invalid", "true");
    expect(handle).toHaveAccessibleDescription(/This handle is taken\./);
  });
});

describe("email links", () => {
  test("confirming the email signs in", async () => {
    const backend = fakeBackend({
      "POST /api/v1/auth/verify-email/": () => json(200, amna),
      "GET /api/v1/auth/me/": () => json(200, amna),
    });
    renderAt("/verify-email?uid=MQ&token=abc-123");

    await userEvent.click(await screen.findByRole("button", { name: "Confirm email and sign in" }));

    expect(await screen.findByRole("heading", { name: "Welcome, Amna Khan" })).toBeInTheDocument();
    const verify = backend.requests.find((r) => r.url.endsWith("/verify-email/"));
    expect(await verify?.json()).toEqual({ uid: "MQ", token: "abc-123" });
  });

  test("a used link says so", async () => {
    fakeBackend({
      "POST /api/v1/auth/verify-email/": () =>
        json(400, { detail: "This link is not valid or has expired." }),
    });
    renderAt("/verify-email?uid=MQ&token=used");

    await userEvent.click(await screen.findByRole("button", { name: "Confirm email and sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("not valid or has expired");
  });

  test("a link without its code does not offer to confirm", () => {
    fakeBackend({});
    renderAt("/verify-email");

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("missing its code");
  });

  test("asking for a reset link always says the same thing", async () => {
    fakeBackend({ "POST /api/v1/auth/password-reset/": () => json(202, { detail: "ok" }) });
    renderAt("/forgot-password");

    await userEvent.type(await screen.findByLabelText("Email"), "who@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "If who@example.com has an account",
    );
  });

  test("a new password is saved from the reset link", async () => {
    const backend = fakeBackend({
      "POST /api/v1/auth/password-reset/confirm/": () => new Response(null, { status: 204 }),
    });
    renderAt("/reset-password?uid=MQ&token=abc");

    await userEvent.type(await screen.findByLabelText("New password"), "a-new-long-password");
    await userEvent.click(screen.getByRole("button", { name: "Save password" }));

    expect(await screen.findByRole("heading", { name: "Password changed" })).toBeInTheDocument();
    const confirm = backend.requests.find((r) => r.url.endsWith("/confirm/"));
    expect(await confirm?.json()).toEqual({
      uid: "MQ",
      token: "abc",
      password: "a-new-long-password",
    });
  });
});
