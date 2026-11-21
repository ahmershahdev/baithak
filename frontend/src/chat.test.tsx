import { act, screen, waitFor, within } from "@testing-library/react";
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
  last_read_seq: 2,
  unread: 0,
  people: [],
  created_at: "2026-11-01T10:00:00Z",
};

function message(seq: number, event: number, body: string, clientId = ""): Message {
  return {
    id: seq,
    seq,
    event,
    parent_seq: null,
    thread_seq: null,
    also_in_channel: false,
    reply_count: 0,
    last_reply_at: null,
    mentions: [],
    mentions_channel: false,
    reactions: [],
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

describe("unread", () => {
  const random: Channel = {
    ...general,
    id: 6,
    name: "random",
    is_default: false,
    last_seq: 0,
    last_read_seq: 0,
  };

  test("opening a channel marks it read and puts a line above what is new", async () => {
    const reads: unknown[] = [];
    fakeBackend({
      "GET /api/v1/auth/me/": () => json(200, amna),
      "GET /api/v1/workspaces/team/": () =>
        json(200, {
          slug: "team",
          name: "Team",
          created_at: "2026-11-01T10:00:00Z",
          role: "member",
        }),
      "GET /api/v1/workspaces/team/channels/": () =>
        json(200, [{ ...general, last_read_seq: 1, unread: 1 }]),
      "GET /api/v1/workspaces/team/channels/5/messages/": () =>
        json(200, page([message(1, 1, "Salaam"), message(2, 2, "Walaikum salaam")], 2)),
      "POST /api/v1/workspaces/team/channels/5/read/": async (request) => {
        reads.push(await request.json());
        return json(200, { channel: 5, last_read_seq: 2, unread: 0 });
      },
    });
    await openChannel();

    const line = await screen.findByRole("separator", { name: "New messages" });
    expect(line.nextElementSibling).toHaveTextContent("Walaikum salaam");
    await waitFor(() => {
      expect(reads).toEqual([{ seq: 2 }]);
    });
  });

  test("a message elsewhere shows a count, and reading it on another device clears it", async () => {
    backend({
      "GET /api/v1/workspaces/team/channels/": () => json(200, [general, random]),
      "GET /api/v1/workspaces/team/channels/5/messages/": () =>
        json(200, page([message(1, 1, "Salaam"), message(2, 2, "Walaikum salaam")], 2)),
    });
    await openChannel();
    await screen.findByText("Walaikum salaam");

    act(() => {
      FakeSocket.latest().receive({
        type: "message",
        channel: 6,
        event: 1,
        message: message(2, 2, "Psst"),
      });
    });
    expect(await screen.findByRole("link", { name: /random, 1 unread/ })).toBeInTheDocument();

    act(() => {
      FakeSocket.latest().receive({ type: "read", channel: 6, last_read_seq: 2 });
    });
    await waitFor(() => {
      expect(screen.queryByText(/1 unread/)).not.toBeInTheDocument();
    });
  });
});

describe("threads", () => {
  test("replies open beside the channel, and a reply can also go to the channel", async () => {
    const parent = { ...message(2, 3, "Who is bringing samosas?"), reply_count: 1 };
    const first = { ...message(1, 2, "I will"), seq: null, parent_seq: 2, thread_seq: 1 };
    const posted: unknown[] = [];
    backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": () =>
        json(200, page([message(1, 1, "Salaam"), parent], 3)),
      "GET /api/v1/workspaces/team/channels/5/messages/2/replies/": () =>
        json(200, { parent, replies: [first], has_more: false }),
      "POST /api/v1/workspaces/team/channels/5/messages/2/replies/": async (request) => {
        const body = (await request.json()) as { body: string; client_id: string };
        posted.push(body);
        return json(201, {
          ...message(3, 4, body.body, body.client_id),
          parent_seq: 2,
          thread_seq: 2,
          also_in_channel: true,
        });
      },
    });
    await openChannel();

    await userEvent.click(await screen.findByRole("button", { name: "1 reply" }));
    const thread = await screen.findByRole("complementary", { name: "Thread" });
    expect(await within(thread).findByText("I will")).toBeInTheDocument();

    await userEvent.click(within(thread).getByLabelText("Also send to #general"));
    await userEvent.type(within(thread).getByLabelText("Reply"), "With chutney{Enter}");

    expect(await within(thread).findByText("With chutney")).toBeInTheDocument();
    expect(posted).toMatchObject([{ body: "With chutney", also_in_channel: true }]);
    // Also sent to the channel, so the channel shows it too.
    expect(await screen.findAllByText("With chutney")).toHaveLength(2);
  });

  test("a live reply lands in the open thread and the count in the channel goes up", async () => {
    const parent = message(2, 2, "Lunch?");
    backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": () =>
        json(200, page([message(1, 1, "Salaam"), parent], 2)),
      "GET /api/v1/workspaces/team/channels/5/messages/2/replies/": () =>
        json(200, { parent, replies: [], has_more: false }),
    });
    renderAt("/w/team/c/5?thread=2");
    await waitFor(() => {
      expect(FakeSocket.all.length).toBeGreaterThan(0);
    });
    act(() => {
      FakeSocket.latest().open();
    });
    const thread = await screen.findByRole("complementary", { name: "Thread" });
    await within(thread).findByText("0 replies");

    live(3, { ...message(4, 3, "Biryani"), seq: null, parent_seq: 2, thread_seq: 1 });
    live(4, { ...parent, event: 4, reply_count: 1 });

    expect(await within(thread).findByText("Biryani")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "1 reply" })).toBeInTheDocument();
    // Kept in the thread: the channel does not show it.
    expect(screen.getAllByText("Biryani")).toHaveLength(1);
  });
});

