import { useQueryClient } from "@tanstack/react-query";
import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import { deleteMessage, editMessage, react, remember, type Channel } from "../api/chat";
import { ApiError } from "../api/workspaces";
import { activeQuery, insertMention, mentionsMe, suggest, type Candidate } from "../chat/mentions";
import { QUICK_REACTIONS, reactedByMe, whoReacted } from "../chat/reactions";
import { typingText, type Person } from "../chat/presence";
import {
  fileProblem,
  fitWithin,
  formatSize,
  isImage,
  MAX_FILES,
  type Attachment,
} from "../chat/files";
import type { Message } from "../chat/timeline";
import { Formatted } from "./Formatted";
import { IssueChip, IssueFromMessage } from "./IssueFromMessage";
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

function ReactionPicker({
  onPick,
  onClose,
}: {
  onPick: (emoji: string) => void;
  onClose: () => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    box.current?.querySelector("button")?.focus();
    const outside = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) onClose();
    };
    document.addEventListener("mousedown", outside);
    return () => {
      document.removeEventListener("mousedown", outside);
    };
  }, [onClose]);
  return (
    <div
      ref={box}
      role="group"
      aria-label="Pick a reaction"
      onKeyDown={(event) => {
        if (event.key === "Escape") onClose();
      }}
      className="settle absolute top-6 right-2 z-20 grid grid-cols-8 gap-0.5 rounded-xl border border-border bg-surface-raised p-1.5 shadow-lg"
    >
      {QUICK_REACTIONS.map(({ emoji, name }) => (
        <button
          key={emoji}
          type="button"
          aria-label={name}
          title={name}
          onClick={() => {
            onPick(emoji);
          }}
          className="grid size-8 place-items-center rounded-lg text-lg hover:bg-bg-subtle focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
        >
          {emoji}
        </button>
      ))}
    </div>
  );
}

const actionClass = "rounded-md px-2 py-1 text-xs font-semibold hover:bg-bg-subtle";

function Attachments({ attachments }: { attachments: Attachment[] }) {
  return (
    <ul aria-label="Files" className="mt-1 flex flex-wrap gap-2">
      {attachments.map((attachment) => {
        const box = fitWithin(attachment.width, attachment.height, 320);
        return (
          <li key={attachment.id} className="max-w-full">
            {isImage(attachment) ? (
              <a href={attachment.url} target="_blank" rel="noopener noreferrer">
                <img
                  src={attachment.preview_url ?? attachment.url}
                  alt={attachment.name}
                  loading="lazy"
                  width={box?.width}
                  height={box?.height}
                  className="max-h-80 max-w-full rounded-lg border border-border bg-bg-subtle object-contain"
                />
              </a>
            ) : (
              <a
                href={attachment.url}
                download={attachment.name}
                className="flex max-w-xs items-center gap-3 rounded-xl border border-border bg-bg px-3 py-2 hover:border-border-strong"
              >
                <svg
                  viewBox="0 0 20 20"
                  className="size-5 shrink-0 text-text-subtle"
                  aria-hidden="true"
                >
                  <path
                    d="M5 2.5h6.5L15 6v11.5H5z M11.5 2.5V6H15"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.4"
                    strokeLinejoin="round"
                  />
                </svg>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold">{attachment.name}</span>
                  <span className="block text-xs text-text-subtle">
                    {formatSize(attachment.size)}
                  </span>
                </span>
              </a>
            )}
          </li>
        );
      })}
    </ul>
  );
}

// An app's message gets links only into GitHub (apps/core/github.py); people's messages are
// formatted by components/Formatted.tsx.
const GITHUB_LINK = /^https:\/\/github\.com\/\S+$/;

function IntegrationBody({ message }: { message: Message }) {
  return (
    <>
      {message.body.split(/(\s+)/).map((part, index) =>
        GITHUB_LINK.test(part) ? (
          <a
            key={index}
            href={part}
            target="_blank"
            rel="noreferrer noopener"
            className="text-accent-text underline"
          >
            {part}
          </a>
        ) : (
          part
        ),
      )}
    </>
  );
}

