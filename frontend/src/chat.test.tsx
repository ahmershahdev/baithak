import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

import type { Channel } from "./api/chat";
import type { User } from "./api/client";
import type { Message } from "./chat/timeline";
import { FakeSocket } from "./test/fakeSocket";
import { renderAt } from "./test/render";
import { fakeBackend, json } from "./test/server";

const amna: User = {
  id: 1,
  email: "amna@example.com",
  username: "amna",
  display_name: "Amna Khan",
  email_verified: true,
};

const general: Channel = {
  id: 5,
  name: "general",
  kind: "public",
  topic: "Say hello",
  is_default: true,
  archived: false,
  is_member: true,
  last_seq: 2,
  created_at: "2026-11-01T10:00:00Z",
};

function message(seq: number, event: number, body: string, clientId = ""): Message {
  return {
    id: seq,
    seq,
    event,
    author: { id: seq % 2 ? 1 : 2, username: seq % 2 ? "amna" : "bilal", display_name: "" },
    body,
    client_id: clientId,
    created_at: `2026-11-17T10:0${String(seq)}:00Z`,
    edited_at: null,
    deleted: false,
  };
}

const page = (messages: Message[], lastEvent: number, hasMore = false) => ({
  messages,
  has_more: hasMore,
  last_seq: messages.at(-1)?.seq ?? 0,
  last_event: lastEvent,
});

function backend(
  messageRoutes: Record<string, (request: Request) => Response | Promise<Response>>,
) {
  return fakeBackend({
    "GET /api/v1/auth/me/": () => json(200, amna),
    "GET /api/v1/workspaces/": () =>
      json(200, [
        { slug: "team", name: "Team", created_at: "2026-11-01T10:00:00Z", role: "member" },
      ]),
    "GET /api/v1/workspaces/team/": () =>
      json(200, { slug: "team", name: "Team", created_at: "2026-11-01T10:00:00Z", role: "member" }),
    "GET /api/v1/workspaces/team/channels/": () => json(200, [general]),
    ...messageRoutes,
  });
}

async function openChannel() {
  renderAt("/w/team/c/5");
  await waitFor(() => {
    expect(FakeSocket.all.length).toBeGreaterThan(0);
  });
  act(() => {
    FakeSocket.latest().open();
  });
}

function live(event: number, body: Message) {
  act(() => {
    FakeSocket.latest().receive({ type: "message", channel: 5, event, message: body });
  });
}

beforeEach(() => {
  FakeSocket.all = [];
  vi.stubGlobal("WebSocket", FakeSocket);
});

