import { useState, type ReactNode, type SubmitEvent } from "react";

import { useChannels, type Channel } from "../../api/chat";
import {
  useCreateWebhook,
  useDeliveries,
  useRemoveWebhook,
  useWebhooks,
  type Delivery,
  type NewWebhook,
  type Webhook,
} from "../../api/integrations";
import { Select } from "../../components/Select";
import { ErrorMessage } from "../../components/ui";
import { ConfirmButton, Panel } from "../../components/workspace";
import { errorText } from "../../forms";

const inputClass =
  "h-10 min-w-0 flex-1 rounded-lg border border-border-strong bg-bg px-3 text-sm outline-none focus-visible:border-focus-ring focus-visible:ring-4 focus-visible:ring-focus-ring/20";

export function IntegrationSettings({ slug }: { slug: string }) {
  const channels = useChannels(slug);
  const webhooks = useWebhooks(slug);
  const choices = (channels.data ?? []).filter(
    (c) => (c.kind === "public" || c.kind === "private") && !c.archived,
  );
  const names = new Map((channels.data ?? []).map((c) => [c.id, c.name]));
  const of = (kind: Webhook["kind"]) => (webhooks.data ?? []).filter((w) => w.kind === kind);

  return (
    <>
      <Section
        slug={slug}
        kind="github"
        title="GitHub"
        intro="Post pull requests and issues from a repository into a channel."
        field={{ label: "Repository", placeholder: "owner/name", key: "repo" }}
        choices={choices}
        connected={of("github")}
        describe={(w) => `${w.repo} to #${names.get(w.channel) ?? "a channel"}`}
        made={(w) => (
          <>
            <p className="font-semibold text-accent-soft-text">
              Now add a webhook in {w.repo} on GitHub (Settings, Webhooks):
            </p>
            <dl className="grid gap-1 sm:grid-cols-[8rem_1fr]">
              <dt className="text-text-muted">Payload URL</dt>
              <dd className="font-mono break-all">{w.url}</dd>
              <dt className="text-text-muted">Content type</dt>
              <dd className="font-mono">application/json</dd>
              <dt className="text-text-muted">Secret</dt>
              <dd className="font-mono break-all">{w.secret}</dd>
              <dt className="text-text-muted">Events</dt>
              <dd>Pull requests and Issues</dd>
            </dl>
            <p className="text-text-muted">The secret is shown only now.</p>
          </>
        )}
      />
      <Section
        slug={slug}
        kind="incoming"
        title="Incoming webhooks"
        intro="A secret address other tools post messages to. Anyone with it can post, so keep it private."
        field={{ label: "Name", placeholder: "Deploy bot", key: "name" }}
        choices={choices}
        connected={of("incoming")}
        describe={(w) => `${w.name} to #${names.get(w.channel) ?? "a channel"}`}
        made={(w) => (
          <>
            <p className="font-semibold text-accent-soft-text">
              Post JSON to this address. It is shown only now:
            </p>
            <p className="font-mono break-all">{w.url}</p>
            <pre className="overflow-x-auto rounded bg-bg p-2 font-mono text-xs">
              {`curl -X POST -H "Content-Type: application/json" \\\n  -d '{"text": "Deployed"}' ${w.url}`}
            </pre>
            <p className="text-text-muted">Up to 30 messages a minute.</p>
          </>
        )}
      />
    </>
  );
}

