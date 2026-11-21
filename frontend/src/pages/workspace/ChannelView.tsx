import { useQueryClient } from "@tanstack/react-query";
import { Fragment, use, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useOutletContext, useParams, useSearchParams } from "react-router";

import {
  loadOlder,
  markRead,
  remember,
  sendMessage,
  useChannels,
  useJoinChannel,
  useMentionCandidates,
  useTimeline,
  type Channel,
} from "../../api/chat";
import type { User } from "../../api/client";
import { startsGroup, storedIds, type Message } from "../../chat/timeline";
import { channelTitle, isConversation } from "../../chat/conversations";
import { TypingContext, useOnline, useTypers } from "../../chat/live";
import { firstUnread } from "../../chat/unread";
import { Composer, MessageRow, TypingLine } from "../../components/chat";
import { ErrorMessage } from "../../components/ui";
import { ChannelIcon, PresenceDot } from "../../components/workspace";
import type { WorkspaceContext } from "./Shell";
import { ThreadPanel } from "./Thread";

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
  return (
    <Conversation
      key={channel.id}
      slug={workspace.slug}
      channel={channel}
      me={me}
      canMentionChannel={workspace.role !== "guest"}
    />
  );
}

/** Report the newest message as read while the reader is at the bottom of a visible tab. */
function useReadMarker(
  slug: string,
  channel: Channel,
  newest: number | undefined,
  atBottom: boolean,
) {
  const client = useQueryClient();
  const reported = useRef(0);
  const lastRead = channel.last_read_seq;

  useEffect(() => {
    if (lastRead === null || newest === undefined) return;
    const report = () => {
      if (document.hidden || !atBottom || newest <= lastRead || newest <= reported.current) return;
      reported.current = newest;
      markRead(client, slug, channel.id, newest).catch(() => {
        reported.current = 0;
      });
    };
    report();
    document.addEventListener("visibilitychange", report);
    return () => {
      document.removeEventListener("visibilitychange", report);
    };
  }, [client, slug, channel.id, lastRead, newest, atBottom]);
}

function Messages({
  messages,
  channel,
  me,
  slug,
  onOpenThread,
}: {
  messages: Message[];
  channel: Channel;
  me: User;
  slug: string;
  onOpenThread: (seq: number) => void;
}) {
  // Fixed when the channel is opened, so the line stays put while the marker moves past it.
  const [newFrom] = useState(() => firstUnread(messages, channel.last_read_seq, me.id));
  return (
    <ol>
      {messages.map((message, index) => (
        <Fragment key={message.seq}>
          {message.seq === newFrom && (
            <li
              role="separator"
              aria-label="New messages"
              className="my-2 flex items-center gap-3 text-xs font-semibold text-accent-text"
            >
              <span className="h-px flex-1 bg-accent" />
              New
            </li>
          )}
          <MessageRow
            message={message}
            grouped={message.seq !== newFrom && !startsGroup(messages[index - 1], message)}
            meId={me.id}
            slug={slug}
            channel={channel}
            onOpenThread={onOpenThread}
          />
        </Fragment>
      ))}
    </ol>
  );
}

function Conversation({
  slug,
  channel,
  me,
  canMentionChannel,
}: {
  slug: string;
  channel: Channel;
  me: User;
  canMentionChannel: boolean;
}) {
  const client = useQueryClient();
  const timeline = useTimeline(slug, channel.id);
  const joinChannel = useJoinChannel(slug);
  const [params, setParams] = useSearchParams();
  const candidates = useMentionCandidates(slug, channel, me, canMentionChannel);
  const scroller = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const [atBottom, setAtBottom] = useState(true);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const messages = timeline.data?.messages ?? [];
  const newest = messages.at(-1)?.seq ?? undefined;
  const threadParam = Number(params.get("thread"));
  const openThread = Number.isInteger(threadParam) && threadParam > 0 ? threadParam : null;
  useReadMarker(slug, channel, newest, atBottom);

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
      setAtBottom(nearBottom.current);
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

  function showThread(seq: number | null) {
    setParams(seq === null ? {} : { thread: String(seq) });
  }

  const title = channelTitle(channel, me.id);
  const conversation = isConversation(channel);
  const sendTyping = use(TypingContext);
  const typers = useTypers(slug, channel.id, null);
  const online = useOnline(slug);
  const other =
    channel.kind === "direct" ? channel.people.find((person) => person.id !== me.id) : undefined;

  async function send(body: string, clientId: string) {
    remember(client, slug, channel.id, await sendMessage(slug, channel.id, body, clientId));
  }

  return (
    <div className="flex h-[calc(100dvh-4rem)] gap-6">
      <div className="flex min-w-0 flex-1 flex-col gap-4">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
          <div className="min-w-0">
            <h1 className="wonky flex items-center gap-2 font-display text-2xl font-semibold">
              {other ? (
                <PresenceDot online={online.has(other.id)} />
              ) : (
                <ChannelIcon kind={channel.kind} />
              )}
              <span className="truncate">{title}</span>
            </h1>
            {channel.kind === "group" && (
              <p className="text-sm text-text-muted">
                Group of {channel.people.length}. Only the people in it can read it.
              </p>
            )}
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
              {conversation
                ? `This is the start of your conversation with ${title}. Say salaam.`
                : `This is the very start of #${channel.name}. Say salaam.`}
            </p>
          )}
          {timeline.data && (
            <Messages
              messages={messages}
              channel={channel}
              me={me}
              slug={slug}
              onOpenThread={showThread}
            />
          )}
        </div>

        <TypingLine people={typers} />
        {channel.is_member && !channel.archived ? (
          <Composer
            id="composer"
            label={conversation ? `Message ${title}` : `Message #${channel.name}`}
            stored={storedIds(timeline.data?.messages, me.id)}
            send={send}
            candidates={candidates}
            onTyping={() => {
              sendTyping(channel.id, null);
            }}
          />
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

      {openThread !== null && (
        <ThreadPanel
          key={openThread}
          slug={slug}
          channel={channel}
          me={me}
          seq={openThread}
          candidates={candidates}
          onClose={() => {
            showThread(null);
          }}
        />
      )}
    </div>
  );
}
