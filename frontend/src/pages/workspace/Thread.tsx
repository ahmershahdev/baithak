import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { remember, sendReply, useThread, type Channel } from "../../api/chat";
import type { User } from "../../api/client";
import { startsGroup, storedIds } from "../../chat/timeline";
import { Composer, MessageRow } from "../../components/chat";
import { ErrorMessage } from "../../components/ui";

export function ThreadPanel({
  slug,
  channel,
  me,
  seq,
  onClose,
}: {
  slug: string;
  channel: Channel;
  me: User;
  seq: number;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const thread = useThread(slug, channel.id, seq);
  const [alsoInChannel, setAlsoInChannel] = useState(false);
  const replies = thread.data?.replies ?? [];

  async function send(body: string, clientId: string) {
    const reply = await sendReply(slug, channel.id, seq, body, clientId, alsoInChannel);
    remember(client, slug, channel.id, reply);
  }

  return (
    <aside
      aria-label="Thread"
      className="settle fixed inset-0 z-30 flex flex-col gap-4 bg-bg p-5 lg:static lg:z-auto lg:w-96 lg:shrink-0 lg:border-l lg:border-border lg:bg-transparent lg:p-0 lg:pl-6"
    >
      <header className="flex items-center justify-between gap-3 border-b border-border pb-4">
        <div>
          <h2 className="font-display text-xl font-semibold">Thread</h2>
          <p className="text-sm text-text-muted">#{channel.name}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg px-3 py-1 text-sm font-semibold text-text-muted hover:bg-surface hover:text-text focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
        >
          Close
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto" aria-live="polite" aria-relevant="additions">
        {thread.isPending && (
          <p role="status" className="p-4 text-text-muted">
            Loading thread
          </p>
        )}
        {thread.isError && <ErrorMessage>This thread is not available.</ErrorMessage>}
        {thread.data && (
          <>
            <ol>
              <MessageRow
                message={thread.data.parent}
                grouped={false}
                mine={thread.data.parent.author?.id === me.id}
                slug={slug}
                channel={channel}
              />
            </ol>
            <p className="my-3 flex items-center gap-3 text-xs font-semibold text-text-subtle">
              {replies.length === 1 ? "1 reply" : `${String(replies.length)} replies`}
              <span className="h-px flex-1 bg-border" />
            </p>
            <ol aria-label="Replies">
              {replies.map((reply, index) => (
                <MessageRow
                  key={reply.thread_seq}
                  message={reply}
                  grouped={!startsGroup(replies[index - 1], reply)}
                  mine={reply.author?.id === me.id}
                  slug={slug}
                  channel={channel}
                />
              ))}
            </ol>
          </>
        )}
      </div>

      {thread.data && channel.is_member && !channel.archived && (
        <Composer
          id="thread-composer"
          label="Reply"
          stored={storedIds(replies, me.id)}
          send={send}
          footer={
            <label className="flex items-center gap-2 text-sm text-text-muted">
              <input
                type="checkbox"
                checked={alsoInChannel}
                onChange={(event) => {
                  setAlsoInChannel(event.target.checked);
                }}
                className="size-4 accent-accent"
              />
              Also send to #{channel.name}
            </label>
          }
        />
      )}
    </aside>
  );
}
