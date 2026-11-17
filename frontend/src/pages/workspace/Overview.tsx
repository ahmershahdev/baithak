import { Link, useOutletContext } from "react-router";

import { useMembers } from "../../api/workspaces";
import { Scene } from "../../components/brand";
import { PageHeader, Panel } from "../../components/workspace";
import { isAdmin } from "../../roles";
import type { WorkspaceContext } from "./Shell";

export function Overview() {
  const { workspace, me } = useOutletContext<WorkspaceContext>();
  const members = useMembers(workspace.slug);
  const count = members.data?.length;
  const base = `/w/${workspace.slug}`;

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title={workspace.name}
        intro={
          <>
            Welcome in, {me.display_name || me.username}.{" "}
            {count !== undefined && (
              <>
                {count} {count === 1 ? "person sits" : "people sit"} in this room.
              </>
            )}
          </>
        }
      />
      <Panel className="settle grid items-center gap-8 overflow-hidden p-6 sm:p-8 md:grid-cols-[1fr_15rem]">
        <div>
          <h2 className="wonky font-display text-2xl font-semibold">The room is ready</h2>
          <p className="mt-2 text-text-muted">
            Channels, threads and live messages arrive next. Until then, bring your people in so the
            conversation can start the moment they do.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            {isAdmin(workspace.role) && (
              <Link
                to={`${base}/invitations`}
                className="btn-lamp inline-flex h-11 items-center rounded-xl bg-accent px-5 font-semibold text-on-accent hover:bg-accent-hover focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2 focus-visible:ring-offset-surface focus-visible:outline-none"
              >
                Invite people
              </Link>
            )}
            <Link
              to={`${base}/members`}
              className="inline-flex h-11 items-center rounded-xl border border-border-strong px-5 font-semibold hover:bg-bg-subtle focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
            >
              See who is here
            </Link>
          </div>
        </div>
        <div className="hidden md:block">
          <Scene />
        </div>
      </Panel>
    </div>
  );
}
