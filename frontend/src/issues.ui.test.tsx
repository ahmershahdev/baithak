import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

import type { Issue } from "./api/issues";
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
const project = {
  key: "BAI",
  name: "Baithak",
  description: "",
  archived: false,
  open_issues: 1,
  created_at: "2026-11-01T10:00:00Z",
};
const bug = { id: 3, name: "bug", color: "danger" };

function issue(extra: Partial<Issue> = {}): Issue {
  return {
    number: 1,
    ref: "BAI-1",
    title: "Search misses Urdu words",
    description: "",
    status: "todo",
    priority: "high",
    assignee: null,
    due: null,
    labels: [],
    created_by: { id: 1, username: "amna", display_name: "Amna Khan" },
    created_at: "2026-11-20T10:00:00Z",
    updated_at: "2026-11-20T10:00:00Z",
    closed_at: null,
    ...extra,
  };
}

function backend(routes: Record<string, (request: Request) => Response | Promise<Response>>) {
  return fakeBackend({
    "GET /api/v1/auth/me/": () => json(200, amna),
    "GET /api/v1/workspaces/": () => json(200, [workspace]),
    "GET /api/v1/workspaces/team/": () => json(200, workspace),
    "GET /api/v1/workspaces/team/channels/": () => json(200, []),
    "GET /api/v1/workspaces/team/members/": () =>
      json(200, [
        { user_id: 1, username: "amna", display_name: "Amna Khan", role: "admin", joined_at: "" },
        { user_id: 2, username: "bilal", display_name: "Bilal", role: "member", joined_at: "" },
      ]),
    "GET /api/v1/workspaces/team/projects/BAI/": () => json(200, project),
    "GET /api/v1/workspaces/team/projects/BAI/labels/": () => json(200, [bug]),
    ...routes,
  });
}

beforeEach(() => {
  FakeSocket.all = [];
  vi.stubGlobal("WebSocket", FakeSocket);
});

describe("issues", () => {
  test("a project lists its open issues and adds one from the box", async () => {
    let issues = [issue()];
    const created: unknown[] = [];
    backend({
      "GET /api/v1/workspaces/team/projects/BAI/issues/": (request) => {
        expect(new URL(request.url).searchParams.get("open")).toBe("true");
        return json(200, { results: issues, next: null });
      },
      "POST /api/v1/workspaces/team/projects/BAI/issues/": async (request) => {
        const body: unknown = await request.json();
        created.push(body);
        issues = [issue({ number: 2, ref: "BAI-2", title: "Add dark mode toggle" }), ...issues];
        return json(201, issues[0]);
      },
    });
    renderAt("/w/team/projects/BAI");

    const list = await screen.findByRole("list", { name: "Issues" });
    expect(within(list).getByText("BAI-1")).toBeInTheDocument();
    expect(within(list).getByText("High")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("New issue title"), "Add dark mode toggle{Enter}");

    expect(await within(list).findByText("BAI-2")).toBeInTheDocument();
    expect(created).toEqual([{ title: "Add dark mode toggle" }]);
  });

  test("an issue's status, assignee and labels change from its page", async () => {
    let current = issue();
    const changes: unknown[] = [];
    backend({
      "GET /api/v1/workspaces/team/projects/BAI/issues/1/": () => json(200, current),
      "PATCH /api/v1/workspaces/team/projects/BAI/issues/1/": async (request) => {
        const body = (await request.json()) as Record<string, unknown>;
        changes.push(body);
        current = issue({
          ...current,
          ...(body.status ? { status: body.status as Issue["status"] } : {}),
          ...(body.assignee_id
            ? { assignee: { id: 2, username: "bilal", display_name: "Bilal" } }
            : {}),
          ...(body.label_ids ? { labels: [bug] as Issue["labels"] } : {}),
        });
        return json(200, current);
      },
    });
    renderAt("/w/team/projects/BAI/issues/1");

    await userEvent.click(await screen.findByRole("combobox", { name: "Status" }));
    await userEvent.click(screen.getByRole("option", { name: "Done" }));
    await userEvent.click(screen.getByRole("combobox", { name: "Assignee" }));
    await userEvent.click(screen.getByRole("option", { name: "Bilal" }));
    await userEvent.click(screen.getByRole("button", { name: "bug" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "bug" })).toHaveAttribute("aria-pressed", "true");
    });
    expect(changes).toEqual([{ status: "done" }, { assignee_id: 2 }, { label_ids: [3] }]);
    expect(screen.getByRole("combobox", { name: "Status" })).toHaveTextContent("Done");
  });
});

