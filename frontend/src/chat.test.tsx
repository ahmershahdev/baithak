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
  has_password: true,
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
    attachments: [],
    issue: null,
    kind: "message",
    sender_name: "",
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

  test("shows formatting, and a handle in code is not a mention", async () => {
    const formatted = {
      ...message(1, 1, "**ship** it, see https://example.com and `@bilal` ||soon||"),
      mentions: [{ id: 2, username: "bilal", display_name: "" }],
    };
    backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": () => json(200, page([formatted], 1)),
    });
    await openChannel();

    expect(await screen.findByText("ship")).toContainHTML("<strong>ship</strong>");
    expect(screen.getByRole("link", { name: "https://example.com" })).toHaveAttribute(
      "rel",
      "noreferrer noopener",
    );
    expect(screen.getByText("@bilal").tagName).toBe("CODE");
    await userEvent.click(screen.getByRole("button", { name: "Spoiler, select to show" }));
    expect(screen.getByText("soon")).toBeVisible();
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
    // The first render can take over a second on a cold run of the whole suite.
    await screen.findByText("two", {}, { timeout: 5_000 });
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

describe("typing and presence", () => {
  const bilal = { id: 2, username: "bilal", display_name: "Bilal" };

  test("typing tells the server, but not on every key", async () => {
    backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": () => json(200, page([], 0)),
    });
    await openChannel();

    await userEvent.type(await screen.findByLabelText("Message #general"), "Salaam");

    const notices = FakeSocket.latest().sent.filter(
      (sent) => (sent as { type: string }).type === "typing",
    );
    expect(notices).toEqual([{ type: "typing", channel: 5, thread: null }]);
  });

  test("someone typing shows until their message arrives", async () => {
    backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": () =>
        json(200, page([message(1, 1, "Salaam")], 1)),
    });
    await openChannel();
    await screen.findByText("Salaam");

    act(() => {
      FakeSocket.latest().receive({ type: "typing", channel: 5, thread: null, user: bilal });
    });
    expect(await screen.findByText("Bilal is typing")).toBeInTheDocument();

    live(2, message(2, 2, "Walaikum salaam"));

    await waitFor(() => {
      expect(screen.queryByText("Bilal is typing")).not.toBeInTheDocument();
    });
  });

  test("a direct message shows whether the other person is online", async () => {
    const direct: Channel = {
      ...general,
      id: 8,
      name: "~1-2",
      kind: "direct",
      is_default: false,
      people: [
        { id: 1, username: "amna", display_name: "Amna Khan" },
        { id: 2, username: "bilal", display_name: "Bilal" },
      ],
    };
    backend({
      "GET /api/v1/workspaces/team/channels/": () => json(200, [general, direct]),
      "GET /api/v1/workspaces/team/channels/5/messages/": () => json(200, page([], 0)),
    });
    await openChannel();
    const dms = await screen.findByRole("region", { name: "Direct messages" });
    expect(await within(dms).findByRole("img", { name: "Offline" })).toBeInTheDocument();

    act(() => {
      FakeSocket.latest().receive({ type: "presence", online: [1, 2] });
    });
    expect(await within(dms).findByRole("img", { name: "Online" })).toBeInTheDocument();

    act(() => {
      FakeSocket.latest().receive({
        type: "presence_changes",
        changes: [
          { user: 3, online: true },
          { user: 2, online: false },
        ],
      });
    });
    expect(await within(dms).findByRole("img", { name: "Offline" })).toBeInTheDocument();
  });
});

