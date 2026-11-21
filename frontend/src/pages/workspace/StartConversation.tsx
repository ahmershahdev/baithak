import { useState } from "react";
import { useNavigate, useOutletContext } from "react-router";

import { useStartConversation } from "../../api/chat";
import { ApiError, useMembers } from "../../api/workspaces";
import { matches } from "../../chat/conversations";
import { Button, ErrorMessage } from "../../components/ui";
import { Avatar, PageHeader, Panel } from "../../components/workspace";
import type { WorkspaceContext } from "./Shell";

// Everyone in a conversation, the starter included (apps/core/conversations.py).
const MAX_OTHERS = 8;

export function StartConversation() {
  const { workspace, me } = useOutletContext<WorkspaceContext>();
  const members = useMembers(workspace.slug);
  const start = useStartConversation(workspace.slug);
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [picked, setPicked] = useState<number[]>([]);
  const others = (members.data ?? []).filter((member) => member.user_id !== me.id);
  const shown = others.filter((member) => matches(member, search));
  const full = picked.length >= MAX_OTHERS;

  function toggle(userId: number) {
    setPicked((now) =>
      now.includes(userId) ? now.filter((id) => id !== userId) : [...now, userId],
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="New message"
        intro="Pick one person for a direct message, or up to eight for a group. Only the people in it can read it."
      />
      <Panel className="settle flex flex-col gap-4 p-5">
        <label htmlFor="people-search" className="text-sm font-semibold">
          Find people
        </label>
        <input
          id="people-search"
          type="search"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
          }}
          placeholder="Name or @handle"
          className="h-11 rounded-lg border border-border-strong bg-bg px-3 outline-none focus-visible:border-focus-ring focus-visible:ring-4 focus-visible:ring-focus-ring/20"
        />
        {members.isPending && (
          <p role="status" className="text-text-muted">
            Loading people
          </p>
        )}
        {members.data && others.length === 0 && (
          <p className="text-text-muted">
            Nobody else is in this workspace yet. Invite someone first.
          </p>
        )}
        <ul aria-label="People" className="flex max-h-96 flex-col gap-1 overflow-y-auto">
          {shown.map((member) => {
            const name = member.display_name || member.username;
            const checked = picked.includes(member.user_id);
            return (
              <li key={member.user_id}>
                <label className="flex cursor-pointer items-center gap-3 rounded-lg px-2 py-2 hover:bg-bg-subtle has-disabled:cursor-not-allowed has-disabled:opacity-60">
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={!checked && full}
                    onChange={() => {
                      toggle(member.user_id);
                    }}
                    className="size-4 accent-accent"
                  />
                  <Avatar name={name} colorKey={member.username} size="sm" />
                  <span className="min-w-0">
                    <span className="block truncate font-semibold">{name}</span>
                    <span className="block truncate text-xs text-text-subtle">
                      @{member.username}
                    </span>
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
        {start.error && (
          <ErrorMessage>
            {start.error instanceof ApiError
              ? (start.error.problems.detail ??
                (Object.values(start.error.problems.fields).flat().join(" ") ||
                  start.error.message))
              : "Could not reach Baithak. Try again."}
          </ErrorMessage>
        )}
        <Button
          type="button"
          disabled={picked.length === 0}
          busy={start.isPending}
          busyLabel="Opening"
          className="self-start"
          onClick={() => {
            start.mutate(picked, {
              onSuccess: (channel) => {
                void navigate(`/w/${workspace.slug}/c/${String(channel.id)}`);
              },
            });
          }}
        >
          {picked.length > 1 ? "Start group" : "Start conversation"}
        </Button>
      </Panel>
    </div>
  );
}
