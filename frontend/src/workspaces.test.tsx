import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test } from "vitest";

import type { User } from "./api/client";
import type { Invitation, Member, Workspace } from "./api/workspaces";
import { safePath } from "./next";
import { renderAt } from "./test/render";
import { fakeBackend, json } from "./test/server";

const amna: User = {
  id: 1,
  email: "amna@example.com",
  username: "amna",
  display_name: "Amna Khan",
  email_verified: true,
};

const team = (role: Workspace["role"] = "admin"): Workspace => ({
  slug: "karachi-team",
  name: "Karachi Team",
  created_at: "2026-11-01T10:00:00Z",
  role,
});

const people: Member[] = [
  {
    user_id: 1,
    username: "amna",
    display_name: "Amna Khan",
    role: "admin",
    joined_at: "2026-11-01T10:00:00Z",
  },
  {
    user_id: 2,
    username: "bilal",
    display_name: "Bilal",
    role: "member",
    joined_at: "2026-11-02T10:00:00Z",
  },
  {
    user_id: 3,
    username: "sana",
    display_name: "Sana",
    role: "owner",
    joined_at: "2026-11-01T09:00:00Z",
  },
];

function inWorkspace(
  role: Workspace["role"] = "admin",
  extra: Record<string, (r: Request) => Response> = {},
) {
  return fakeBackend({
    "GET /api/v1/auth/me/": () => json(200, amna),
    "GET /api/v1/workspaces/": () => json(200, [team(role)]),
    "GET /api/v1/workspaces/karachi-team/": () => json(200, team(role)),
    "GET /api/v1/workspaces/karachi-team/members/": () => json(200, people),
    ...extra,
  });
}

describe("home", () => {
  test("opens the workspace when there is one", async () => {
    inWorkspace();
    renderAt("/");

    expect(await screen.findByRole("heading", { name: "Karachi Team" })).toBeInTheDocument();
    expect(await screen.findByText(/3 people sit in this room/)).toBeInTheDocument();
  });

  test("without a workspace, creating one opens it", async () => {
    let created = false;
    const backend = fakeBackend({
      "GET /api/v1/auth/me/": () => json(200, amna),
      "GET /api/v1/workspaces/": () => json(200, created ? [team("owner")] : []),
      "POST /api/v1/workspaces/": () => {
        created = true;
        return json(201, team("owner"));
      },
      "GET /api/v1/workspaces/karachi-team/": () => json(200, team("owner")),
      "GET /api/v1/workspaces/karachi-team/members/": () => json(200, people),
    });
    renderAt("/");

    await userEvent.type(await screen.findByLabelText("Workspace name"), "Karachi Team");
    await userEvent.click(screen.getByRole("button", { name: "Create workspace" }));

    expect(await screen.findByRole("heading", { name: "Karachi Team" })).toBeInTheDocument();
    const post = backend.requests.find(
      (r) => r.method === "POST" && r.url.endsWith("/workspaces/"),
    );
    expect(await post?.json()).toEqual({ name: "Karachi Team" });
  });

  test("an unconfirmed email can't create a workspace yet", async () => {
    fakeBackend({ "GET /api/v1/auth/me/": () => json(200, { ...amna, email_verified: false }) });
    renderAt("/");

    expect(await screen.findByLabelText("Workspace name")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Create workspace" })).toBeDisabled();
    expect(
      screen.getByText("Confirm your email to create or join a workspace."),
    ).toBeInTheDocument();
  });

  test("a workspace you are not in sends you home", async () => {
    fakeBackend({
      "GET /api/v1/auth/me/": () => json(200, amna),
      "GET /api/v1/workspaces/secret/": () => json(404, { detail: "Not found." }),
    });
    renderAt("/w/secret");

    expect(await screen.findByRole("heading", { name: "Welcome, Amna Khan" })).toBeInTheDocument();
  });

  test("signed out, a workspace page goes to sign in", async () => {
    fakeBackend({ "GET /api/v1/auth/me/": () => json(403, {}) });
    renderAt("/w/karachi-team/members");

    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
  });
});

describe("members", () => {
  test("an admin changes a member's role", async () => {
    const backend = inWorkspace("admin", {
      "PATCH /api/v1/workspaces/karachi-team/members/2/": () =>
        json(200, { ...people[1], role: "admin" }),
    });
    renderAt("/w/karachi-team/members");

    await userEvent.selectOptions(await screen.findByLabelText("Role of Bilal"), "admin");

    await waitFor(() => {
      expect(backend.requests.some((r) => r.method === "PATCH")).toBe(true);
    });
    const patch = backend.requests.find((r) => r.method === "PATCH");
    expect(await patch?.json()).toEqual({ role: "admin" });
  });

  test("an admin can't touch the owner and can't offer the owner role", async () => {
    inWorkspace("admin");
    renderAt("/w/karachi-team/members");

    const roleOfBilal = await screen.findByLabelText("Role of Bilal");
    expect(within(roleOfBilal).queryByRole("option", { name: "Owner" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Role of Sana")).not.toBeInTheDocument();
  });

  test("removing someone asks once more first", async () => {
    const backend = inWorkspace("admin", {
      "DELETE /api/v1/workspaces/karachi-team/members/2/": () =>
        new Response(null, { status: 204 }),
    });
    renderAt("/w/karachi-team/members");

    const row = (await screen.findByText("Bilal")).closest("li") as HTMLElement;
    await userEvent.click(within(row).getByRole("button", { name: "Remove" }));
    expect(backend.requests.some((r) => r.method === "DELETE")).toBe(false);
    await userEvent.click(within(row).getByRole("button", { name: "Yes, remove Bilal" }));

    await waitFor(() => {
      expect(backend.requests.some((r) => r.method === "DELETE")).toBe(true);
    });
  });

  test("the API's refusal is shown on the row", async () => {
    inWorkspace("admin", {
      "PATCH /api/v1/workspaces/karachi-team/members/2/": () =>
        json(403, { detail: "You can't give this person that role." }),
    });
    renderAt("/w/karachi-team/members");

    await userEvent.selectOptions(await screen.findByLabelText("Role of Bilal"), "guest");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You can't give this person that role.",
    );
  });

  test("members see no admin pages in the menu", async () => {
    inWorkspace("member");
    renderAt("/w/karachi-team");

    await screen.findByRole("heading", { name: "Karachi Team" });
    const nav = screen.getByRole("navigation", { name: "Workspace" });
    expect(within(nav).getByRole("link", { name: "Members" })).toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Invitations" })).not.toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Audit log" })).not.toBeInTheDocument();
  });
});