describe("board", () => {
  function columns(byStatus: Record<string, Issue[]>, onPatch?: (body: unknown) => Response) {
    const patched: unknown[] = [];
    backend({
      "GET /api/v1/workspaces/team/projects/BAI/issues/": (request) => {
        const status = new URL(request.url).searchParams.get("status") ?? "";
        const results = byStatus[status] ?? [];
        return json(200, { results, next: null, total: results.length });
      },
      "PATCH /api/v1/workspaces/team/projects/BAI/issues/1/": async (request) => {
        const body = (await request.json()) as { status: Issue["status"] };
        patched.push(body);
        if (onPatch) return onPatch(body);
        const moved = issue({ status: body.status });
        for (const key of Object.keys(byStatus)) {
          byStatus[key] = (byStatus[key] ?? []).filter((i) => i.number !== 1);
        }
        byStatus[body.status] = [moved, ...(byStatus[body.status] ?? [])];
        return json(200, moved);
      },
    });
    return patched;
  }

  test("a card moves to another column from its status menu", async () => {
    const patched = columns({ todo: [issue()] });
    renderAt("/w/team/projects/BAI/board");

    const todo = await screen.findByRole("list", { name: "To do" });
    await within(todo).findByText("Search misses Urdu words");
    await userEvent.click(within(todo).getByRole("combobox", { name: "Status of BAI-1" }));
    await userEvent.click(screen.getByRole("option", { name: "In progress" }));

    const doing = screen.getByRole("list", { name: "In progress" });
    expect(await within(doing).findByText("Search misses Urdu words")).toBeInTheDocument();
    await waitFor(() => {
      expect(within(todo).queryByText("Search misses Urdu words")).not.toBeInTheDocument();
    });
    expect(patched).toEqual([{ status: "in_progress" }]);
  });

  test("dragging a card onto a column moves it there", async () => {
    const patched = columns({ todo: [issue()] });
    renderAt("/w/team/projects/BAI/board");
    const todo = await screen.findByRole("list", { name: "To do" });
    const card = (await within(todo).findByText("Search misses Urdu words")).closest("li");
    const done = screen.getByRole("region", { name: /^Done/ });
    const transfer = {
      types: ["application/x-baithak-issue"],
      setData: () => undefined,
      effectAllowed: "",
    };

    fireEvent.dragStart(card as HTMLElement, { dataTransfer: transfer });
    fireEvent.dragOver(done, { dataTransfer: transfer });
    fireEvent.drop(done, { dataTransfer: transfer });

    expect(await within(done).findByText("Search misses Urdu words")).toBeInTheDocument();
    expect(patched).toEqual([{ status: "done" }]);
  });

  test("a move the server refuses puts the card back", async () => {
    columns({ todo: [issue()] }, () => json(403, { detail: "This project is archived." }));
    renderAt("/w/team/projects/BAI/board");
    const todo = await screen.findByRole("list", { name: "To do" });
    await within(todo).findByText("Search misses Urdu words");

    await userEvent.click(within(todo).getByRole("combobox", { name: "Status of BAI-1" }));
    await userEvent.click(screen.getByRole("option", { name: "Done" }));

    expect(
      await screen.findByText("That move did not save, so the card went back."),
    ).toBeInTheDocument();
    expect(within(todo).getByText("Search misses Urdu words")).toBeInTheDocument();
  });
});
