import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

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

const signedOut = { "GET /api/v1/auth/me/": () => new Response(null, { status: 204 }) };

describe("home", () => {
  test("sends a signed-out visitor to sign in", async () => {
    fakeBackend(signedOut);
    renderAt("/");

    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
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
      "GET /api/v1/auth/me/": () =>
        signedIn ? json(200, amna) : new Response(null, { status: 204 }),
      "POST /api/v1/auth/signout/": () => {
        signedIn = false;
        return new Response(null, { status: 204 });
      },
    });
    renderAt("/");

    await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
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
    await userEvent.type(screen.getByLabelText("Password"), "Chai-At-Four-42");
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
    await userEvent.type(screen.getByLabelText("Password"), "Chai-At-Four-42");
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
    await userEvent.click(screen.getByRole("button", { name: "Send me a code" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "If who@example.com has an account",
    );
  });

  test("a new password is saved from the reset link", async () => {
    const backend = fakeBackend({
      "POST /api/v1/auth/password-reset/confirm/": () => new Response(null, { status: 204 }),
    });
    renderAt("/reset-password?uid=MQ&code=123456");

    expect(await screen.findByLabelText("Code")).toHaveValue("123456");
    await userEvent.type(screen.getByLabelText("New password"), "Lamp-Lit-Room-77");
    await userEvent.click(screen.getByRole("button", { name: "Save password" }));

    expect(await screen.findByRole("heading", { name: "Password changed" })).toBeInTheDocument();
    const confirm = backend.requests.find((r) => r.url.endsWith("/confirm/"));
    expect(await confirm?.json()).toEqual({
      uid: "MQ",
      code: "123456",
      password: "Lamp-Lit-Room-77",
    });
  });
});

describe("password field", () => {
  test("the curtain button shows and hides the password", async () => {
    fakeBackend(signedOut);
    renderAt("/signin");

    const password = await screen.findByLabelText("Password");
    expect(password).toHaveAttribute("type", "password");

    await userEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(password).toHaveAttribute("type", "text");

    await userEvent.click(screen.getByRole("button", { name: "Hide password" }));
    expect(password).toHaveAttribute("type", "password");
  });

  test("sign up rates the password as it is typed", async () => {
    fakeBackend(signedOut);
    renderAt("/signup");

    const password = await screen.findByLabelText("Password");
    await userEvent.type(password, "password1");
    expect(
      await screen.findByText(
        /Password strength: (Too easy to guess|Weak)\./,
        {},
        { timeout: 5000 },
      ),
    ).toBeInTheDocument();

    await userEvent.clear(password);
    await userEvent.type(password, "copper-lantern-mango-river-71");
    expect(
      await screen.findByText("Password strength: Strong.", {}, { timeout: 5000 }),
    ).toBeInTheDocument();
  });

  test("a password made from the handle scores low", async () => {
    fakeBackend(signedOut);
    renderAt("/signup");

    await userEvent.type(await screen.findByLabelText("Handle"), "zarqawi_basharat");
    await userEvent.type(screen.getByLabelText("Password"), "zarqawi_basharat");

    expect(
      await screen.findByText(
        /Password strength: (Too easy to guess|Weak)\./,
        {},
        { timeout: 5000 },
      ),
    ).toBeInTheDocument();
  });
});

