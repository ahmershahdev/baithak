import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import { FakeSocket } from "./test/fakeSocket";
import { renderAt } from "./test/render";
import { fakeBackend, json } from "./test/server";

const amna = {
  id: 1,
  email: "amna@example.com",
  username: "amna",
  display_name: "Amna Khan",
  email_verified: true,
  has_password: true,
};
const workspace = { slug: "team", name: "Team", created_at: "2026-11-01T10:00:00Z", role: "admin" };
const general = {
  id: 5,
  name: "general",
  kind: "public",
  topic: "",
  is_default: true,
  archived: false,
  is_member: true,
  last_seq: 0,
  last_read_seq: 0,
  unread: 0,
  people: [],
  created_at: "2026-11-01T10:00:00Z",
};

beforeEach(() => {
  FakeSocket.all = [];
  vi.stubGlobal("WebSocket", FakeSocket);
});

/** The settings page with one kind of webhook: what was sent to create it is returned. */
async function addWebhook(
  form: string,
  label: string,
  value: string,
  made: Record<string, unknown>,
) {
  let hooks: unknown[] = [];
  const sent: unknown[] = [];
  fakeBackend({
    "GET /api/v1/auth/me/": () => json(200, amna),
    "GET /api/v1/workspaces/": () => json(200, [workspace]),
    "GET /api/v1/workspaces/team/": () => json(200, workspace),
    "GET /api/v1/workspaces/team/channels/": () => json(200, [general]),
    "GET /api/v1/workspaces/team/integrations/webhooks/": () => json(200, hooks),
    "POST /api/v1/workspaces/team/integrations/webhooks/": async (request) => {
      sent.push(await request.json());
      hooks = [{ ...made, secret: undefined }];
      return json(201, made);
    },
  });
  renderAt("/w/team/settings");

  const box = await screen.findByRole("form", { name: form });
  await userEvent.type(within(box).getByLabelText(label), value);
  await waitFor(() => {
    expect(within(box).getByRole("combobox", { name: "Channel" })).toHaveTextContent("#general");
  });
  await userEvent.click(within(box).getByRole("button", { name: "Add" }));
  return sent;
}

const base = {
  id: 3,
  channel: 5,
  repo: "",
  name: "",
  created_by: null,
  created_at: "2026-11-22T10:00:00Z",
};

test("an admin connects a repository and sees the secret once", async () => {
  const url = "https://baithak.test/api/v1/hooks/github/tok/";
  const sent = await addWebhook("GitHub", "Repository", "team/app", {
    ...base,
    kind: "github",
    repo: "team/app",
    url,
    secret: "s3cret-value",
  });

  const shown = await screen.findByRole("status");
  expect(shown).toHaveTextContent("s3cret-value");
  expect(shown).toHaveTextContent(url);
  expect(sent).toEqual([{ kind: "github", channel_id: 5, repo: "team/app" }]);
  const list = await screen.findByRole("list", { name: "GitHub connected" });
  expect(list).toHaveTextContent("team/app to #general");
});

test("an admin makes an incoming webhook and sees its address once", async () => {
  const url = "https://baithak.test/api/v1/hooks/incoming/secret-token/";
  const sent = await addWebhook("Incoming webhooks", "Name", "Deploy bot", {
    ...base,
    kind: "incoming",
    name: "Deploy bot",
    url,
    secret: null,
  });

  const shown = await screen.findByRole("status");
  expect(shown).toHaveTextContent(url);
  expect(shown).toHaveTextContent("curl -X POST");
  expect(sent).toEqual([{ kind: "incoming", channel_id: 5, name: "Deploy bot" }]);
  const list = await screen.findByRole("list", { name: "Incoming webhooks connected" });
  expect(list).toHaveTextContent("Deploy bot to #general");
});

test("each webhook shows its latest deliveries and why", async () => {
  fakeBackend({
    "GET /api/v1/auth/me/": () => json(200, amna),
    "GET /api/v1/workspaces/": () => json(200, [workspace]),
    "GET /api/v1/workspaces/team/": () => json(200, workspace),
    "GET /api/v1/workspaces/team/channels/": () => json(200, [general]),
    "GET /api/v1/workspaces/team/integrations/webhooks/": () =>
      json(200, [{ ...base, kind: "github", repo: "team/app", url: "https://x.test/" }]),
    "GET /api/v1/workspaces/team/integrations/webhooks/3/deliveries/": () =>
      json(200, [
        {
          id: 2,
          event: "pull_request",
          status: "failed",
          detail: "OperationalError: gone away",
          attempts: 6,
          received_at: "2026-11-22T10:05:00Z",
          finished_at: "2026-11-22T12:00:00Z",
        },
        {
          id: 1,
          event: "push",
          status: "ignored",
          detail: "Not an event that is posted.",
          attempts: 0,
          received_at: "2026-11-22T10:00:00Z",
          finished_at: "2026-11-22T10:00:00Z",
        },
      ]),
  });
  renderAt("/w/team/settings");

  const list = await screen.findByRole("list", { name: "GitHub connected" });
  await userEvent.click(within(list).getByRole("button", { name: "Deliveries" }));

  const rows = within(await screen.findByRole("list", { name: "Deliveries" })).getAllByRole(
    "listitem",
  );
  expect(rows[0]).toHaveTextContent("Failedpull_requestOperationalError: gone away6 tries");
  expect(rows[1]).toHaveTextContent("IgnoredpushNot an event that is posted.");
});