describe("a channel", () => {
  test("shows history and new messages as they arrive", async () => {
    backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": () =>
        json(200, page([message(1, 1, "Salaam"), message(2, 2, "Walaikum salaam")], 2)),
    });
    await openChannel();

    expect(await screen.findByText("Walaikum salaam")).toBeInTheDocument();
    live(3, message(3, 3, "Chai at four?"));

    expect(await screen.findByText("Chai at four?")).toBeInTheDocument();
  });

  test("after a dropped socket nothing is lost and nothing is shown twice", async () => {
    const asked: string[] = [];
    const backendState = backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": (request) => {
        const after = new URL(request.url).searchParams.get("after_event");
        if (after === null) return json(200, page([message(1, 1, "one"), message(2, 2, "two")], 2));
        asked.push(after);
        if (after === "3")
          return json(200, page([message(1, 4, "one, edited"), message(4, 5, "four")], 5));
        return json(
          200,
          page([message(5, 6, "five"), message(6, 7, "six"), message(7, 8, "seven")], 8),
        );
      },
    });
    await openChannel();
    await screen.findByText("two");
    live(3, message(3, 3, "three"));
    await screen.findByText("three");

    // The socket drops. While it is down, message 1 is edited and message 4 is sent.
    act(() => {
      FakeSocket.latest().drop();
    });
    expect(await screen.findByText(/Reconnecting/)).toBeInTheDocument();
    await waitFor(
      () => {
        expect(FakeSocket.all).toHaveLength(2);
      },
      { timeout: 2_500 },
    );
    act(() => {
      FakeSocket.latest().open();
    });

    expect(await screen.findByText("one, edited")).toBeInTheDocument();
    expect(await screen.findByText("four")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText(/Reconnecting/)).not.toBeInTheDocument();
    });

    // The same event again (a late duplicate) changes nothing.
    live(5, message(4, 5, "four"));
    expect(screen.getAllByText("four")).toHaveLength(1);

    // Event 8 arrives but 6 and 7 never did: a gap, so the tab catches up instead of guessing.
    live(8, message(7, 8, "seven"));
    expect(await screen.findByText("five")).toBeInTheDocument();
    expect(screen.getByText("six")).toBeInTheDocument();
    expect(screen.getAllByText("seven")).toHaveLength(1);
    expect(screen.getAllByText("three")).toHaveLength(1);
    expect(asked).toEqual(["3", "5"]);
    expect(backendState.requests.length).toBeGreaterThan(0);
  });

  test("a sent message shows at once and appears once, whatever arrives first", async () => {
    let sent: Message | null = null;
    const backendState = backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": () => json(200, page([], 0)),
      "POST /api/v1/workspaces/team/channels/5/messages/": async (request) => {
        const body = (await request.json()) as { body: string; client_id: string };
        sent = message(1, 1, body.body, body.client_id);
        return json(201, sent);
      },
    });
    await openChannel();
    await screen.findByText(/This is the very start of #general/);

    await userEvent.type(screen.getByLabelText("Message #general"), "Salaam{Enter}");

    expect(await screen.findByText("Salaam")).toBeInTheDocument();
    await waitFor(() => {
      expect(sent).not.toBeNull();
    });
    live(1, sent as unknown as Message);
    expect(screen.getAllByText("Salaam")).toHaveLength(1);
    expect(screen.queryByText("Sending")).not.toBeInTheDocument();
    expect(backendState.requests.filter((r) => r.method === "POST")).toHaveLength(1);
    expect((sent as unknown as Message).client_id).toMatch(/^[\w-]{36}$/);
  });

  test("a failed send can be retried with the same id, so it is stored once", async () => {
    const ids: string[] = [];
    let fail = true;
    backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": () => json(200, page([], 0)),
      "POST /api/v1/workspaces/team/channels/5/messages/": async (request) => {
        const body = (await request.json()) as { body: string; client_id: string };
        ids.push(body.client_id);
        if (fail) return json(503, { detail: "Down" });
        return json(201, message(1, 1, body.body, body.client_id));
      },
    });
    await openChannel();
    await screen.findByText(/This is the very start/);

    await userEvent.type(screen.getByLabelText("Message #general"), "Hello{Enter}");
    fail = false;
    await userEvent.click(await screen.findByRole("button", { name: "Not sent. Retry" }));

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Not sent. Retry" })).not.toBeInTheDocument();
    });
    expect(ids).toHaveLength(2);
    expect(ids[0]).toBe(ids[1]);
  });

  test("Shift+Enter makes a new line instead of sending", async () => {
    const backendState = backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": () => json(200, page([], 0)),
    });
    await openChannel();
    const composer = await screen.findByLabelText("Message #general");

    await userEvent.type(composer, "line one{Shift>}{Enter}{/Shift}line two");

    expect(composer).toHaveValue("line one\nline two");
    expect(backendState.requests.some((r) => r.method === "POST")).toBe(false);
  });

  test("a channel you have not joined can be read, with a join button instead of a composer", async () => {
    fakeBackend({
      "GET /api/v1/auth/me/": () => json(200, amna),
      "GET /api/v1/workspaces/team/": () =>
        json(200, {
          slug: "team",
          name: "Team",
          created_at: "2026-11-01T10:00:00Z",
          role: "member",
        }),
      "GET /api/v1/workspaces/team/channels/": () => json(200, [{ ...general, is_member: false }]),
      "GET /api/v1/workspaces/team/channels/5/messages/": () =>
        json(200, page([message(1, 1, "Public words")], 1)),
    });
    await openChannel();

    expect(await screen.findByText("Public words")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Join #general" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Message #general")).not.toBeInTheDocument();
  });

  test("a channel you can't see says so without telling which", async () => {
    backend({});
    renderAt("/w/team/c/999");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This channel does not exist, or it is private.",
    );
  });
});