describe("files", () => {
  test("attach a file, see it upload, and send it with no text", async () => {
    const notes = {
      id: 31,
      name: "notes.txt",
      content_type: "text/plain",
      size: 2048,
      width: null,
      height: null,
      scan: "clean" as const,
      scan_note: "",
      url: "/api/v1/workspaces/team/files/signed-notes/",
      preview_url: null,
    };
    const sent: unknown[] = [];
    let uploaded = false;
    backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": () => json(200, page([], 0)),
      "POST /api/v1/workspaces/team/channels/5/files/": (request) => {
        // Sent as a form with the file, not as JSON.
        uploaded = request.headers.get("content-type")?.startsWith("multipart/form-data") ?? false;
        return json(201, notes);
      },
      "POST /api/v1/workspaces/team/channels/5/messages/": async (request) => {
        const body = (await request.json()) as { client_id: string };
        sent.push(body);
        return json(201, { ...message(1, 1, "", body.client_id), attachments: [notes] });
      },
    });
    await openChannel();
    await screen.findByText(/This is the very start/);

    await userEvent.upload(
      screen.getByLabelText("Attach files"),
      new File(["chai at four"], "notes.txt", { type: "text/plain" }),
    );
    const files = await screen.findByRole("list", { name: "Files to send" });
    expect(await within(files).findByText("2 KB")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    const link = await screen.findByRole("link", { name: /notes\.txt/ });
    expect(link).toHaveAttribute("href", notes.url);
    expect(uploaded).toBe(true);
    expect(sent).toMatchObject([{ body: "", attachments: [31] }]);
    expect(screen.queryByRole("list", { name: "Files to send" })).not.toBeInTheDocument();
  });

  test("a file being checked has no link, and a refused one says why", async () => {
    const base = { content_type: "text/plain", size: 10, width: null, height: null };
    const held = {
      ...message(1, 1, ""),
      attachments: [
        { ...base, id: 1, name: "draft.txt", scan: "pending" as const, scan_note: "" },
        {
          ...base,
          id: 2,
          name: "eicar.txt",
          scan: "infected" as const,
          scan_note: "Removed: a virus scan flagged it.",
        },
      ].map((file) => ({ ...file, url: null, preview_url: null })),
    };
    backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": () => json(200, page([held], 1)),
    });
    await openChannel();

    expect(await screen.findByText("Checking for viruses")).toBeInTheDocument();
    expect(screen.getByText("Removed: a virus scan flagged it.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /draft\.txt|eicar\.txt/ })).not.toBeInTheDocument();
  });

  test("a file over the limit is refused before uploading", async () => {
    const backendState = backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": () => json(200, page([], 0)),
    });
    await openChannel();
    await screen.findByText(/This is the very start/);
    const big = new File(["x"], "huge.zip");
    Object.defineProperty(big, "size", { value: 26 * 1024 * 1024 });

    await userEvent.upload(screen.getByLabelText("Attach files"), big);

    expect(await screen.findByText("Files can be up to 25 MB.")).toBeInTheDocument();
    expect(backendState.requests.some((r) => r.url.endsWith("/files/"))).toBe(false);
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });
});

describe("search", () => {
  test("searching from the sidebar shows highlighted results that open their thread", async () => {
    const asked: string[] = [];
    backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": () => json(200, page([], 0)),
      "GET /api/v1/workspaces/team/search/messages/": (request) => {
        const url = new URL(request.url);
        asked.push(url.search);
        if (url.searchParams.get("before_id") === "40")
          return json(200, {
            terms: ["deploy"],
            results: [{ channel: 5, message: message(2, 2, "Old deploy notes") }],
            next: null,
          });
        return json(200, {
          terms: ["deploy"],
          results: [
            {
              channel: 5,
              message: { ...message(9, 9, "Deployment is done"), id: 40, parent_seq: 3, seq: null },
            },
          ],
          next: 40,
        });
      },
    });
    await openChannel();

    await userEvent.type(screen.getByLabelText("Search messages and files"), "deploy{Enter}");

    const results = await screen.findByRole("list", { name: "Results" });
    const hit = within(results).getByText("Deployment");
    expect(hit.tagName).toBe("MARK");
    expect(within(results).getByRole("link", { name: /Deployment is done/ })).toHaveAttribute(
      "href",
      "/w/team/c/5?thread=3",
    );
    expect(within(results).getByText(/in general, in a thread/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "More results" }));
    expect(await within(results).findByText(/Old/)).toBeInTheDocument();
    expect(asked.at(-1)).toContain("before_id=40");
  });

  test("words too short to search say so", async () => {
    backend({
      "GET /api/v1/workspaces/team/search/messages/": () =>
        json(200, { terms: [], results: [], next: null }),
    });
    renderAt("/w/team/search?q=it");

    expect(await screen.findByText(/at least three letters/)).toBeInTheDocument();
  });
});

