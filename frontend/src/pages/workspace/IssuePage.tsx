import { useState, type ReactNode } from "react";
import { Link, useOutletContext, useParams } from "react-router";

import { useIssue, useLabels, useProject, useUpdateIssue, type Issue } from "../../api/issues";
import { ApiError, useMembers } from "../../api/workspaces";
import { Select } from "../../components/Select";
import { ErrorMessage } from "../../components/ui";
import { Panel } from "../../components/workspace";
import {
  labelClass,
  PRIORITIES,
  PRIORITY_LABELS,
  STATUS_LABELS,
  STATUSES,
  type Priority,
  type Status,
} from "../../issues";
import type { WorkspaceContext } from "./Shell";

const when = new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" });

export function IssuePage() {
  const { workspace } = useOutletContext<WorkspaceContext>();
  const { key = "", number = "" } = useParams();
  const issue = useIssue(workspace.slug, key, Number(number));
  if (issue.isPending) {
    return (
      <p role="status" className="text-text-muted">
        Loading
      </p>
    );
  }
  if (issue.isError) return <ErrorMessage>This issue does not exist.</ErrorMessage>;
  return (
    <IssueEditor
      key={issue.data.number}
      slug={workspace.slug}
      projectKey={key}
      issue={issue.data}
    />
  );
}

function IssueEditor({
  slug,
  projectKey,
  issue,
}: {
  slug: string;
  projectKey: string;
  issue: Issue;
}) {
  const project = useProject(slug, projectKey);
  const labels = useLabels(slug, projectKey);
  const members = useMembers(slug);
  const update = useUpdateIssue(slug, projectKey, issue.number);
  const [title, setTitle] = useState(issue.title);
  const [description, setDescription] = useState(issue.description);
  const readOnly = project.data?.archived ?? false;
  const chosen = new Set(issue.labels.map((label) => label.id));

  const problem =
    update.error instanceof ApiError
      ? Object.values(update.error.problems.fields).flat().join(" ") ||
        (update.error.problems.detail ?? update.error.message)
      : update.error
        ? "Could not reach Baithak. Try again."
        : null;

  return (
    <div className="flex flex-col gap-6">
      <nav aria-label="Breadcrumb" className="text-sm text-text-muted">
        <Link
          to={`/w/${slug}/projects/${projectKey}`}
          className="font-semibold text-accent-text hover:underline"
        >
          {project.data?.name ?? projectKey}
        </Link>{" "}
        / <span className="font-mono">{issue.ref}</span>
      </nav>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_16rem]">
        <div className="flex flex-col gap-4">
          <label htmlFor="issue-title" className="sr-only">
            Title
          </label>
          <input
            id="issue-title"
            value={title}
            readOnly={readOnly}
            maxLength={200}
            onChange={(event) => {
              setTitle(event.target.value);
            }}
            onBlur={() => {
              if (title.trim() && title !== issue.title) update.mutate({ title: title.trim() });
            }}
            className="wonky rounded-lg border border-transparent bg-transparent px-2 py-1 font-display text-2xl font-semibold outline-none hover:border-border focus-visible:border-focus-ring focus-visible:ring-4 focus-visible:ring-focus-ring/20"
          />
          <label htmlFor="issue-description" className="text-sm font-semibold">
            Description
          </label>
          <textarea
            id="issue-description"
            value={description}
            readOnly={readOnly}
            maxLength={10000}
            rows={8}
            onChange={(event) => {
              setDescription(event.target.value);
            }}
            onBlur={() => {
              if (description !== issue.description) update.mutate({ description });
            }}
            placeholder="Details, steps, links"
            className="rounded-lg border border-border-strong bg-bg px-3 py-2 outline-none focus-visible:border-focus-ring focus-visible:ring-4 focus-visible:ring-focus-ring/20"
          />
          {problem && <ErrorMessage>{problem}</ErrorMessage>}
          <p className="text-xs text-text-subtle">
            Opened by {issue.created_by?.display_name || issue.created_by?.username || "someone"} on{" "}
            {when.format(new Date(issue.created_at))}
            {issue.closed_at && `, closed ${when.format(new Date(issue.closed_at))}`}
          </p>
        </div>

        <Panel className="flex flex-col gap-4 p-4">
          <Field label="Status">
            <Select
              aria-label="Status"
              value={issue.status}
              disabled={readOnly}
              full
              onChange={(status: Status) => {
                update.mutate({ status });
              }}
              options={STATUSES.map((s) => ({ value: s, label: STATUS_LABELS[s] }))}
            />
          </Field>
          <Field label="Priority">
            <Select
              aria-label="Priority"
              value={issue.priority}
              disabled={readOnly}
              full
              onChange={(priority: Priority) => {
                update.mutate({ priority });
              }}
              options={PRIORITIES.map((p) => ({ value: p, label: PRIORITY_LABELS[p] }))}
            />
          </Field>
          <Field label="Assignee">
            <Select
              aria-label="Assignee"
              value={issue.assignee ? String(issue.assignee.id) : ""}
              disabled={readOnly}
              full
              onChange={(value) => {
                update.mutate({ assignee_id: value ? Number(value) : null });
              }}
              options={[
                { value: "", label: "Nobody" },
                ...(members.data ?? [])
                  .filter((m) => m.role !== "guest")
                  .map((m) => ({ value: String(m.user_id), label: m.display_name || m.username })),
              ]}
            />
          </Field>
          <Field label="Due">
            <input
              type="date"
              aria-label="Due"
              value={issue.due ?? ""}
              disabled={readOnly}
              onChange={(event) => {
                update.mutate({ due: event.target.value || null });
              }}
              className="h-10 w-full rounded-lg border border-border-strong bg-bg px-3 text-sm outline-none focus-visible:border-focus-ring focus-visible:ring-4 focus-visible:ring-focus-ring/20"
            />
          </Field>
          <Field label="Labels">
            <ul aria-label="Labels" className="flex flex-wrap gap-1.5">
              {labels.data?.map((label) => {
                const on = chosen.has(label.id);
                return (
                  <li key={label.id}>
                    <button
                      type="button"
                      aria-pressed={on}
                      disabled={readOnly}
                      onClick={() => {
                        const next = on
                          ? [...chosen].filter((id) => id !== label.id)
                          : [...chosen, label.id];
                        update.mutate({ label_ids: next });
                      }}
                      className={`rounded-full px-2.5 py-0.5 text-sm font-semibold ring-1 ring-transparent aria-pressed:ring-border-strong ${
                        on ? labelClass(label.color) : "bg-surface-sunken text-text-muted"
                      }`}
                    >
                      {label.name}
                    </button>
                  </li>
                );
              })}
              {labels.data?.length === 0 && (
                <li className="text-sm text-text-subtle">No labels in this project yet.</li>
              )}
            </ul>
          </Field>
        </Panel>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs font-semibold tracking-wide text-text-subtle uppercase">
        {label}
      </span>
      {children}
    </div>
  );
}