describe("bot checks", () => {
  test("the honeypot is out of reach and sent empty", async () => {
    const backend = fakeBackend({
      ...signedOut,
      "POST /api/v1/auth/signin/": () => json(200, amna),
    });
    const { container } = renderAt("/signin");
    const email = await screen.findByLabelText("Email");

    const trap = container.querySelector<HTMLInputElement>('input[name="website"]');
    expect(trap).not.toBeNull();
    expect(trap).toHaveAttribute("tabindex", "-1");
    expect(screen.queryByRole("textbox", { name: "Website" })).not.toBeInTheDocument();

    await userEvent.type(email, "amna@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "Chai-At-Four-42");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await screen.findByRole("heading", { name: "Welcome, Amna Khan" });

    const sent = backend.requests.find((r) => r.url.endsWith("/signin/"));
    expect(await sent?.json()).toMatchObject({ website: "" });
  });

  test("when the API doubts, the checkbox appears and its token is sent next time", async () => {
    let attempts = 0;
    const backend = fakeBackend({
      ...signedOut,
      "GET /api/v1/auth/config/": () =>
        json(200, { recaptcha_v3_site_key: "v3-site", recaptcha_v2_site_key: "v2-site" }),
      "POST /api/v1/auth/signin/": () => {
        attempts += 1;
        return attempts === 1
          ? json(400, { detail: "Please confirm you are a person.", captcha: "v2" })
          : json(200, amna);
      },
    });
    let solve: (token: string) => void = () => undefined;
    const grecaptcha = {
      ready: (callback: () => void) => {
        callback();
      },
      execute: vi.fn(() => Promise.resolve("v3-token")),
      render: vi.fn((_box: HTMLElement, options: { callback: (token: string) => void }) => {
        solve = options.callback;
        return 0;
      }),
      reset: vi.fn(),
    };
    vi.stubGlobal("grecaptcha", grecaptcha);
    renderAt("/signin");

    await userEvent.type(await screen.findByLabelText("Email"), "amna@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "Chai-At-Four-42");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Please confirm you are a person.");
    // Drawn only once its box is visible, and in the page's theme.
    await waitFor(() => {
      expect(grecaptcha.render).toHaveBeenCalledWith(
        expect.any(HTMLElement),
        expect.objectContaining({ sitekey: "v2-site", theme: "light" }),
      );
    });
    const box = vi.mocked(grecaptcha.render).mock.calls[0]?.[0];
    expect(box?.closest(".hidden")).toBeNull();
    expect(screen.getByText(/tick the box/)).toBeInTheDocument();
    act(() => {
      solve("v2-token");
    });
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Welcome, Amna Khan" })).toBeInTheDocument();
    const [first, second] = backend.requests.filter((r) => r.url.endsWith("/signin/"));
    expect(await first?.json()).toMatchObject({ captcha: "v3-token" });
    expect(await second?.json()).toMatchObject({ captcha_v2: "v2-token" });
    // A checkbox token works once at Google, so the box is unticked as soon as it is used.
    expect(grecaptcha.reset).toHaveBeenCalledWith(0);
  });
});

describe("privacy", () => {
  test("is open to signed-out visitors and covers reCAPTCHA, Resend and deletion", async () => {
    fakeBackend(signedOut);
    renderAt("/privacy");

    expect(await screen.findByRole("heading", { name: "Privacy" })).toBeInTheDocument();
    expect(screen.getByText(/Google receives details/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Resend" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Deleting your account" })).toBeInTheDocument();
  });

  test("has a breadcrumb, a table of contents and the contact form's retention", async () => {
    fakeBackend(signedOut);
    renderAt("/privacy");

    const trail = await screen.findByRole("navigation", { name: "Breadcrumb" });
    expect(within(trail).getByRole("link", { name: "Baithak" })).toHaveAttribute("href", "/");
    expect(within(trail).getByText("Privacy")).toHaveAttribute("aria-current", "page");
    const contents = screen.getByRole("navigation", { name: "On this page" });
    expect(
      within(contents).getByRole("link", { name: "Cookies and browser storage" }),
    ).toHaveAttribute("href", "#cookies");
    expect(screen.getByRole("rowheader", { name: "Contact form messages" })).toBeInTheDocument();
  });

  test("the contact page has a breadcrumb back home", async () => {
    fakeBackend(signedOut);
    renderAt("/contact");

    const trail = await screen.findByRole("navigation", { name: "Breadcrumb" });
    expect(within(trail).getByRole("link", { name: "Baithak" })).toHaveAttribute("href", "/");
    expect(within(trail).getByText("Contact")).toHaveAttribute("aria-current", "page");
  });

  test("is linked from the sign-in page", async () => {
    fakeBackend(signedOut);
    renderAt("/signin");

    expect(await screen.findByRole("link", { name: "Privacy" })).toHaveAttribute(
      "href",
      "/privacy",
    );
  });
});
