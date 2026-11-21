import { useState, type DragEvent } from "react";
import { Link, useOutletContext, useParams } from "react-router";

import { useBoardColumn, useMoveIssue, useProject, type Issue } from "../../api/issues";
import { Select } from "../../components/Select";
import { ErrorMessage } from "../../components/ui";
import { Avatar } from "../../components/workspace";
import { labelClass, PRIORITY_LABELS, STATUS_LABELS, STATUSES, type Status } from "../../issues";
import { ProjectHeader } from "./Project";
import type { WorkspaceContext } from "./Shell";

// Dragged cards carry their number under this type, so drops from elsewhere are ignored.
const DRAG_TYPE = "application/x-baithak-issue";

export function Board() {
  const { workspace } = useOutletContext<WorkspaceContext>();
  const { key = "" } = useParams();
  const project = useProject(workspace.slug, key);
  const move = useMoveIssue(workspace.slug, key);
  const [dragging, setDragging] = useState<Issue | null>(null);

  if (project.isError) return <ErrorMessage>This project does not exist.</ErrorMessage>;
  const readOnly = project.data?.archived ?? true;

  return (
    <div className="flex flex-col gap-6">
      <ProjectHeader slug={workspace.slug} projectKey={key} project={project.data} />
      {move.isError && <ErrorMessage>That move did not save, so the card went back.</ErrorMessage>}
      <div className="-mx-1 flex gap-4 overflow-x-auto px-1 pb-2">
        {STATUSES.map((status) => (
          <Column
            key={status}
            slug={workspace.slug}
            projectKey={key}
            status={status}
            readOnly={readOnly}
            dragging={dragging}
            onDrag={setDragging}
            onMove={(issue, to) => {
              if (issue.status !== to) move.mutate({ issue, status: to });
            }}
          />
        ))}
      </div>
    </div>
  );
}

function Column({
  slug,
  projectKey,
  status,
  readOnly,
  dragging,
  onDrag,
  onMove,
}: {
  slug: string;
  projectKey: string;
  status: Status;
  readOnly: boolean;
  dragging: Issue | null;
  onDrag: (issue: Issue | null) => void;
  onMove: (issue: Issue, status: Status) => void;
}) {
  const column = useBoardColumn(slug, projectKey, status);
  const [over, setOver] = useState(false);
  const cards = column.data?.results ?? [];
  const hidden = (column.data?.total ?? 0) - cards.length;
  const canDrop = !readOnly && dragging !== null && dragging.status !== status;

  function drop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    setOver(false);
    if (dragging && canDrop) onMove(dragging, status);
    onDrag(null);
  }

  return (
    <section
      aria-labelledby={`column-${status}`}
      onDragOver={(event) => {
        if (!canDrop || !event.dataTransfer.types.includes(DRAG_TYPE)) return;
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => {
        setOver(false);
      }}
      onDrop={drop}
      className={`flex w-72 shrink-0 flex-col gap-2 rounded-2xl border p-3 transition-colors ${
        over ? "border-focus-ring bg-accent-soft/40" : "border-border bg-bg-subtle"
      }`}
    >
      <h2
        id={`column-${status}`}
        className="flex items-center justify-between px-1 text-sm font-semibold"
      >
        {STATUS_LABELS[status]}
        <span className="text-xs text-text-subtle tabular-nums">{column.data?.total ?? ""}</span>
      </h2>
      <ul aria-label={STATUS_LABELS[status]} className="flex min-h-16 flex-col gap-2">
        {cards.map((issue) => (
          <Card
            key={issue.number}
            slug={slug}
            projectKey={projectKey}
            issue={issue}
            readOnly={readOnly}
            onDrag={onDrag}
            onMove={onMove}
          />
        ))}
      </ul>
      {hidden > 0 && (
        <Link
          to={`/w/${slug}/projects/${projectKey}`}
          className="px-1 text-xs font-semibold text-accent-text hover:underline"
        >
          {hidden} more in the list
        </Link>
      )}
    </section>
  );
}

function Card({
  slug,
  projectKey,
  issue,
  readOnly,
  onDrag,
  onMove,
}: {
  slug: string;
  projectKey: string;
  issue: Issue;
  readOnly: boolean;
  onDrag: (issue: Issue | null) => void;
  onMove: (issue: Issue, status: Status) => void;
}) {
  return (
    <li
      draggable={!readOnly}
      onDragStart={(event) => {
        event.dataTransfer.setData(DRAG_TYPE, String(issue.number));
        event.dataTransfer.effectAllowed = "move";
        onDrag(issue);
      }}
      onDragEnd={() => {
        onDrag(null);
      }}
      className={`flex flex-col gap-2 rounded-xl border border-border bg-surface p-3 shadow-sm ${
        readOnly ? "" : "cursor-grab active:cursor-grabbing"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <Link
          to={`/w/${slug}/projects/${projectKey}/issues/${String(issue.number)}`}
          className="min-w-0 text-sm font-semibold hover:underline"
        >
          <span className="mr-1.5 font-mono text-xs font-normal text-text-subtle">{issue.ref}</span>
          {issue.title}
        </Link>
        {issue.assignee && (
          <Avatar
            name={issue.assignee.display_name || issue.assignee.username}
            colorKey={issue.assignee.username}
            size="sm"
          />
        )}
      </div>
      {(issue.labels.length > 0 || issue.priority !== "none") && (
        <div className="flex flex-wrap items-center gap-1.5">
          {issue.priority !== "none" && (
            <span className="text-xs font-semibold text-text-muted">
              {PRIORITY_LABELS[issue.priority]}
            </span>
          )}
          {issue.labels.map((label) => (
            <span
              key={label.id}
              className={`rounded-full px-2 py-0.5 text-xs font-semibold ${labelClass(label.color)}`}
            >
              {label.name}
            </span>
          ))}
        </div>
      )}
      {/* Dragging needs a mouse; this moves a card from the keyboard or a phone. */}
      {!readOnly && (
        <Select
          aria-label={`Status of ${issue.ref}`}
          value={issue.status}
          full
          onChange={(status: Status) => {
            onMove(issue, status);
          }}
          options={STATUSES.map((s) => ({ value: s, label: STATUS_LABELS[s] }))}
        />
      )}
    </li>
  );
}
