import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link, useOutletContext, useParams } from "react-router";

import {
  deleteMessage,
  editMessage,
  loadOlder,
  remember,
  sendMessage,
  useChannels,
  useJoinChannel,
  useTimeline,
  type Channel,
} from "../../api/chat";
import type { User } from "../../api/client";
import { ApiError } from "../../api/workspaces";
import { startsGroup, type Message } from "../../chat/timeline";
import { ErrorMessage } from "../../components/ui";
import { Avatar, ChannelIcon, ConfirmButton } from "../../components/workspace";
import type { WorkspaceContext } from "./Shell";

const clock = new Intl.DateTimeFormat("en", { hour: "numeric", minute: "2-digit" });

interface Pending {
  clientId: string;
  body: string;
  failed: boolean;
}

function problem(error: unknown): string {
  return error instanceof ApiError
    ? (error.problems.detail ??
        (Object.values(error.problems.fields).flat().join(" ") || error.message))
    : "Could not reach Baithak. Try again.";
}

function MessageRow({
  message,
  grouped,
  mine,
  slug,
  channel,
}: {
  message: Message;
  grouped: boolean;
  mine: boolean;
  slug: string;
  channel: Channel;
}) {
  const client = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.body);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const name = message.author ? message.author.display_name || message.author.username : "Someone";

  async function save() {
    setBusy(true);
    setError(null);
    try {
      remember(client, slug, channel.id, await editMessage(slug, channel.id, message.seq, draft));
      setEditing(false);
    } catch (failure) {
      setError(problem(failure));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await deleteMessage(slug, channel.id, message.seq);
    } catch (failure) {
      setError(problem(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li
      className={`group relative flex gap-3 rounded-lg px-2 hover:bg-bg-subtle ${grouped ? "py-0.5" : "mt-3 py-1"}`}
    >
      <div className="w-9 shrink-0">
        {!grouped && message.author && <Avatar name={name} colorKey={message.author.username} />}
      </div>
      <div className="min-w-0 flex-1">
        {!grouped && (
          <p className="flex items-baseline gap-2">
            <span className="font-semibold">{name}</span>
            <time dateTime={message.created_at} className="text-xs text-text-subtle tabular-nums">
              {clock.format(new Date(message.created_at))}
            </time>
          </p>
        )}
        {message.deleted ? (
          <p className="text-sm text-text-subtle italic">This message was deleted.</p>
        ) : editing ? (
          <div className="mt-1 flex flex-col gap-2">
            <textarea
              aria-label="Edit message"
              value={draft}
              onChange={(event) => {
                setDraft(event.target.value);
              }}
              rows={2}
              maxLength={4000}
              className="w-full resize-y rounded-lg border border-border-strong bg-bg px-3 py-2 outline-none focus-visible:border-focus-ring focus-visible:ring-4 focus-visible:ring-focus-ring/20"
            />
            <div className="flex gap-2 text-sm">
              <button
                type="button"
                disabled={busy || !draft.trim()}
                onClick={() => void save()}
                className="rounded-lg bg-accent px-3 py-1 font-semibold text-on-accent hover:bg-accent-hover disabled:opacity-60"
              >
                Save
              </button>
              <button
                type="button"
                onClick={() => {
                  setEditing(false);
                  setDraft(message.body);
                }}
                className="rounded-lg px-3 py-1 font-semibold text-text-muted hover:bg-surface"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <p className="break-words whitespace-pre-wrap">
            {message.body}
            {message.edited_at && <span className="ml-1 text-xs text-text-subtle">(edited)</span>}
          </p>
        )}
        {error && <ErrorMessage>{error}</ErrorMessage>}
      </div>
      {mine && !message.deleted && !editing && (
        <div className="absolute -top-3 right-2 hidden items-center gap-1 rounded-lg border border-border bg-surface-raised p-0.5 shadow-sm group-focus-within:flex group-hover:flex">
          {!channel.archived && (
            <button
              type="button"
              onClick={() => {
                setDraft(message.body);
                setEditing(true);
              }}
              className="rounded-md px-2 py-1 text-xs font-semibold hover:bg-bg-subtle"
            >
              Edit
            </button>
          )}
          <ConfirmButton
            label="Delete"
            confirmLabel="Yes, delete"
            busy={busy}
            onConfirm={() => void remove()}
          />
        </div>
      )}
    </li>
  );
}

function Composer({ slug, channel, me }: { slug: string; channel: Channel; me: User }) {
  const client = useQueryClient();
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<Pending[]>([]);
  const timeline = useTimeline(slug, channel.id);

  // A pending message is done once the timeline holds the stored copy, whichever arrived first:
  // the API's answer or the live event.
  const stored = new Set(
    timeline.data?.messages.filter((m) => m.author?.id === me.id).map((m) => m.client_id),
  );
  const waiting = pending.filter((item) => !stored.has(item.clientId));

  async function deliver(item: Pending) {
    setPending((now) =>
      now.map((p) => (p.clientId === item.clientId ? { ...p, failed: false } : p)),
    );
    try {
      remember(
        client,
        slug,
        channel.id,
        await sendMessage(slug, channel.id, item.body, item.clientId),
      );
    } catch {
      setPending((now) =>
        now.map((p) => (p.clientId === item.clientId ? { ...p, failed: true } : p)),
      );
    }
  }

  function submit() {
    const body = draft.trim();
    if (!body) return;
    // The same id goes with every retry, so the server stores the message once.
    const item = { clientId: crypto.randomUUID(), body, failed: false };
    setPending((now) => [...now.filter((p) => !stored.has(p.clientId)), item]);
    setDraft("");
    void deliver(item);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {waiting.length > 0 && (
        <ul className="flex flex-col gap-1 px-2" aria-label="Sending">
          {waiting.map((item) => (
            <li key={item.clientId} className="flex items-center gap-3 pl-12 text-text-muted">
              <span className="min-w-0 flex-1 break-words whitespace-pre-wrap">{item.body}</span>
              {item.failed ? (
                <button
                  type="button"
                  onClick={() => void deliver(item)}
                  className="shrink-0 text-sm font-semibold text-danger hover:underline"
                >
                  Not sent. Retry
                </button>
              ) : (
                <span className="shrink-0 text-xs">Sending</span>
              )}
            </li>
          ))}
        </ul>
      )}
      <div className="rounded-2xl border border-border-strong bg-surface p-2 focus-within:border-focus-ring focus-within:ring-4 focus-within:ring-focus-ring/20">
        <label htmlFor="composer" className="sr-only">
          Message #{channel.name}
        </label>
        <textarea
          id="composer"
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value);
          }}
          onKeyDown={onKeyDown}
          rows={2}
          maxLength={4000}
          placeholder={`Message #${channel.name}`}
          className="block w-full resize-none bg-transparent px-2 py-1 outline-none placeholder:text-text-subtle"
        />
        <div className="flex items-center justify-between px-2 pt-1">
          <span className="text-xs text-text-subtle">
            Enter to send, Shift+Enter for a new line
          </span>
          <button
            type="button"
            onClick={submit}
            disabled={!draft.trim()}
            className="btn-lamp rounded-lg bg-accent px-4 py-1.5 text-sm font-semibold text-on-accent hover:bg-accent-hover disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

export function ChannelView() {
  const { workspace, me } = useOutletContext<WorkspaceContext>();
  const { channelId = "" } = useParams();
  const id = Number(channelId);
  const channels = useChannels(workspace.slug);
  const channel = channels.data?.find((c) => c.id === id);

  if (channels.isPending) {
    return (
      <p role="status" className="text-text-muted">
        Loading
      </p>
    );
  }
  if (!channel) {
    return (
      <div className="flex flex-col gap-4">
        <ErrorMessage>This channel does not exist, or it is private.</ErrorMessage>
        <Link to={`/w/${workspace.slug}/channels`} className="font-semibold text-accent-text">
          See all channels
        </Link>
      </div>
    );
  }
  return <Conversation key={channel.id} slug={workspace.slug} channel={channel} me={me} />;
}

function Conversation({ slug, channel, me }: { slug: string; channel: Channel; me: User }) {
  const client = useQueryClient();
  const timeline = useTimeline(slug, channel.id);
  const joinChannel = useJoinChannel(slug);
  const scroller = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const messages = timeline.data?.messages ?? [];
  const newest = messages.at(-1)?.seq;

  // Follow new messages only when the reader is already at the bottom, never yank them away
  // from something older they are reading.
  useLayoutEffect(() => {
    const box = scroller.current;
    if (box && nearBottom.current) box.scrollTop = box.scrollHeight;
  }, [newest]);

  useEffect(() => {
    const box = scroller.current;
    if (!box) return;
    const track = () => {
      nearBottom.current = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
    };
    box.addEventListener("scroll", track);
    return () => {
      box.removeEventListener("scroll", track);
    };
  }, []);

  async function older() {
    setLoadingOlder(true);
    try {
      await loadOlder(client, slug, channel.id);
    } finally {
      setLoadingOlder(false);
    }
  }

  return (
    <div className="flex h-[calc(100dvh-4rem)] flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
        <div className="min-w-0">
          <h1 className="wonky flex items-center gap-2 font-display text-2xl font-semibold">
            <ChannelIcon kind={channel.kind} />
            {channel.name}
          </h1>
          {channel.topic && <p className="truncate text-sm text-text-muted">{channel.topic}</p>}
        </div>
        {channel.archived && (
          <span className="rounded-full bg-surface-sunken px-3 py-1 text-xs font-semibold text-text-muted">
            Archived
          </span>
        )}
      </header>

      <div
        ref={scroller}
        className="min-h-0 flex-1 overflow-y-auto"
        aria-live="polite"
        aria-relevant="additions"
      >
        {timeline.data?.hasMore && (
          <div className="flex justify-center py-2">
            <button
              type="button"
              onClick={() => void older()}
              disabled={loadingOlder}
              className="rounded-lg border border-border-strong px-3 py-1 text-sm font-semibold hover:bg-bg-subtle disabled:opacity-60"
            >
              {loadingOlder ? "Loading" : "Show earlier messages"}
            </button>
          </div>
        )}
        {timeline.isPending && (
          <p role="status" className="p-4 text-text-muted">
            Loading messages
          </p>
        )}
        {timeline.data && messages.length === 0 && (
          <p className="p-4 text-text-muted">
            This is the very start of #{channel.name}. Say salaam.
          </p>
        )}
        <ol>
          {messages.map((message, index) => (
            <MessageRow
              key={message.seq}
              message={message}
              grouped={!startsGroup(messages[index - 1], message)}
              mine={message.author?.id === me.id}
              slug={slug}
              channel={channel}
            />
          ))}
        </ol>
      </div>

      {channel.is_member && !channel.archived ? (
        <Composer slug={slug} channel={channel} me={me} />
      ) : channel.archived ? (
        <p className="rounded-xl bg-surface-sunken px-4 py-3 text-sm text-text-muted">
          This channel is archived. You can read it, but not post.
        </p>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface px-4 py-3">
          <p className="text-text-muted">You are reading #{channel.name}. Join to post.</p>
          <button
            type="button"
            disabled={joinChannel.isPending}
            onClick={() => {
              joinChannel.mutate(channel.id);
            }}
            className="rounded-lg bg-accent px-4 py-1.5 font-semibold text-on-accent hover:bg-accent-hover disabled:opacity-60"
          >
            Join #{channel.name}
          </button>
        </div>
      )}
    </div>
  );
}
