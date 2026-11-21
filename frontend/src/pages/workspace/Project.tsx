import { useState, type SubmitEvent } from "react";
import { Link, NavLink, useOutletContext, useParams, useSearchParams } from "react-router";

import {
  useCreateIssue,
  useCreateLabel,
  useIssues,
  useLabels,
  useProject,
  type IssueFilters,
  type Project as ProjectData,
} from "../../api/issues";
import { useMembers } from "../../api/workspaces";
import { Select } from "../../components/Select";
import { ErrorMessage } from "../../components/ui";
import { Avatar, PageHeader, Panel } from "../../components/workspace";
import {
  dueText,
  isClosed,
  LABEL_COLORS,
  labelClass,
  PRIORITIES,
  PRIORITY_LABELS,
  STATUS_LABELS,
  type LabelColor,
} from "../../issues";
import { isAdmin } from "../../roles";
import type { WorkspaceContext } from "./Shell";

const viewClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-1.5 text-sm font-semibold ${
    isActive ? "bg-surface text-text shadow-sm" : "text-text-muted hover:bg-surface"
  }`;

/** A project's name, what it is for, and the switch between its list and its board. */
export function ProjectHeader({
  slug,
  projectKey,
  project,
}: {
  slug: string;
  projectKey: string;
  project: ProjectData | undefined;
}) {
  const base = `/w/${slug}/projects/${projectKey}`;
  return (
    <PageHeader
      title={project ? project.name : "Project"}
      intro={
        project?.archived
          ? "Archived: read only."
          : project?.description || `Issues numbered ${projectKey}-1, ${projectKey}-2 and on.`
      }
      action={
        <nav aria-label="Project view" className="flex gap-1">
          <NavLink end to={base} className={viewClass}>
            List
          </NavLink>
          <NavLink to={`${base}/board`} className={viewClass}>
            Board
          </NavLink>
        </nav>
      }
    />
  );
}

function readFilters(search: URLSearchParams): IssueFilters {
  const label = Number(search.get("label"));
  return {
    open: search.get("state") === "closed" ? "false" : "true",
    ...(search.get("assignee") ? { assignee: search.get("assignee") ?? "" } : {}),
    ...(Number.isInteger(label) && label > 0 ? { label } : {}),
    ...(search.get("priority") ? { priority: search.get("priority") ?? "" } : {}),
  };
}

export function Project() {
  const { workspace } = useOutletContext<WorkspaceContext>();
  const { key = "" } = useParams();
  const slug = workspace.slug;
  const project = useProject(slug, key);
  const labels = useLabels(slug, key);
  const members = useMembers(slug);
  const [search, setSearch] = useSearchParams();
  const filters = readFilters(search);
  const issues = useIssues(slug, key, filters);
  const create = useCreateIssue(slug, key);
  const [title, setTitle] = useState("");
  const today = new Date();

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(search);
    for (const [name, value] of Object.entries(changes)) {
      if (value) next.set(name, value);
      else next.delete(name);
    }
    setSearch(next);
  }

  function add(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim()) return;
    create.mutate(
      { title: title.trim() },
      {
        onSuccess: () => {
          setTitle("");
        },
      },
    );
  }

  if (project.isError) {
    return <ErrorMessage>This project does not exist.</ErrorMessage>;
  }
  const items = issues.data?.pages.flatMap((page) => page.results) ?? [];
  const closedView = filters.open === "false";

  return (
    <div className="flex flex-col gap-6">
      <ProjectHeader slug={slug} projectKey={key} project={project.data} />
      {project.data && !project.data.archived && (
        <form onSubmit={add} className="flex gap-2">
          <label htmlFor="new-issue" className="sr-only">
            New issue title
          </label>
          <input
            id="new-issue"
            value={title}
            onChange={(event) => {
              setTitle(event.target.value);
            }}
            maxLength={200}
            placeholder="New issue: what needs doing?"
            className="h-11 flex-1 rounded-lg border border-border-strong bg-bg px-3 outline-none focus-visible:border-focus-ring focus-visible:ring-4 focus-visible:ring-focus-ring/20"
          />
          <button
            type="submit"
            disabled={create.isPending || !title.trim()}
            className="btn-lamp h-11 rounded-lg bg-accent px-4 font-semibold text-on-accent hover:bg-accent-hover disabled:opacity-60"
          >
            Add
          </button>
        </form>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <div role="tablist" aria-label="Open or closed" className="flex gap-1">
          {[
            { value: null, label: "Open" },
            { value: "closed", label: "Closed" },
          ].map((tab) => (
            <button
              key={tab.label}
              type="button"
              role="tab"
              aria-selected={(tab.value === "closed") === closedView}
              onClick={() => {
                update({ state: tab.value });
              }}
              className="rounded-lg px-3 py-1.5 text-sm font-semibold text-text-muted hover:bg-surface aria-selected:bg-surface aria-selected:text-text aria-selected:shadow-sm"
            >
              {tab.label}
            </button>
          ))}
        </div>
        <Select
          aria-label="Assignee"
          value={filters.assignee ?? ""}
          onChange={(value) => {
            update({ assignee: value || null });
          }}
          options={[
            { value: "", label: "Anyone" },
            { value: "none", label: "Nobody" },
            ...(members.data ?? [])
              .filter((m) => m.role !== "guest")
              .map((m) => ({ value: m.username, label: m.display_name || m.username })),
          ]}
        />
        <Select
          aria-label="Label"
          value={filters.label ? String(filters.label) : ""}
          onChange={(value) => {
            update({ label: value || null });
          }}
          options={[
            { value: "", label: "Any label" },
            ...(labels.data ?? []).map((l) => ({ value: String(l.id), label: l.name })),
          ]}
        />
        <Select
          aria-label="Priority"
          value={filters.priority ?? ""}
          onChange={(value) => {
            update({ priority: value || null });
          }}
          options={[
            { value: "", label: "Any priority" },
            ...PRIORITIES.map((p) => ({ value: p, label: PRIORITY_LABELS[p] })),
          ]}
        />
      </div>

      {issues.data && items.length === 0 && (
        <p className="text-text-muted">{closedView ? "Nothing closed yet." : "Nothing open."}</p>
      )}
      {items.length > 0 && (
        <Panel className="settle">
          <ul aria-label="Issues" className="divide-y divide-border">
            {items.map((issue) => (
              <li key={issue.number}>
                <Link
                  to={`/w/${slug}/projects/${key}/issues/${String(issue.number)}`}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 px-5 py-3 hover:bg-bg-subtle"
                >
                  <span className="w-16 shrink-0 font-mono text-xs text-text-subtle">
                    {issue.ref}
                  </span>
                  <span
                    className={`min-w-0 flex-1 truncate font-medium ${isClosed(issue.status) ? "text-text-muted" : ""}`}
                  >
                    {issue.title}
                  </span>
                  {issue.labels.map((label) => (
                    <span
                      key={label.id}
                      className={`rounded-full px-2 py-0.5 text-xs font-semibold ${labelClass(label.color)}`}
                    >
                      {label.name}
                    </span>
                  ))}
                  {issue.priority !== "none" && (
                    <span className="text-xs font-semibold text-text-muted">
                      {PRIORITY_LABELS[issue.priority]}
                    </span>
                  )}
                  {issue.due && !isClosed(issue.status) && (
                    <span className="text-xs text-text-muted">{dueText(issue.due, today)}</span>
                  )}
                  <span className="text-xs text-text-subtle">{STATUS_LABELS[issue.status]}</span>
                  {issue.assignee && (
                    <Avatar
                      name={issue.assignee.display_name || issue.assignee.username}
                      colorKey={issue.assignee.username}
                      size="sm"
                    />
                  )}
                </Link>
              </li>
            ))}
          </ul>
          {issues.hasNextPage && (
            <div className="flex justify-center border-t border-border p-3">
              <button
                type="button"
                disabled={issues.isFetchingNextPage}
                onClick={() => void issues.fetchNextPage()}
                className="rounded-lg border border-border-strong px-3 py-1 text-sm font-semibold hover:bg-bg-subtle disabled:opacity-60"
              >
                {issues.isFetchingNextPage ? "Loading" : "Older issues"}
              </button>
            </div>
          )}
        </Panel>
      )}

      {isAdmin(workspace.role) && project.data && <LabelEditor slug={slug} projectKey={key} />}
    </div>
  );
}

function LabelEditor({ slug, projectKey }: { slug: string; projectKey: string }) {
  const labels = useLabels(slug, projectKey);
  const create = useCreateLabel(slug, projectKey);
  const [name, setName] = useState("");
  const [color, setColor] = useState<LabelColor>("accent");

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) return;
    create.mutate(
      { name: name.trim(), color },
      {
        onSuccess: () => {
          setName("");
        },
      },
    );
  }

  return (
    <Panel className="flex flex-col gap-3 p-5">
      <h2 className="font-display text-lg font-semibold">Labels</h2>
      <ul aria-label="Labels" className="flex flex-wrap gap-2">
        {labels.data?.map((label) => (
          <li
            key={label.id}
            className={`rounded-full px-2.5 py-0.5 text-sm font-semibold ${labelClass(label.color)}`}
          >
            {label.name}
          </li>
        ))}
      </ul>
      <form onSubmit={submit} className="flex flex-wrap items-center gap-2">
        <label htmlFor="label-name" className="sr-only">
          Label name
        </label>
        <input
          id="label-name"
          value={name}
          onChange={(event) => {
            setName(event.target.value);
          }}
          maxLength={40}
          placeholder="bug"
          className="h-10 rounded-lg border border-border-strong bg-bg px-3 text-sm outline-none focus-visible:border-focus-ring focus-visible:ring-4 focus-visible:ring-focus-ring/20"
        />
        <Select
          aria-label="Label color"
          value={color}
          onChange={setColor}
          options={LABEL_COLORS.map((c) => ({
            value: c,
            label: c.charAt(0).toUpperCase() + c.slice(1),
          }))}
        />
        <button
          type="submit"
          disabled={create.isPending || !name.trim()}
          className="h-10 rounded-lg border border-border-strong px-3 text-sm font-semibold hover:bg-bg-subtle disabled:opacity-60"
        >
          Add label
        </button>
      </form>
      {create.error && (
        <ErrorMessage>That label could not be added; is the name taken?</ErrorMessage>
      )}
    </Panel>
  );
}
