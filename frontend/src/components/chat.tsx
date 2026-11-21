import { useQueryClient } from "@tanstack/react-query";
import { useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import { deleteMessage, editMessage, remember, type Channel } from "../api/chat";
import { ApiError } from "../api/workspaces";
import {
  activeQuery,
  insertMention,
  mentionsMe,
  segments,
  suggest,
  type Candidate,
} from "../chat/mentions";
import type { Message } from "../chat/timeline";
import { ErrorMessage } from "./ui";
import { Avatar, ConfirmButton } from "./workspace";

const clock = new Intl.DateTimeFormat("en", { hour: "numeric", minute: "2-digit" });

function problem(error: unknown): string {
  return error instanceof ApiError
    ? (error.problems.detail ??
        (Object.values(error.problems.fields).flat().join(" ") || error.message))
    : "Could not reach Baithak. Try again.";
}

function replies(count: number): string {
  return count === 1 ? "1 reply" : `${String(count)} replies`;
}

const actionClass = "rounded-md px-2 py-1 text-xs font-semibold hover:bg-bg-subtle";

const mentionClass = {
  person: "font-semibold text-accent-text",
  me: "rounded bg-mention px-0.5 font-semibold ring-1 ring-mention-edge",
  channel: "rounded bg-mention px-0.5 font-semibold ring-1 ring-mention-edge",
};

function Body({ message, meId }: { message: Message; meId: number }) {
  return (
    <>
      {segments(message, meId).map((part, index) =>
        "mention" in part ? (
          <span key={index} className={mentionClass[part.mention]}>
            {part.text}
          </span>
        ) : (
          part.text
        ),
      )}
    </>
  );
}

export function MessageRow({
  message,
  grouped,
  meId,
  slug,
  channel,
  onOpenThread,
}: {
  message: Message;
  grouped: boolean;
  meId: number;
  slug: string;
  channel: Channel;
  /** Shows the thread links and the Reply action; left out inside a thread. */
  onOpenThread?: (seq: number) => void;
}) {
  const client = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.body);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const name = message.author ? message.author.display_name || message.author.username : "Someone";
  const mine = message.author?.id === meId;
  const forMe = !mine && !message.deleted && mentionsMe(message, meId);
  const threadSeq = message.parent_seq === null ? message.seq : null;
  const canEdit = mine && !message.deleted && !editing;
  const canReply = onOpenThread !== undefined && threadSeq !== null && !editing;

  async function save() {
    setBusy(true);
    setError(null);
    try {
      remember(client, slug, channel.id, await editMessage(slug, channel.id, message, draft));
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
      await deleteMessage(slug, channel.id, message);
    } catch (failure) {
      setError(problem(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li
      className={`group relative flex gap-3 rounded-lg px-2 ${
        forMe ? "border-l-2 border-mention-edge bg-mention" : "hover:bg-bg-subtle"
      } ${grouped ? "py-0.5" : "mt-3 py-1"}`}
    >
      <div className="w-9 shrink-0">
        {!grouped && message.author && <Avatar name={name} colorKey={message.author.username} />}
      </div>
      <div className="min-w-0 flex-1">
        {onOpenThread && message.parent_seq !== null && (
          <button
            type="button"
            onClick={() => {
              if (message.parent_seq !== null) onOpenThread(message.parent_seq);
            }}
            className="text-xs text-text-subtle hover:text-accent-text hover:underline"
          >
            Replied in a thread
          </button>
        )}
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
            <Body message={message} meId={meId} />
            {message.edited_at && <span className="ml-1 text-xs text-text-subtle">(edited)</span>}
          </p>
        )}
        {onOpenThread && threadSeq !== null && message.reply_count > 0 && (
          <button
            type="button"
            onClick={() => {
              onOpenThread(threadSeq);
            }}
            className="mt-1 text-sm font-semibold text-accent-text hover:underline"
          >
            {replies(message.reply_count)}
          </button>
        )}
        {error && <ErrorMessage>{error}</ErrorMessage>}
      </div>
      {(canEdit || canReply) && (
        <div className="absolute -top-3 right-2 hidden items-center gap-1 rounded-lg border border-border bg-surface-raised p-0.5 shadow-sm group-focus-within:flex group-hover:flex">
          {canReply && (
            <button
              type="button"
              onClick={() => {
                onOpenThread(threadSeq);
              }}
              className={actionClass}
            >
              Reply
            </button>
          )}
          {canEdit && !channel.archived && (
            <button
              type="button"
              onClick={() => {
                setDraft(message.body);
                setEditing(true);
              }}
              className={actionClass}
            >
              Edit
            </button>
          )}
          {canEdit && (
            <ConfirmButton
              label="Delete"
              confirmLabel="Yes, delete"
              busy={busy}
              onConfirm={() => void remove()}
            />
          )}
        </div>
      )}
    </li>
  );
}

interface Pending {
  clientId: string;
  body: string;
  failed: boolean;
}

export function Composer({
  id,
  label,
  stored,
  send,
  footer,
  candidates = [],
}: {
  id: string;
  label: string;
  /** People (and @channel) offered after typing "@". */
  candidates?: Candidate[];
  /** client_ids of my messages already stored where this composer sends. */
  stored: Set<string>;
  send: (body: string, clientId: string) => Promise<void>;
  footer?: ReactNode;
}) {
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<Pending[]>([]);
  const area = useRef<HTMLTextAreaElement>(null);
  const [caret, setCaret] = useState(0);
  const [active, setActive] = useState(0);
  const [dismissedAt, setDismissedAt] = useState<number | null>(null);
  const moveCaretTo = useRef<number | null>(null);
  const query = activeQuery(draft, caret);
  const options = query && query.start !== dismissedAt ? suggest(candidates, query.query) : [];
  const open = options.length > 0;
  const current = Math.min(active, options.length - 1);

  useLayoutEffect(() => {
    if (moveCaretTo.current === null || !area.current) return;
    area.current.setSelectionRange(moveCaretTo.current, moveCaretTo.current);
    moveCaretTo.current = null;
  }, [draft]);

  function choose(candidate: Candidate) {
    if (!query) return;
    const next = insertMention(draft, query.start, caret, candidate.username);
    moveCaretTo.current = next.caret;
    setDraft(next.text);
    setCaret(next.caret);
    area.current?.focus();
  }
  // A pending message is done once the stored copy is shown, whichever arrived first: the API's
  // answer or the live event.
  const waiting = pending.filter((item) => !stored.has(item.clientId));

  async function deliver(item: Pending) {
    setPending((now) =>
      now.map((p) => (p.clientId === item.clientId ? { ...p, failed: false } : p)),
    );
    try {
      await send(item.body, item.clientId);
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
    if (open && !event.nativeEvent.isComposing) {
      const picked = options[current];
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const step = event.key === "ArrowDown" ? 1 : -1;
        setActive((current + step + options.length) % options.length);
        return;
      }
      if ((event.key === "Enter" || event.key === "Tab") && picked) {
        event.preventDefault();
        choose(picked);
        return;
      }
      if (event.key === "Escape" && query) {
        event.preventDefault();
        setDismissedAt(query.start);
        return;
      }
    }
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
      <div className="relative rounded-2xl border border-border-strong bg-surface p-2 focus-within:border-focus-ring focus-within:ring-4 focus-within:ring-focus-ring/20">
        {open && (
          <ul
            id={`${id}-mentions`}
            role="listbox"
            aria-label="People to mention"
            className="settle absolute inset-x-2 bottom-full z-20 mb-2 overflow-hidden rounded-xl border border-border bg-surface-raised p-1 shadow-lg"
          >
            {options.map((candidate, index) => (
              <li
                key={candidate.username}
                id={`${id}-mention-${candidate.username}`}
                role="option"
                aria-selected={index === current}
                onMouseDown={(event) => {
                  event.preventDefault();
                  choose(candidate);
                }}
                className="flex cursor-pointer items-baseline gap-2 rounded-lg px-3 py-1.5 text-sm aria-selected:bg-bg-subtle"
              >
                <span className="font-semibold">@{candidate.username}</span>
                {candidate.display_name && (
                  <span className="truncate text-text-muted">{candidate.display_name}</span>
                )}
              </li>
            ))}
          </ul>
        )}
        <label htmlFor={id} className="sr-only">
          {label}
        </label>
        <textarea
          ref={area}
          id={id}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={open ? `${id}-mentions` : undefined}
          aria-activedescendant={
            open && options[current] ? `${id}-mention-${options[current].username}` : undefined
          }
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value);
            setCaret(event.target.selectionStart);
            setActive(0);
          }}
          onSelect={(event) => {
            setCaret(event.currentTarget.selectionStart);
          }}
          onKeyDown={onKeyDown}
          rows={2}
          maxLength={4000}
          placeholder={label}
          className="block w-full resize-none bg-transparent px-2 py-1 outline-none placeholder:text-text-subtle"
        />
        <div className="flex flex-wrap items-center justify-between gap-2 px-2 pt-1">
          {footer ?? (
            <span className="text-xs text-text-subtle">
              Enter to send, Shift+Enter for a new line
            </span>
          )}
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