function Section({
  slug,
  kind,
  title,
  intro,
  field,
  choices,
  connected,
  describe,
  made,
}: {
  slug: string;
  kind: Webhook["kind"];
  title: string;
  intro: string;
  field: { label: string; placeholder: string; key: "repo" | "name" };
  choices: Channel[];
  connected: Webhook[];
  describe: (webhook: Webhook) => string;
  made: (webhook: NewWebhook) => ReactNode;
}) {
  const create = useCreateWebhook(slug);
  const remove = useRemoveWebhook(slug);
  const [channelId, setChannelId] = useState<string | undefined>(undefined);
  const [value, setValue] = useState("");
  const [fresh, setFresh] = useState<NewWebhook | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const chosen = channelId ?? (choices[0] ? String(choices[0].id) : undefined);
  const inputId = `${kind}-${field.key}`;

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!chosen || !value.trim()) return;
    create.mutate(
      { kind, channel_id: Number(chosen), [field.key]: value.trim() },
      {
        onSuccess: (webhook) => {
          setFresh(webhook);
          setValue("");
        },
      },
    );
  }

  return (
    <Panel className="settle flex flex-col gap-4 p-5 sm:p-6">
      <div>
        <h2 className="font-display text-xl font-semibold">{title}</h2>
        <p className="text-sm text-text-muted">{intro}</p>
      </div>
      <form onSubmit={submit} aria-label={title} className="flex flex-wrap gap-2">
        <label htmlFor={inputId} className="sr-only">
          {field.label}
        </label>
        <input
          id={inputId}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
          }}
          placeholder={field.placeholder}
          className={inputClass}
        />
        <Select
          aria-label="Channel"
          value={chosen}
          onChange={setChannelId}
          options={choices.map((c) => ({ value: String(c.id), label: `#${c.name}` }))}
        />
        <button
          type="submit"
          disabled={create.isPending || !chosen || !value.trim()}
          className="h-10 rounded-lg bg-accent px-4 text-sm font-semibold text-on-accent hover:bg-accent-hover disabled:opacity-60"
        >
          Add
        </button>
      </form>
      {create.error && <ErrorMessage>{errorText(create.error)}</ErrorMessage>}
      {fresh && (
        <div role="status" className="flex flex-col gap-2 rounded-lg bg-accent-soft p-4 text-sm">
          {made(fresh)}
        </div>
      )}
      {connected.length > 0 && (
        <ul aria-label={`${title} connected`} className="divide-y divide-border">
          {connected.map((webhook) => (
            <li key={webhook.id} className="flex flex-wrap items-center gap-3 py-3">
              <span className="min-w-0 flex-1 text-sm">{describe(webhook)}</span>
              <button
                type="button"
                aria-expanded={open === webhook.id}
                onClick={() => {
                  setOpen((now) => (now === webhook.id ? null : webhook.id));
                }}
                className="rounded-lg px-3 py-1.5 text-sm font-semibold text-text-muted hover:bg-bg-subtle"
              >
                Deliveries
              </button>
              <ConfirmButton
                label="Remove"
                confirmLabel="Yes, remove"
                busy={remove.isPending}
                onConfirm={() => {
                  remove.mutate(webhook.id);
                }}
              />
              {open === webhook.id && <DeliveryLog slug={slug} id={webhook.id} />}
            </li>
          ))}
        </ul>
      )}
      {remove.error && <ErrorMessage>{errorText(remove.error)}</ErrorMessage>}
    </Panel>
  );
}

const when = new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" });

const STATUS_LABELS: Record<Delivery["status"], string> = {
  pending: "Waiting",
  posted: "Posted",
  ignored: "Ignored",
  failed: "Failed",
};

function DeliveryLog({ slug, id }: { slug: string; id: number }) {
  const log = useDeliveries(slug, id);
  if (log.isPending) return <p className="w-full text-sm text-text-muted">Loading</p>;
  if (log.isError) return <ErrorMessage>Could not load deliveries.</ErrorMessage>;
  if (log.data.length === 0) {
    return <p className="w-full text-sm text-text-muted">Nothing has arrived yet.</p>;
  }
  return (
    <ol
      aria-label="Deliveries"
      className="w-full divide-y divide-border rounded-lg bg-bg-subtle text-sm"
    >
      {log.data.map((delivery) => (
        <li key={delivery.id} className="flex flex-wrap items-baseline gap-x-3 px-3 py-2">
          <span
            className={delivery.status === "failed" ? "font-semibold text-danger" : "font-semibold"}
          >
            {STATUS_LABELS[delivery.status]}
          </span>
          <span className="font-mono text-xs">{delivery.event}</span>
          {delivery.detail && <span className="text-text-muted">{delivery.detail}</span>}
          {delivery.attempts > 1 && (
            <span className="text-text-subtle">{delivery.attempts} tries</span>
          )}
          <time dateTime={delivery.received_at} className="ml-auto text-xs text-text-subtle">
            {when.format(new Date(delivery.received_at))}
          </time>
        </li>
      ))}
    </ol>
  );
}