describe("notifications", () => {
  test("the sidebar counts unread, refreshes live, and the page marks them read", async () => {
    const mention = {
      id: 7,
      kind: "mention",
      channel: 5,
      created_at: "2026-11-21T10:00:00Z",
      read: false,
      message: { ...message(2, 2, "@amna can you check the invoice?") },
    };
    let unread = 0;
    const marked: unknown[] = [];
    backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": () => json(200, page([], 0)),
      "GET /api/v1/workspaces/team/notifications/": () =>
        json(200, {
          unread,
          results: unread ? [mention] : [{ ...mention, read: true }],
          next: null,
        }),
      "POST /api/v1/workspaces/team/notifications/read/": async (request) => {
        marked.push(await request.json());
        unread = 0;
        return json(200, { unread: 0 });
      },
    });
    await openChannel();
    const link = await screen.findByRole("link", { name: "Notifications" });

    unread = 1;
    act(() => {
      FakeSocket.latest().receive({ type: "notifications" });
    });
    expect(
      await screen.findByRole("link", { name: /Notifications, 1 unread/ }),
    ).toBeInTheDocument();

    await userEvent.click(link);
    const list = await screen.findByRole("list", { name: "Notifications" });
    expect(within(list).getByText("bilal mentioned you in general")).toBeInTheDocument();
    expect(within(list).getByText("@amna can you check the invoice?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Mark all read" }));

    await waitFor(() => {
      expect(screen.queryByText(/1 unread/)).not.toBeInTheDocument();
    });
    expect(marked).toEqual([{ all: true }]);
  });
});

