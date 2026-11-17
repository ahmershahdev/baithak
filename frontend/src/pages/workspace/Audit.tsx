import { useOutletContext } from "react-router";

import { ApiError, useAuditLog, type AuditEvent } from "../../api/workspaces";
import { ErrorMessage } from "../../components/ui";
import { PageHeader, Panel, When } from "../../components/workspace";
import { isAdmin } from "../../roles";
import type { WorkspaceContext } from "./Shell";

const ACTIONS: Record<string, string> = {
  "workspace.create": "created the workspace",
  "workspace.update": "changed the workspace",
  "member.add": "added a member",
  "member.update": "changed a role",
  "member.remove": "removed a member",
  "invitation.create": "sent an invitation",
  "invitation.revoke": "revoked an invitation",
  "invitation.accept": "accepted an invitation",
};

function describe(changes: unknown): string {
  if (typeof changes !== "object" || changes === null) return "";
  return Object.entries(changes)
    .map(([field, value]) =>
      Array.isArray(value) && value.length === 2
        ? `${field}: ${String(value[0])} → ${String(value[1])}`
        : `${field}: ${String(value)}`,
    )
    .join(", ");
}

function Event({ event }: { event: AuditEvent }) {
  const details = describe(event.changes);
  return (
    <li className="grid gap-1 px-5 py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:gap-4">
      <div className="min-w-0">
        <p>
          <span className="font-semibold">{event.actor ? `@${event.actor}` : "Someone"}</span>{" "}
          {ACTIONS[event.action] ?? event.action}
        </p>
        {details && <p className="truncate text-sm text-text-subtle">{details}</p>}
      </div>
      <p className="text-sm text-text-subtle tabular-nums">
        <When iso={event.at} />
      </p>
    </li>
  );
}

export function Audit() {
  const { workspace } = useOutletContext<WorkspaceContext>();
  const admin = isAdmin(workspace.role);
  const log = useAuditLog(workspace.slug, admin);

  if (!admin) {
    return (
      <div className="flex flex-col gap-8">
        <PageHeader title="Audit log" />
        <ErrorMessage>Only owners and admins can read the audit log.</ErrorMessage>
      </div>
    );
  }

  const events = log.data?.pages.flatMap((page) => page.results) ?? [];
  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Audit log"
        intro="Every change to this workspace, its members and its invitations, newest first."
      />
      {log.isError && (
        <ErrorMessage>
          {log.error instanceof ApiError ? log.error.message : "Could not load the log."}
        </ErrorMessage>
      )}
      {events.length > 0 && (
        <Panel className="settle">
          <ol className="divide-y divide-border">
            {events.map((event) => (
              <Event key={event.id} event={event} />
            ))}
          </ol>
        </Panel>
      )}
      {log.hasNextPage && (
        <button
          type="button"
          onClick={() => {
            void log.fetchNextPage();
          }}
          disabled={log.isFetchingNextPage}
          className="self-center rounded-xl border border-border-strong px-5 py-2 font-semibold hover:bg-bg-subtle focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none disabled:opacity-60"
        >
          {log.isFetchingNextPage ? "Loading" : "Show older"}
        </button>
      )}
    </div>
  );
}
