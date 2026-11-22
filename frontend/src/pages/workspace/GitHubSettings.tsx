import { useState, type SubmitEvent } from "react";

import { useChannels } from "../../api/chat";
import {
  useConnectRepo,
  useRemoveWebhook,
  useWebhooks,
  type NewWebhook,
} from "../../api/integrations";
import { Select } from "../../components/Select";
import { ErrorMessage } from "../../components/ui";
import { ConfirmButton, Panel } from "../../components/workspace";
import { errorText } from "../../forms";

const inputClass =
  "h-10 rounded-lg border border-border-strong bg-bg px-3 text-sm outline-none focus-visible:border-focus-ring focus-visible:ring-4 focus-visible:ring-focus-ring/20";

export function GitHubSettings({ slug }: { slug: string }) {
  const channels = useChannels(slug);
  const webhooks = useWebhooks(slug);
  const connect = useConnectRepo(slug);
  const remove = useRemoveWebhook(slug);
  const choices = (channels.data ?? []).filter(
    (c) => (c.kind === "public" || c.kind === "private") && !c.archived,
  );
  const names = new Map((channels.data ?? []).map((c) => [c.id, c.name]));
  const [channelId, setChannelId] = useState<string | undefined>(undefined);
  const [repo, setRepo] = useState("");
  const [made, setMade] = useState<NewWebhook | null>(null);
  const chosen = channelId ?? (choices[0] ? String(choices[0].id) : undefined);

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!chosen || !repo.trim()) return;
    connect.mutate(
      { channel_id: Number(chosen), repo: repo.trim() },
      {
        onSuccess: (webhook) => {
          setMade(webhook);
          setRepo("");
        },
      },
    );
  }

  return (
    <Panel className="settle flex flex-col gap-4 p-5 sm:p-6">
      <div>
        <h2 className="font-display text-xl font-semibold">GitHub</h2>
        <p className="text-sm text-text-muted">
          Post pull requests and issues from a repository into a channel.
        </p>
      </div>

      <form onSubmit={submit} aria-label="Connect a repository" className="flex flex-wrap gap-2">
        <label htmlFor="github-repo" className="sr-only">
          Repository
        </label>
        <input
          id="github-repo"
          value={repo}
          onChange={(event) => {
            setRepo(event.target.value);
          }}
          placeholder="owner/name"
          className={`${inputClass} min-w-0 flex-1`}
        />
        <Select
          aria-label="Channel"
          value={chosen}
          onChange={setChannelId}
          options={choices.map((c) => ({ value: String(c.id), label: `#${c.name}` }))}
        />
        <button
          type="submit"
          disabled={connect.isPending || !chosen || !repo.trim()}
          className="h-10 rounded-lg bg-accent px-4 text-sm font-semibold text-on-accent hover:bg-accent-hover disabled:opacity-60"
        >
          Connect
        </button>
      </form>
      {connect.error && <ErrorMessage>{errorText(connect.error)}</ErrorMessage>}

      {made && (
        <div role="status" className="flex flex-col gap-2 rounded-lg bg-accent-soft p-4 text-sm">
          <p className="font-semibold text-accent-soft-text">
            Now add a webhook in {made.repo} on GitHub (Settings, Webhooks):
          </p>
          <dl className="grid gap-1 sm:grid-cols-[8rem_1fr]">
            <dt className="text-text-muted">Payload URL</dt>
            <dd className="font-mono break-all">{made.url}</dd>
            <dt className="text-text-muted">Content type</dt>
            <dd className="font-mono">application/json</dd>
            <dt className="text-text-muted">Secret</dt>
            <dd className="font-mono break-all">{made.secret}</dd>
            <dt className="text-text-muted">Events</dt>
            <dd>Pull requests and Issues</dd>
          </dl>
          <p className="text-text-muted">The secret is shown only now.</p>
        </div>
      )}

      {webhooks.data && webhooks.data.length > 0 && (
        <ul aria-label="Connected repositories" className="divide-y divide-border">
          {webhooks.data.map((webhook) => (
            <li key={webhook.id} className="flex flex-wrap items-center gap-3 py-3">
              <span className="min-w-0 flex-1 text-sm">
                <span className="font-mono font-semibold">{webhook.repo}</span> to #
                {names.get(webhook.channel) ?? "a channel"}
              </span>
              <ConfirmButton
                label="Remove"
                confirmLabel="Yes, remove"
                busy={remove.isPending}
                onConfirm={() => {
                  remove.mutate(webhook.id);
                }}
              />
            </li>
          ))}
        </ul>
      )}
      {remove.error && <ErrorMessage>{errorText(remove.error)}</ErrorMessage>}
    </Panel>
  );
}