describe("your settings", () => {
  test("turn on quiet hours in your time zone and save", async () => {
    const saved: unknown[] = [];
    backend({
      "GET /api/v1/auth/notifications/": () =>
        json(200, { notify_by_email: true, quiet_start: null, quiet_end: null, time_zone: "UTC" }),
      "PATCH /api/v1/auth/notifications/": async (request) => {
        const body: unknown = await request.json();
        saved.push(body);
        return json(200, body);
      },
    });
    renderAt("/w/team/me");

    await userEvent.click(await screen.findByLabelText("No emails between"));
    await userEvent.click(screen.getByRole("combobox", { name: "Time zone" }));
    await userEvent.click(screen.getByRole("option", { name: "Asia/Karachi" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(saved).toEqual([
      {
        notify_by_email: true,
        quiet_start: "22:00",
        quiet_end: "08:00",
        time_zone: "Asia/Karachi",
      },
    ]);
  });
});

describe("guests", () => {
  test("see direct messages only, with no channels to browse", async () => {
    const asGuest = {
      slug: "team",
      name: "Team",
      created_at: "2026-11-01T10:00:00Z",
      role: "guest",
    };
    backend({
      "GET /api/v1/workspaces/": () => json(200, [asGuest]),
      "GET /api/v1/workspaces/team/": () => json(200, asGuest),
      "GET /api/v1/workspaces/team/channels/": () => json(200, []),
    });
    renderAt("/w/team/channels");

    expect(await screen.findByText(/Guests talk in direct and group messages only/)).toBeVisible();
    expect(screen.getByRole("heading", { name: "Direct messages" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Browse" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create channel" })).not.toBeInTheDocument();
  });
});

describe("two-step sign-in settings", () => {
  const settings = () =>
    json(200, { notify_by_email: true, quiet_start: null, quiet_end: null, time_zone: "UTC" });
  const codes = Array.from({ length: 10 }, (_, i) => `abcde-fgh${String(i)}k`);

  test("set it up with the key, a first code, then see the recovery codes once", async () => {
    let on = false;
    backend({
      "GET /api/v1/auth/notifications/": settings,
      "GET /api/v1/auth/two-step/": () =>
        json(200, { enabled: on, recovery_codes_left: on ? 10 : 0 }),
      "POST /api/v1/auth/two-step/setup/": () =>
        json(200, {
          secret: "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
          uri: "otpauth://totp/Baithak%3Aamna%40example.com?secret=JBSW&issuer=Baithak",
        }),
      "POST /api/v1/auth/two-step/enable/": () => {
        on = true;
        return json(200, { recovery_codes: codes });
      },
    });
    renderAt("/w/team/me");

    await userEvent.click(await screen.findByRole("button", { name: "Set up two-step sign-in" }));
    const qr = screen.getByRole("img", { name: "QR code for your authenticator app" });
    expect(qr.querySelector("path")?.getAttribute("d")).toMatch(/^M\d+ \d+h1v1h-1z/);
    expect(screen.getByLabelText("Key for your app")).toHaveTextContent(
      "JBSW Y3DP EHPK 3PXP JBSW Y3DP EHPK 3PXP",
    );
    expect(
      screen.getByRole("link", { name: "On this phone? Open it in your authenticator app" }),
    ).toHaveAttribute("href", expect.stringMatching(/^otpauth:\/\/totp\//));
    await userEvent.type(screen.getByLabelText("Code from the app"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Turn on two-step sign-in" }));

    const list = await screen.findByRole("list", { name: "Recovery codes" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(10);
    expect(screen.getByRole("link", { name: "Download" })).toHaveAttribute(
      "download",
      "baithak-recovery-codes.txt",
    );
    await userEvent.click(screen.getByRole("button", { name: "I have saved them" }));

    expect(screen.queryByRole("list", { name: "Recovery codes" })).not.toBeInTheDocument();
    expect(await screen.findByText("10 recovery codes left.")).toBeInTheDocument();
  });

  test("turning it off asks for the password and a code", async () => {
    const sent: unknown[] = [];
    backend({
      "GET /api/v1/auth/notifications/": settings,
      "GET /api/v1/auth/two-step/": () => json(200, { enabled: true, recovery_codes_left: 3 }),
      "POST /api/v1/auth/two-step/disable/": async (request) => {
        sent.push(await request.json());
        return new Response(null, { status: 204 });
      },
    });
    renderAt("/w/team/me");

    await userEvent.click(await screen.findByRole("button", { name: "Turn off" }));
    await userEvent.type(screen.getByLabelText("Your password"), "Chai-At-Four-42");
    await userEvent.type(screen.getByLabelText("Code from the app, or a recovery code"), "654321");
    await userEvent.click(screen.getByRole("button", { name: "Turn off two-step sign-in" }));

    await waitFor(() => {
      expect(sent).toEqual([{ password: "Chai-At-Four-42", code: "654321" }]);
    });
  });
});

describe("signed-in devices", () => {
  const settings = () =>
    json(200, { notify_by_email: true, quiet_start: null, quiet_end: null, time_zone: "UTC" });
  const now = new Date().toISOString();

  test("lists devices and signs one out, then every other one", async () => {
    let listed = [
      { id: 1, name: "Chrome on Windows", created_at: now, last_seen_at: now, current: true },
      { id: 2, name: "Safari on iPhone", created_at: now, last_seen_at: now, current: false },
      { id: 3, name: "Firefox on Linux", created_at: now, last_seen_at: now, current: false },
    ];
    const signedOut: string[] = [];
    backend({
      "GET /api/v1/auth/notifications/": settings,
      "GET /api/v1/auth/devices/": () => json(200, listed),
      "DELETE /api/v1/auth/devices/2/": () => {
        signedOut.push("2");
        listed = listed.filter((d) => d.id !== 2);
        return new Response(null, { status: 204 });
      },
      "POST /api/v1/auth/devices/sign-out-others/": () => {
        signedOut.push("others");
        listed = listed.filter((d) => d.current);
        return json(200, { signed_out: 1 });
      },
    });
    renderAt("/w/team/me");

    const devices = await screen.findByRole("list", { name: "Devices" });
    expect(within(devices).getByText("This device")).toBeInTheDocument();
    expect(
      within(devices).queryByRole("button", { name: "Sign out Chrome on Windows" }),
    ).not.toBeInTheDocument();

    await userEvent.click(
      within(devices).getByRole("button", { name: "Sign out Safari on iPhone" }),
    );
    expect(await screen.findByText("That device is signed out.")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("Safari on iPhone")).not.toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Sign out everywhere else" }));
    expect(await screen.findByText("1 other device is signed out.")).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: "Sign out everywhere else" }),
      ).not.toBeInTheDocument();
    });
    expect(signedOut).toEqual(["2", "others"]);
  });
});

describe("deleting your account", () => {
  const settings = () =>
    json(200, { notify_by_email: true, quiet_start: null, quiet_end: null, time_zone: "UTC" });

  test("lists the workspaces to hand over when you are their last owner", async () => {
    backend({
      "GET /api/v1/auth/notifications/": settings,
      "POST /api/v1/auth/delete-account/": () =>
        json(409, {
          detail: "Make someone else an owner of these workspaces first, or remove everyone else.",
          workspaces: [{ slug: "team", name: "Chai and Code" }],
        }),
    });
    renderAt("/w/team/me");

    await userEvent.click(await screen.findByRole("button", { name: "Delete account" }));
    await userEvent.type(screen.getByLabelText("Your password, to confirm"), "Chai-At-Four-42");
    await userEvent.click(screen.getByRole("button", { name: "Delete my account for good" }));

    expect(await screen.findByText(/Make someone else an owner/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Chai and Code" })).toHaveAttribute(
      "href",
      "/w/team/members",
    );
  });

  test("someone without a password confirms with their email", async () => {
    const sent: unknown[] = [];
    backend({
      "GET /api/v1/auth/notifications/": settings,
      "GET /api/v1/auth/me/": () => json(200, { ...amna, has_password: false }),
      "POST /api/v1/auth/delete-account/": async (request) => {
        sent.push(await request.json());
        return new Response(null, { status: 204 });
      },
    });
    renderAt("/w/team/me");

    await userEvent.click(await screen.findByRole("button", { name: "Delete account" }));
    expect(screen.queryByLabelText("Your password, to confirm")).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Your email address, to confirm"), amna.email);
    await userEvent.click(screen.getByRole("button", { name: "Delete my account for good" }));

    await waitFor(() => {
      expect(sent).toEqual([{ email: amna.email }]);
    });
  });

  test("sends the password and lands on sign in once deleted", async () => {
    const sent: unknown[] = [];
    let deleted = false;
    backend({
      "GET /api/v1/auth/notifications/": settings,
      "POST /api/v1/auth/delete-account/": async (request) => {
        sent.push(await request.json());
        deleted = true;
        return new Response(null, { status: 204 });
      },
      "GET /api/v1/auth/me/": () =>
        deleted ? new Response(null, { status: 204 }) : json(200, amna),
    });
    renderAt("/w/team/me");

    await userEvent.click(await screen.findByRole("button", { name: "Delete account" }));
    await userEvent.type(screen.getByLabelText("Your password, to confirm"), "Chai-At-Four-42");
    await userEvent.click(screen.getByRole("button", { name: "Delete my account for good" }));

    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    expect(sent).toEqual([{ password: "Chai-At-Four-42" }]);
  });
});

describe("issues from messages", () => {
  test("open an issue from a message and see it linked once it arrives", async () => {
    const bodies: unknown[] = [];
    const report = message(2, 2, "Upload does nothing on Safari\nTried twice");
    backend({
      "GET /api/v1/workspaces/team/channels/5/messages/": () =>
        json(200, page([message(1, 1, "Hi"), report], 2)),
      "GET /api/v1/workspaces/team/projects/": () =>
        json(200, [
          {
            key: "BAI",
            name: "Baithak",
            description: "",
            archived: false,
            open_issues: 0,
            created_at: "2026-11-01T10:00:00Z",
          },
        ]),
      "POST /api/v1/workspaces/team/projects/BAI/issues/": async (request) => {
        bodies.push(await request.json());
        return json(201, {});
      },
    });
    await openChannel();
    const row = (await screen.findByText(/Upload does nothing/)).closest("li") as HTMLElement;

    await userEvent.click(within(row).getByRole("button", { name: "Issue" }));
    const form = await screen.findByRole("form", { name: "Open an issue" });
    expect(within(form).getByLabelText("Issue title")).toHaveValue("Upload does nothing on Safari");
    await userEvent.click(within(form).getByRole("button", { name: "Open issue" }));

    await waitFor(() => {
      expect(screen.queryByRole("form", { name: "Open an issue" })).not.toBeInTheDocument();
    });
    expect(bodies).toEqual([
      { title: "Upload does nothing on Safari", from_message: { channel_id: 5, seq: 2 } },
    ]);
    live(3, { ...report, event: 3, issue: { ref: "BAI-7", project: "BAI", number: 7 } });

    const chip = await screen.findByRole("link", { name: /BAI-7/ });
    expect(chip).toHaveAttribute("href", "/w/team/projects/BAI/issues/7");
    expect(within(row).queryByRole("button", { name: "Issue" })).not.toBeInTheDocument();
  });
});

test("an issue update shows as a short line with no actions", async () => {
  backend({
    "GET /api/v1/workspaces/team/channels/5/messages/": () =>
      json(
        200,
        page(
          [message(1, 1, "Hi"), { ...message(2, 2, "BAI-7: moved it to Done"), kind: "activity" }],
          2,
        ),
      ),
  });
  await openChannel();

  const row = (await screen.findByText("BAI-7: moved it to Done", { exact: false })).closest(
    "li",
  ) as HTMLElement;

  expect(within(row).queryByRole("button")).not.toBeInTheDocument();
  expect(row).toHaveTextContent("bilal BAI-7: moved it to Done");
});

test("the Issues tab finds issues and opens them", async () => {
  backend({
    "GET /api/v1/workspaces/team/members/": () => json(200, []),
    "GET /api/v1/workspaces/team/search/issues/": (request) => {
      expect(new URL(request.url).searchParams.get("q")).toBe("upload");
      return json(200, {
        terms: ["upload"],
        results: [
          {
            ref: "BAI-7",
            project: "BAI",
            number: 7,
            title: "Upload fails on Safari",
            description: "Steps:\n1. upload a file",
            status: "in_progress",
            assignee: null,
          },
        ],
        next: null,
      });
    },
  });
  renderAt("/w/team/search?q=upload&kind=issues");

  const results = await screen.findByRole("list", { name: "Results" });
  const link = within(results).getByRole("link");

  expect(screen.getByRole("tab", { name: "Issues" })).toHaveAttribute("aria-selected", "true");
  expect(link).toHaveAttribute("href", "/w/team/projects/BAI/issues/7");
  expect(link).toHaveTextContent("BAI-7Upload fails on SafariIn progress");
  expect(within(link).getAllByText("upload", { selector: "mark" })).toHaveLength(1);
});

test("a GitHub message shows its app name and links into GitHub", async () => {
  const fromGitHub: Message = {
    ...message(
      2,
      2,
      "amna opened pull request #12 in team/app: Fix uploads\nhttps://github.com/team/app/pull/12",
    ),
    author: null,
    kind: "integration",
    sender_name: "GitHub",
  };
  backend({
    "GET /api/v1/workspaces/team/channels/5/messages/": () =>
      json(200, page([message(1, 1, "Hi"), fromGitHub], 2)),
  });
  await openChannel();

  const link = await screen.findByRole("link", { name: "https://github.com/team/app/pull/12" });
  const row = link.closest("li") as HTMLElement;

  expect(link).toHaveAttribute("href", "https://github.com/team/app/pull/12");
  expect(within(row).getByText("GitHub")).toBeInTheDocument();
  expect(within(row).getByText("App")).toBeInTheDocument();
});
