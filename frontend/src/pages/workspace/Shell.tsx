import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, NavLink, Navigate, Outlet, useNavigate, useParams } from "react-router";

import { useChannels } from "../../api/chat";
import { api, type User } from "../../api/client";
import { useWorkspace, useWorkspaces, type Workspace } from "../../api/workspaces";
import { ME } from "../../auth";
import { useLive } from "../../chat/live";
import { Wordmark } from "../../components/brand";
import { Avatar, ChannelIcon, RoleBadge } from "../../components/workspace";
import { rememberWorkspace } from "../../lastWorkspace";
import { isAdmin } from "../../roles";

export interface WorkspaceContext {
  workspace: Workspace;
  me: User;
}

function Switcher({ current }: { current: Workspace }) {
  const workspaces = useWorkspaces();
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-controls="workspace-list"
        onClick={() => {
          setOpen((now) => !now);
        }}
        className="flex w-full items-center gap-3 rounded-xl p-2 text-left transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
      >
        <Avatar name={current.name} colorKey={current.slug} />
        <span className="min-w-0 flex-1">
          <span className="block truncate font-semibold">{current.name}</span>
          <span className="block text-xs text-text-subtle">Switch workspace</span>
        </span>
        <svg
          viewBox="0 0 20 20"
          className={`size-4 text-text-subtle transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden="true"
        >
          <path d="M5 8l5 5 5-5" fill="none" stroke="currentColor" strokeWidth="1.8" />
        </svg>
      </button>
      {open && (
        <ul
          id="workspace-list"
          className="settle absolute inset-x-0 top-full z-20 mt-1 overflow-hidden rounded-xl border border-border bg-surface-raised p-1 shadow-lg"
        >
          {workspaces.data?.map((workspace) => (
            <li key={workspace.slug}>
              <Link
                to={`/w/${workspace.slug}`}
                aria-current={workspace.slug === current.slug ? "page" : undefined}
                onClick={() => {
                  setOpen(false);
                }}
                className="flex items-center gap-3 rounded-lg p-2 hover:bg-bg-subtle aria-[current=page]:bg-bg-subtle"
              >
                <Avatar name={workspace.name} colorKey={workspace.slug} size="sm" />
                <span className="truncate text-sm font-medium">{workspace.name}</span>
              </Link>
            </li>
          ))}
          <li className="mt-1 border-t border-border pt-1">
            <Link
              to="/w/new"
              className="flex items-center gap-3 rounded-lg p-2 text-sm font-semibold text-accent-text hover:bg-bg-subtle"
            >
              <span className="grid size-7 place-items-center rounded-lg border border-dashed border-border-strong">
                +
              </span>
              New workspace
            </Link>
          </li>
        </ul>
      )}
    </div>
  );
}

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none ${
    isActive ? "bg-surface text-text shadow-sm" : "text-text-muted hover:bg-surface hover:text-text"
  }`;

function ChannelList({ slug }: { slug: string }) {
  const channels = useChannels(slug);
  const mine = channels.data?.filter((channel) => channel.is_member) ?? [];
  return (
    <section aria-labelledby="channels-heading" className="flex flex-col gap-1">
      <div className="flex items-center justify-between px-3">
        <h2
          id="channels-heading"
          className="text-xs font-semibold tracking-wide text-text-subtle uppercase"
        >
          Channels
        </h2>
        <Link
          to={`/w/${slug}/channels`}
          className="rounded-md px-1.5 text-xs font-semibold text-accent-text hover:bg-surface focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
        >
          Browse
        </Link>
      </div>
      <ul className="flex flex-col gap-0.5">
        {mine.map((channel) => (
          <li key={channel.id}>
            <NavLink to={`/w/${slug}/c/${String(channel.id)}`} className={linkClass}>
              <ChannelIcon kind={channel.kind} />
              <span
                className={`truncate ${channel.archived ? "text-text-subtle line-through" : ""}`}
              >
                {channel.name}
              </span>
            </NavLink>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Nav({ workspace }: { workspace: Workspace }) {
  const base = `/w/${workspace.slug}`;
  const admin = isAdmin(workspace.role);
  return (
    <nav aria-label="Workspace" className="flex gap-1 overflow-x-auto md:flex-col">
      <NavLink end to={base} className={linkClass}>
        Overview
      </NavLink>
      <NavLink to={`${base}/members`} className={linkClass}>
        Members
      </NavLink>
      {admin && (
        <>
          <NavLink to={`${base}/invitations`} className={linkClass}>
            Invitations
          </NavLink>
          <NavLink to={`${base}/settings`} className={linkClass}>
            Settings
          </NavLink>
          <NavLink to={`${base}/audit`} className={linkClass}>
            Audit log
          </NavLink>
        </>
      )}
    </nav>
  );
}

function Account({ me }: { me: User }) {
  const client = useQueryClient();
  const navigate = useNavigate();
  const signOut = useMutation({
    mutationFn: async () => api.POST("/api/v1/auth/signout/"),
    onSuccess: () => {
      client.removeQueries({ predicate: (query) => query.queryKey[0] !== ME[0] });
      client.setQueryData(ME, null);
      void navigate("/signin");
    },
  });
  return (
    <div className="flex items-center gap-3 rounded-xl p-2">
      <Avatar name={me.display_name || me.username} colorKey={me.username} size="sm" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold">
          {me.display_name || me.username}
        </span>
        <span className="block truncate text-xs text-text-subtle">@{me.username}</span>
      </span>
      <button
        type="button"
        onClick={() => {
          signOut.mutate();
        }}
        disabled={signOut.isPending}
        className="rounded-lg px-2 py-1 text-xs font-semibold text-text-muted hover:bg-surface hover:text-text focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
      >
        Sign out
      </button>
    </div>
  );
}

export function WorkspaceShell({ me }: { me: User }) {
  const { slug = "" } = useParams();
  const workspace = useWorkspace(slug);
  const live = useLive(slug);

  useEffect(() => {
    if (workspace.data) rememberWorkspace(workspace.data.slug);
  }, [workspace.data]);

  if (workspace.isPending) {
    return (
      <p role="status" className="p-8 text-text-muted">
        Loading
      </p>
    );
  }
  // Not a member, or no such workspace: the API answers the same 404 for both.
  if (workspace.isError) return <Navigate to="/" replace />;

  const context: WorkspaceContext = { workspace: workspace.data, me };
  return (
    <div className="grid min-h-dvh bg-bg md:grid-cols-[17rem_minmax(0,1fr)]">
      <aside className="flex flex-col gap-6 border-b border-border bg-bg-subtle p-4 md:sticky md:top-0 md:h-dvh md:overflow-y-auto md:border-r md:border-b-0">
        <Link
          to="/"
          className="self-start rounded-md px-2 pt-1 focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
        >
          <Wordmark />
          <span className="sr-only">Baithak home</span>
        </Link>
        <Switcher current={workspace.data} />
        <div className="flex items-center gap-2 px-2">
          <span className="text-xs text-text-subtle">Your role</span>
          <RoleBadge role={workspace.data.role} />
        </div>
        <ChannelList slug={workspace.data.slug} />
        <Nav workspace={workspace.data} />
        <div className="mt-auto hidden md:block">
          <Account me={me} />
        </div>
      </aside>
      <main className="min-w-0 px-5 py-8 sm:px-10 lg:px-14">
        <div className="mx-auto max-w-4xl">
          {live === "reconnecting" && (
            <p
              role="status"
              className="settle mb-4 rounded-xl bg-warning-soft px-4 py-2 text-sm text-warning-soft-text"
            >
              Reconnecting. Messages sent meanwhile will appear when the connection is back.
            </p>
          )}
          <Outlet context={context} />
        </div>
        <div className="mt-12 border-t border-border pt-4 md:hidden">
          <Account me={me} />
        </div>
      </main>
    </div>
  );
}
