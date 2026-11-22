import { useState, type SubmitEvent } from "react";
import { Link } from "react-router";

import { useOpenIssue, useProjects } from "../api/issues";
import { errorText } from "../forms";
import type { Message } from "../chat/timeline";
import { titleFrom } from "../issues";
import { Select } from "./Select";
import { ErrorMessage } from "./ui";

export function IssueChip({ slug, issue }: { slug: string; issue: NonNullable<Message["issue"]> }) {
  return (
    <Link
      to={`/w/${slug}/projects/${issue.project}/issues/${String(issue.number)}`}
      className="mt-1 inline-flex items-center gap-1.5 rounded-full border border-border bg-bg px-2.5 py-0.5 text-sm font-semibold text-accent-text hover:border-border-strong"
    >
      <span className="text-text-subtle">Issue</span>
      <span className="font-mono">{issue.ref}</span>
    </Link>
  );
}

export function IssueFromMessage({
  slug,
  channelId,
  message,
  onDone,
}: {
  slug: string;
  channelId: number;
  message: Message;
  onDone: () => void;
}) {
  const projects = useProjects(slug);
  const open = useOpenIssue(slug);
  const choices = (projects.data ?? []).filter((project) => !project.archived);
  const [key, setKey] = useState<string | undefined>(undefined);
  const [title, setTitle] = useState(() => titleFrom(message.body));
  const chosen = key ?? choices[0]?.key;

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!chosen || !title.trim() || message.seq === null) return;
    open.mutate(
      {
        key: chosen,
        body: { title: title.trim(), from_message: { channel_id: channelId, seq: message.seq } },
      },
      { onSuccess: onDone },
    );
  }

  const problem = errorText(open.error);

  if (projects.isSuccess && choices.length === 0) {
    return (
      <div className="mt-2 flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface p-3 text-sm">
        <p className="text-text-muted">There is no open project to put an issue in yet.</p>
        <button type="button" onClick={onDone} className="font-semibold text-text-muted">
          Close
        </button>
      </div>
    );
  }

  return (
    <form
      aria-label="Open an issue"
      onSubmit={submit}
      className="mt-2 flex flex-col gap-2 rounded-lg border border-border bg-surface p-3"
    >
      <div className="flex flex-wrap gap-2">
        <Select
          aria-label="Project"
          value={chosen}
          onChange={setKey}
          options={choices.map((project) => ({
            value: project.key,
            label: `${project.key} ${project.name}`,
          }))}
        />
        <label htmlFor={`issue-title-${String(message.id)}`} className="sr-only">
          Issue title
        </label>
        <input
          id={`issue-title-${String(message.id)}`}
          value={title}
          maxLength={200}
          onChange={(event) => {
            setTitle(event.target.value);
          }}
          className="h-10 min-w-0 flex-1 rounded-lg border border-border-strong bg-bg px-3 text-sm outline-none focus-visible:border-focus-ring focus-visible:ring-4 focus-visible:ring-focus-ring/20"
        />
      </div>
      <p className="text-xs text-text-subtle">
        Replies to this message become the issue's discussion.
      </p>
      {problem && <ErrorMessage>{problem}</ErrorMessage>}
      <div className="flex gap-2 text-sm">
        <button
          type="submit"
          disabled={open.isPending || !chosen || !title.trim()}
          className="rounded-lg bg-accent px-3 py-1 font-semibold text-on-accent hover:bg-accent-hover disabled:opacity-60"
        >
          Open issue
        </button>
        <button
          type="button"
          onClick={onDone}
          className="rounded-lg px-3 py-1 font-semibold text-text-muted hover:bg-surface"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