function MessageText({ message, meId }: { message: Message; meId: number }) {
  const edited = message.edited_at && (
    <span className="ml-1 text-xs text-text-subtle">(edited)</span>
  );
  if (message.kind === "integration") {
    return (
      <p className="break-words whitespace-pre-wrap">
        <IntegrationBody message={message} />
        {edited}
      </p>
    );
  }
  return <Formatted message={message} meId={meId} trailing={edited} />;
}

export function MessageRow({
  message,
  grouped,
  meId,
  slug,
  channel,
  onOpenThread,
  canSeeIssues = false,
}: {
  message: Message;
  grouped: boolean;
  meId: number;
  slug: string;
  channel: Channel;
  /** Shows the thread links and the Reply action; left out inside a thread. */
  onOpenThread?: (seq: number) => void;
  canSeeIssues?: boolean;
}) {
  const client = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.body);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const name = message.author
    ? message.author.display_name || message.author.username
    : message.sender_name || "Deleted account";
  const mine = message.author?.id === meId;
  const forMe = !mine && !message.deleted && mentionsMe(message, meId);
  const threadSeq = message.parent_seq === null ? message.seq : null;
  const canEdit = mine && !message.deleted && !editing;
  const canReply = onOpenThread !== undefined && threadSeq !== null && !editing;
  const canReact = channel.is_member && !channel.archived && !message.deleted && !editing;
  const [picking, setPicking] = useState(false);
  const [filing, setFiling] = useState(false);
  const canFile =
    canSeeIssues && threadSeq !== null && !message.issue && !message.deleted && !editing;

  async function toggle(emoji: string, on: boolean) {
    setPicking(false);
    setError(null);
    try {
      remember(client, slug, channel.id, await react(slug, channel.id, message, emoji, on));
    } catch (failure) {
      setError(problem(failure));
    }
  }

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

  if (message.kind === "activity") {
    return (
      <li className="flex gap-3 px-2 py-1 text-sm text-text-muted">
        <div className="w-9 shrink-0" />
        <p className="min-w-0 flex-1 break-words">
          {onOpenThread && message.parent_seq !== null && (
            <button
              type="button"
              onClick={() => {
                if (message.parent_seq !== null) onOpenThread(message.parent_seq);
              }}
              className="mr-2 text-xs text-text-subtle hover:text-accent-text hover:underline"
            >
              In a thread
            </button>
          )}
          <span className="font-semibold text-text">{name}</span>{" "}
          {message.deleted ? <em>removed this update</em> : message.body}{" "}
          <time dateTime={message.created_at} className="text-xs text-text-subtle tabular-nums">
            {clock.format(new Date(message.created_at))}
          </time>
        </p>
      </li>
    );
  }

  return (
    <li
      className={`group relative flex gap-3 rounded-lg px-2 ${
        forMe ? "border-l-2 border-mention-edge bg-mention" : "hover:bg-bg-subtle"
      } ${grouped ? "py-0.5" : "mt-3 py-1"}`}
    >
      <div className="w-9 shrink-0">
        {!grouped && <Avatar name={name} colorKey={message.author?.username ?? name} />}
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
            {message.kind === "integration" && (
              <span className="rounded bg-surface-sunken px-1.5 text-xs font-semibold text-text-muted">
                App
              </span>
            )}
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
          <MessageText message={message} meId={meId} />
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
        {message.attachments.length > 0 && <Attachments attachments={message.attachments} />}
        {canSeeIssues && message.issue && <IssueChip slug={slug} issue={message.issue} />}
        {filing && canFile && (
          <IssueFromMessage
            slug={slug}
            channelId={channel.id}
            message={message}
            onDone={() => {
              setFiling(false);
            }}
          />
        )}
        {message.reactions.length > 0 && (
          <ul aria-label="Reactions" className="mt-1 flex flex-wrap gap-1">
            {message.reactions.map((reaction) => {
              const mineToo = reactedByMe(reaction, meId);
              const label = whoReacted(reaction, meId);
              return (
                <li key={reaction.emoji}>
                  <button
                    type="button"
                    aria-pressed={mineToo}
                    aria-label={label}
                    title={label}
                    disabled={!canReact}
                    onClick={() => void toggle(reaction.emoji, !mineToo)}
                    className="flex h-7 items-center gap-1 rounded-full border border-border bg-bg px-2 text-sm tabular-nums transition-colors hover:border-border-strong disabled:cursor-default aria-pressed:border-accent aria-pressed:bg-accent-soft aria-pressed:text-accent-soft-text"
                  >
                    <span aria-hidden="true">{reaction.emoji}</span>
                    <span aria-hidden="true">{reaction.count}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        {error && <ErrorMessage>{error}</ErrorMessage>}
      </div>
      {picking && (
        <ReactionPicker
          onPick={(emoji) => void toggle(emoji, true)}
          onClose={() => {
            setPicking(false);
          }}
        />
      )}
      {(canEdit || canReply || canReact || canFile) && (
        <div className="absolute -top-3 right-2 hidden items-center gap-1 rounded-lg border border-border bg-surface-raised p-0.5 shadow-sm group-focus-within:flex group-hover:flex">
          {canReact && (
            <button
              type="button"
              aria-expanded={picking}
              onClick={() => {
                setPicking((now) => !now);
              }}
              className={actionClass}
            >
              React
            </button>
          )}
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
          {canFile && (
            <button
              type="button"
              aria-expanded={filing}
              onClick={() => {
                setFiling((now) => !now);
              }}
              className={actionClass}
            >
              Issue
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
  attachments: Attachment[];
  failed: boolean;
}

/** A file picked for the next message: uploading, ready to send, or refused. */
interface Picked {
  key: string;
  name: string;
  attachment?: Attachment;
  problem?: string;
}

export function Composer({
  id,
  label,
  stored,
  send,
  footer,
  candidates = [],
  onTyping,
  upload,
}: {
  id: string;
  label: string;
  /** Uploads a picked or pasted file; without it the composer takes no files. */
  upload?: (file: File) => Promise<Attachment>;
  /** People (and @channel) offered after typing "@". */
  candidates?: Candidate[];
  /** Called as the person types; the caller throttles what it sends. */
  onTyping?: () => void;
  /** client_ids of my messages already stored where this composer sends. */
  stored: Set<string>;
  send: (body: string, clientId: string, attachments: number[]) => Promise<void>;
  footer?: ReactNode;
}) {
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<Pending[]>([]);
  const [picked, setPicked] = useState<Picked[]>([]);
  const area = useRef<HTMLTextAreaElement>(null);
  const filePicker = useRef<HTMLInputElement>(null);
  const uploading = picked.some((item) => !item.attachment && !item.problem);
  const ready = picked.flatMap((item) => (item.attachment ? [item.attachment] : []));
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
      await send(
        item.body,
        item.clientId,
        item.attachments.map((attachment) => attachment.id),
      );
    } catch {
      setPending((now) =>
        now.map((p) => (p.clientId === item.clientId ? { ...p, failed: true } : p)),
      );
    }
  }

  function submit() {
    const body = draft.trim();
    if ((!body && ready.length === 0) || uploading) return;
    // The same id goes with every retry, so the server stores the message once.
    const item = { clientId: crypto.randomUUID(), body, attachments: ready, failed: false };
    setPending((now) => [...now.filter((p) => !stored.has(p.clientId)), item]);
    setDraft("");
    setPicked([]);
    void deliver(item);
  }

  function addFiles(files: File[]) {
    if (!upload) return;
    const room = MAX_FILES - picked.length;
    for (const file of files.slice(0, Math.max(0, room))) {
      const key = crypto.randomUUID();
      const problem = fileProblem(file);
      setPicked((now) => [...now, { key, name: file.name, ...(problem ? { problem } : {}) }]);
      if (problem) continue;
      upload(file).then(
        (attachment) => {
          setPicked((now) => now.map((p) => (p.key === key ? { ...p, attachment } : p)));
        },
        (failure: unknown) => {
          const message =
            failure instanceof ApiError
              ? Object.values(failure.problems.fields).flat().join(" ") ||
                (failure.problems.detail ?? "Could not upload it.")
              : "Could not upload it.";
          setPicked((now) => now.map((p) => (p.key === key ? { ...p, problem: message } : p)));
        },
      );
    }
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
              <span className="min-w-0 flex-1 break-words whitespace-pre-wrap">
                {item.body ||
                  (item.attachments.length === 1
                    ? item.attachments[0]?.name
                    : `${String(item.attachments.length)} files`)}
              </span>
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
      <div
        onDragOver={(event) => {
          if (upload && event.dataTransfer.types.includes("Files")) event.preventDefault();
        }}
        onDrop={(event) => {
          if (!upload || event.dataTransfer.files.length === 0) return;
          event.preventDefault();
          addFiles([...event.dataTransfer.files]);
        }}
        className="relative rounded-2xl border border-border-strong bg-surface p-2 focus-within:border-focus-ring focus-within:ring-4 focus-within:ring-focus-ring/20"
      >
        {picked.length > 0 && (
          <ul aria-label="Files to send" className="flex flex-wrap gap-2 px-2 pt-1 pb-2">
            {picked.map((item) => (
              <li
                key={item.key}
                className={`flex max-w-full items-center gap-2 rounded-lg border px-2 py-1 text-sm ${
                  item.problem ? "border-danger text-danger" : "border-border bg-bg"
                }`}
              >
                <span className="truncate">{item.name}</span>
                <span className="shrink-0 text-xs text-text-subtle">
                  {item.problem ??
                    (item.attachment ? formatSize(item.attachment.size) : "Uploading")}
                </span>
                <button
                  type="button"
                  aria-label={`Remove ${item.name}`}
                  onClick={() => {
                    setPicked((now) => now.filter((p) => p.key !== item.key));
                  }}
                  className="shrink-0 rounded px-1 text-text-subtle hover:bg-bg-subtle hover:text-text"
                >
                  &times;
                </button>
              </li>
            ))}
          </ul>
        )}
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
            if (event.target.value.trim()) onTyping?.();
          }}
          onSelect={(event) => {
            setCaret(event.currentTarget.selectionStart);
          }}
          onKeyDown={onKeyDown}
          onPaste={(event) => {
            const files = [...event.clipboardData.files];
            if (upload && files.length > 0) {
              event.preventDefault();
              addFiles(files);
            }
          }}
          rows={2}
          maxLength={4000}
          placeholder={label}
          className="block w-full resize-none bg-transparent px-2 py-1 outline-none placeholder:text-text-subtle"
        />
        <div className="flex flex-wrap items-center justify-between gap-2 px-2 pt-1">
          <div className="flex flex-wrap items-center gap-3">
            {upload && (
              <>
                <input
                  ref={filePicker}
                  type="file"
                  multiple
                  hidden
                  aria-label="Attach files"
                  onChange={(event) => {
                    addFiles([...(event.target.files ?? [])]);
                    event.target.value = "";
                  }}
                />
                <button
                  type="button"
                  onClick={() => filePicker.current?.click()}
                  disabled={picked.length >= MAX_FILES}
                  className="rounded-lg px-2 py-1 text-sm font-semibold text-text-muted hover:bg-bg-subtle hover:text-text disabled:opacity-50"
                >
                  Attach
                </button>
              </>
            )}
            {footer ?? (
              <span
                className="text-xs text-text-subtle"
                title="**bold**  *italic*  __underline__  ~~strike~~  `code`  ```code block```  > quote  - list  ||spoiler||"
              >
                Enter to send, Shift+Enter for a new line
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={submit}
            disabled={(!draft.trim() && ready.length === 0) || uploading}
            className="btn-lamp rounded-lg bg-accent px-4 py-1.5 text-sm font-semibold text-on-accent hover:bg-accent-hover disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

/** "Bilal is typing", in a line that keeps its height so the messages don't jump. */
export function TypingLine({ people }: { people: Person[] }) {
  return (
    <p aria-live="polite" className="h-5 px-2 text-xs text-text-muted">
      {typingText(people)}
    </p>
  );
}