describe("invitations", () => {
  const pending: Invitation = {
    id: 7,
    email: "chanda@example.com",
    role: "member",
    invited_by: "amna",
    created_at: "2026-11-10T10:00:00Z",
    expires_at: "2099-11-17T10:00:00Z",
  };

  test("an admin invites someone and sees it waiting", async () => {
    let sent: Invitation[] = [];
    const backend = inWorkspace("admin", {
      "GET /api/v1/workspaces/karachi-team/invitations/": () => json(200, sent),
      "POST /api/v1/workspaces/karachi-team/invitations/": () => {
        sent = [pending];
        return json(201, pending);
      },
    });
    renderAt("/w/karachi-team/invitations");

    await userEvent.type(await screen.findByLabelText("Email"), "chanda@example.com");
    await userEvent.selectOptions(screen.getByLabelText("Role"), "member");
    await userEvent.click(screen.getByRole("button", { name: "Send invitation" }));

    expect(await screen.findByText("Invitation sent to chanda@example.com.")).toBeInTheDocument();
    expect(await screen.findByText("chanda@example.com")).toBeInTheDocument();
    const post = backend.requests.find(
      (r) => r.method === "POST" && r.url.endsWith("/invitations/"),
    );
    expect(await post?.json()).toEqual({ email: "chanda@example.com", role: "member" });
  });

  test("revoking asks once more, then sends the delete", async () => {
    const backend = inWorkspace("admin", {
      "GET /api/v1/workspaces/karachi-team/invitations/": () => json(200, [pending]),
      "DELETE /api/v1/workspaces/karachi-team/invitations/7/": () =>
        new Response(null, { status: 204 }),
    });
    renderAt("/w/karachi-team/invitations");

    await userEvent.click(await screen.findByRole("button", { name: "Revoke" }));
    await userEvent.click(screen.getByRole("button", { name: "Yes, revoke" }));

    await waitFor(() => {
      expect(backend.requests.some((r) => r.method === "DELETE")).toBe(true);
    });
  });
});