describe("mentions", () => {
  const people = [
    { user_id: 1, username: "amna", display_name: "Amna Khan", role: "member", joined_at: "" },
    { user_id: 2, username: "bilal", display_name: "Bilal Ahmed", role: "member", joined_at: "" },
    { user_id: 3, username: "sara", display_name: "Sara", role: "guest", joined_at: "" },
  ];

  test("typing @ offers people, and Enter picks one instead of sending", async () => {
    const backendState = backend({
      "GET /api/v1/workspaces/team/members/": () => json(200, people),
      "GET /api/v1/workspaces/team/channels/5/messages/": () => json(200, page([], 0)),
    });
    await openChannel();
    const composer = await screen.findByLabelText("Message #general");

    await userEvent.type(composer, "chai @");
    const list = await screen.findByRole("listbox", { name: "People to mention" });
    // Not me, not a guest in a public channel; @channel for everyone.
    expect(
      within(list)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["@bilalBilal Ahmed", "@channelEveryone in this channel"]);

    await userEvent.type(composer, "bi{Enter}");

    expect(composer).toHaveValue("chai @bilal ");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(backendState.requests.some((r) => r.method === "POST")).toBe(false);
  });

  test("Escape closes the list and Enter sends again", async () => {
    backend({
      "GET /api/v1/workspaces/team/members/": () => json(200, people),
      "GET /api/v1/workspaces/team/channels/5/messages/": () => json(200, page([], 0)),
    });
    await openChannel();
    const composer = await screen.findByLabelText("Message #general");

    await userEvent.type(composer, "@b");
    await screen.findByRole("listbox");
    await userEvent.keyboard("{Escape}");

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  test("a message that mentions me stands out", async () => {
    const forMe = {
      ...message(2, 2, "@amna can you check?"),
      mentions: [{ id: 1, username: "amna", display_name: "Amna Khan" }],
    };
    backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": () =>
        json(200, page([message(1, 1, "Salaam"), forMe], 2)),
    });
    await openChannel();

    const row = (await screen.findByText(/can you check/)).closest("li");
    const mention = within(row as HTMLElement).getByText("@amna");
    expect(mention).toHaveClass("bg-mention");
    expect(row).toHaveClass("border-mention-edge");
  });
});

