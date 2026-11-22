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

test("an admin connects a repository and sees the secret once", async () => {
  const hook = {
    id: 3,
    kind: "github",
    channel: 5,
    repo: "team/app",
    url: "https://baithak.test/api/v1/hooks/github/tok/",
    created_by: null,
    created_at: "2026-11-22T10:00:00Z",
  };
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
      hooks = [hook];
      return json(201, { ...hook, secret: "s3cret-value" });
    },
  });
  renderAt("/w/team/settings");

  const form = await screen.findByRole("form", { name: "Connect a repository" });
  await userEvent.type(within(form).getByLabelText("Repository"), "team/app");
  await waitFor(() => {
    expect(within(form).getByRole("combobox", { name: "Channel" })).toHaveTextContent("#general");
  });
  await userEvent.click(within(form).getByRole("button", { name: "Connect" }));

  const shown = await screen.findByRole("status");
  expect(shown).toHaveTextContent("s3cret-value");
  expect(shown).toHaveTextContent("https://baithak.test/api/v1/hooks/github/tok/");
  expect(sent).toEqual([{ kind: "github", channel_id: 5, repo: "team/app" }]);
  const list = await screen.findByRole("list", { name: "Connected repositories" });
  expect(list).toHaveTextContent("team/app to #general");
});