describe("audit log", () => {
  test("shows events and loads older ones with the cursor", async () => {
    const backend = inWorkspace("owner", {
      "GET /api/v1/workspaces/karachi-team/audit/": (request) =>
        new URL(request.url).searchParams.get("cursor") === "older"
          ? json(200, {
              next: null,
              previous: null,
              results: [
                {
                  id: 1,
                  actor: "sana",
                  action: "workspace.create",
                  model: "workspace",
                  object_id: "1",
                  changes: { name: "Karachi Team" },
                  at: "2026-11-01T09:00:00Z",
                },
              ],
            })
          : json(200, {
              next: "http://testserver/api/v1/workspaces/karachi-team/audit/?cursor=older",
              previous: null,
              results: [
                {
                  id: 2,
                  actor: "amna",
                  action: "member.update",
                  model: "member",
                  object_id: "2",
                  changes: { role: ["member", "admin"] },
                  at: "2026-11-02T09:00:00Z",
                },
              ],
            }),
    });
    renderAt("/w/karachi-team/audit");

    expect(await screen.findByText("changed a role")).toBeInTheDocument();
    expect(screen.getByText("role: member → admin")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show older" }));

    expect(await screen.findByText("created the workspace")).toBeInTheDocument();
    expect(backend.requests.some((r) => r.url.includes("cursor=older"))).toBe(true);
  });
});

describe("invitation link", () => {
  const preview = {
    workspace: "Karachi Team",
    role: "member",
    invited_by: "sana",
    email: "a***@example.com",
  };

  test("signed out, it explains and links to sign in that comes back here", async () => {
    fakeBackend({
      "GET /api/v1/auth/me/": () => json(403, {}),
      "POST /api/v1/invitations/preview/": () => json(200, preview),
    });
    renderAt("/invite?token=tok-123");

    expect(await screen.findByRole("heading", { name: "Join Karachi Team" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute(
      "href",
      `/signin?next=${encodeURIComponent("/invite?token=tok-123")}`,
    );
  });

  test("signed in, accepting opens the workspace", async () => {
    let joined = false;
    const backend = fakeBackend({
      "GET /api/v1/auth/me/": () => json(200, amna),
      "POST /api/v1/invitations/preview/": () => json(200, preview),
      "POST /api/v1/invitations/accept/": () => {
        joined = true;
        return json(200, team("member"));
      },
      "GET /api/v1/workspaces/": () => json(200, joined ? [team("member")] : []),
      "GET /api/v1/workspaces/karachi-team/": () => json(200, team("member")),
      "GET /api/v1/workspaces/karachi-team/members/": () => json(200, people),
    });
    renderAt("/invite?token=tok-123");

    await userEvent.click(await screen.findByRole("button", { name: "Accept and join" }));

    expect(await screen.findByRole("heading", { name: "Karachi Team" })).toBeInTheDocument();
    const accept = backend.requests.find((r) => r.url.endsWith("/accept/"));
    expect(await accept?.json()).toEqual({ token: "tok-123" });
  });

  test("the wrong account sees why", async () => {
    fakeBackend({
      "GET /api/v1/auth/me/": () => json(200, amna),
      "POST /api/v1/invitations/preview/": () => json(200, preview),
      "POST /api/v1/invitations/accept/": () =>
        json(403, { detail: "This invitation was sent to another email address." }),
    });
    renderAt("/invite?token=tok-123");

    await userEvent.click(await screen.findByRole("button", { name: "Accept and join" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("sent to another email address");
  });

  test("a used or expired link says it has closed", async () => {
    fakeBackend({
      "GET /api/v1/auth/me/": () => json(403, {}),
      "POST /api/v1/invitations/preview/": () => json(404, { detail: "gone" }),
    });
    renderAt("/invite?token=used");

    expect(
      await screen.findByRole("heading", { name: "This invitation has closed" }),
    ).toBeInTheDocument();
  });

  test("signing in from the invitation comes back to it", async () => {
    fakeBackend({
      "GET /api/v1/auth/me/": () => json(403, {}),
      "POST /api/v1/auth/signin/": () => json(200, amna),
      "POST /api/v1/invitations/preview/": () => json(200, preview),
    });
    renderAt(`/signin?next=${encodeURIComponent("/invite?token=tok-123")}`);

    await userEvent.type(await screen.findByLabelText("Email"), "amna@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "a-long-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("button", { name: "Accept and join" })).toBeInTheDocument();
  });
});

describe("safe return paths", () => {
  test.each([
    ["/invite?token=x", "/invite?token=x"],
    ["//evil.example", null],
    ["/\\evil.example", null],
    ["https://evil.example", null],
    ["", null],
    [null, null],
  ])("%s gives %s", (value, expected) => {
    expect(safePath(value)).toBe(expected);
  });
});