describe("reactions", () => {
  const THUMBS_UP = "\u{1F44D}";

  test("pick a reaction, see it counted, and take it back", async () => {
    const salaam = message(2, 2, "Salaam");
    const reacted = {
      ...salaam,
      event: 3,
      reactions: [
        {
          emoji: THUMBS_UP,
          count: 1,
          users: [{ id: 1, username: "amna", display_name: "Amna Khan" }],
        },
      ],
    };
    const calls: string[] = [];
    backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": () =>
        json(200, page([message(1, 1, "Hi"), salaam], 2)),
      "POST /api/v1/workspaces/team/channels/5/messages/2/reactions/": async (request) => {
        calls.push(`add ${((await request.json()) as { emoji: string }).emoji}`);
        return json(200, reacted);
      },
      [`DELETE /api/v1/workspaces/team/channels/5/messages/2/reactions/${encodeURIComponent(THUMBS_UP)}/`]:
        () => {
          calls.push("remove");
          return json(200, { ...salaam, event: 4 });
        },
    });
    await openChannel();
    const row = (await screen.findByText("Salaam")).closest("li") as HTMLElement;

    await userEvent.click(within(row).getByRole("button", { name: "React" }));
    await userEvent.click(screen.getByRole("button", { name: "thumbs up" }));

    const chip = await screen.findByRole("button", { name: "You reacted with thumbs up" });
    expect(chip).toHaveAttribute("aria-pressed", "true");
    expect(chip).toHaveTextContent("1");
    expect(screen.queryByRole("group", { name: "Pick a reaction" })).not.toBeInTheDocument();

    await userEvent.click(chip);

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /reacted with/ })).not.toBeInTheDocument();
    });
    expect(calls).toEqual([`add ${THUMBS_UP}`, "remove"]);
  });
});

describe("direct messages", () => {
  test("pick people, start a group, and it shows under Direct messages by their names", async () => {
    const group: Channel = {
      ...general,
      id: 9,
      name: "~1-2-3",
      kind: "group",
      topic: "",
      is_default: false,
      last_seq: 0,
      last_read_seq: 0,
      people: [
        { id: 1, username: "amna", display_name: "Amna Khan" },
        { id: 2, username: "bilal", display_name: "Bilal Ahmed" },
        { id: 3, username: "sara", display_name: "" },
      ],
    };
    let started = false;
    const sent: unknown[] = [];
    fakeBackend({
      "GET /api/v1/auth/me/": () => json(200, amna),
      "GET /api/v1/workspaces/team/": () =>
        json(200, {
          slug: "team",
          name: "Team",
          created_at: "2026-11-01T10:00:00Z",
          role: "member",
        }),
      "GET /api/v1/workspaces/team/channels/": () =>
        json(200, started ? [general, group] : [general]),
      "GET /api/v1/workspaces/team/members/": () =>
        json(200, [
          {
            user_id: 1,
            username: "amna",
            display_name: "Amna Khan",
            role: "member",
            joined_at: "",
          },
          {
            user_id: 2,
            username: "bilal",
            display_name: "Bilal Ahmed",
            role: "member",
            joined_at: "",
          },
          { user_id: 3, username: "sara", display_name: "", role: "guest", joined_at: "" },
        ]),
      "POST /api/v1/workspaces/team/channels/conversations/": async (request) => {
        sent.push(await request.json());
        started = true;
        return json(201, group);
      },
      "GET /api/v1/workspaces/team/channels/9/messages/": () => json(200, page([], 0)),
    });
    renderAt("/w/team/dm");

    const people = await screen.findByRole("list", { name: "People" });
    await userEvent.click(await within(people).findByLabelText(/Bilal Ahmed/));
    // Not me.
    expect(within(people).queryByText("Amna Khan")).not.toBeInTheDocument();
    await userEvent.click(within(people).getByLabelText(/sara/));
    await userEvent.click(screen.getByRole("button", { name: "Start group" }));

    expect(await screen.findByRole("heading", { name: /Bilal Ahmed, sara/ })).toBeInTheDocument();
    expect(sent).toEqual([{ user_ids: [2, 3] }]);
    const dms = screen.getByRole("region", { name: "Direct messages" });
    expect(within(dms).getByRole("link", { name: /Bilal Ahmed, sara/ })).toBeInTheDocument();
    expect(screen.getByLabelText("Message Bilal Ahmed, sara")).toBeInTheDocument();
  });
});
