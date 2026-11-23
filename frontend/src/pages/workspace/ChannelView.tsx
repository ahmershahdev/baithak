import { useQueryClient } from "@tanstack/react-query";
import { Fragment, use, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useOutletContext, useParams, useSearchParams } from "react-router";

import {
  loadOlder,
  markRead,
  remember,
  sendMessage,
  uploadFile,
  useChannelMembers,
  useChannels,
  useJoinChannel,
  useMentionCandidates,
  useTimeline,
  type Channel,
} from "../../api/chat";
import type { User } from "../../api/client";
import { channelTitle, isConversation } from "../../chat/conversations";
import { dayLabel, startsDay } from "../../chat/days";
import { TypingContext, useOnline, useTypers } from "../../chat/live";
import { startsGroup, storedIds, type Message } from "../../chat/timeline";
import { firstUnread } from "../../chat/unread";
import { Composer, MessageRow, TypingLine } from "../../components/chat";
import { Icon } from "../../components/icons";
import { ErrorMessage } from "../../components/ui";
import { Avatar, ChannelIcon } from "../../components/workspace";
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
      <p role="status" className="p-8 text-text-muted">
        Loading
      </p>
    );
  }
  if (!channel) {
    return (
      <div className="flex flex-col gap-4 p-8">
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
      canSeeIssues={workspace.role !== "guest"}
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

function DayDivider({ iso }: { iso: string }) {
  return (
    <li role="separator" aria-label={dayLabel(iso)} className="my-4 flex items-center gap-3">
      <span className="h-px flex-1 bg-border" />
      <span className="rounded-full border border-border bg-surface px-3 py-0.5 text-xs font-semibold text-text-muted shadow-sm">
        {dayLabel(iso)}
      </span>
      <span className="h-px flex-1 bg-border" />
    </li>
  );
}

function Messages({
  messages,
  channel,
  me,
  slug,
  onOpenThread,
  canSeeIssues,
}: {
  messages: Message[];
  channel: Channel;
  me: User;
  slug: string;
  onOpenThread: (seq: number) => void;
  canSeeIssues: boolean;
}) {
  // Fixed when the channel is opened, so the line stays put while the marker moves past it.
  const [newFrom] = useState(() => firstUnread(messages, channel.last_read_seq, me.id));
  return (
    <ol className="pb-2">
      {messages.map((message, index) => {
        const previous = messages[index - 1];
        const newDay = startsDay(previous, message.created_at);
        return (
          <Fragment key={message.seq}>
            {newDay && <DayDivider iso={message.created_at} />}
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
              grouped={message.seq !== newFrom && !newDay && !startsGroup(previous, message)}
              meId={me.id}
              slug={slug}
              channel={channel}
              onOpenThread={onOpenThread}
              canSeeIssues={canSeeIssues}
            />
          </Fragment>
        );
      })}
    </ol>
  );
}

function Welcome({ channel, title }: { channel: Channel; title: string }) {
  const conversation = isConversation(channel);
  return (
    <div className="settle mx-auto flex max-w-md flex-col items-center gap-3 px-6 py-16 text-center">
      <span className="grid size-14 place-items-center rounded-t-full rounded-b-2xl bg-accent-soft text-2xl text-accent-soft-text">
        {conversation ? <Icon name="people" className="size-6" /> : "#"}
      </span>
      <h2 className="wonky font-display text-2xl font-semibold">
        {conversation ? title : `Welcome to #${channel.name}`}
      </h2>
      <p className="text-text-muted">
        {conversation
          ? `This is the start of your conversation with ${title}. Say salaam.`
          : `This is the very start of #${channel.name}. Say salaam.`}
      </p>
      {channel.topic && <p className="text-sm text-text-subtle">{channel.topic}</p>}
    </div>
  );
}

function People({ slug, channel }: { slug: string; channel: Channel }) {
  const conversation = isConversation(channel);
  const members = useChannelMembers(slug, channel.id, !conversation);
  const people = conversation
    ? channel.people.map((person) => ({
        key: person.username,
        name: person.display_name || person.username,
      }))
    : (members.data ?? []).map((member) => ({
        key: member.username,
        name: member.display_name || member.username,
      }));
  if (people.length === 0 || channel.kind === "direct") return null;
  const label = people.length === 1 ? "1 member" : `${String(people.length)} members`;
  return (
    <span
      title={people
        .filter((_, index) => conversation || index < 20)
        .map((person) => person.name)
        .join(", ")}
      className="flex items-center gap-2 rounded-xl border border-border px-2 py-1 text-sm text-text-muted"
    >
      <span className="flex -space-x-2" aria-hidden="true">
        {people.slice(0, 3).map((person) => (
          <span key={person.key} className="rounded-t-full rounded-b-lg ring-2 ring-bg">
            <Avatar name={person.name} colorKey={person.key} size="sm" />
          </span>
        ))}
      </span>
      <span className="tabular-nums">{label}</span>
    </span>
  );
}

function Header({
  slug,
  channel,
  me,
  title,
}: {
  slug: string;
  channel: Channel;
  me: User;
  title: string;
}) {
  const online = useOnline(slug);
  const other =
    channel.kind === "direct" ? channel.people.find((person) => person.id !== me.id) : undefined;
  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-bg/90 px-4 py-3 backdrop-blur sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-t-full rounded-b-xl bg-surface-sunken text-text-muted">
          {other ? (
            <Avatar
              name={other.display_name || other.username}
              colorKey={other.username}
              online={online.has(other.id)}
            />
          ) : (
            <ChannelIcon kind={channel.kind} />
          )}
        </span>
        <div className="min-w-0">
          <h1 className="wonky flex items-center gap-2 font-display text-xl font-semibold">
            <span className="truncate">{title}</span>
            {channel.archived && (
              <span className="rounded-full bg-surface-sunken px-2.5 py-0.5 font-sans text-xs font-semibold text-text-muted">
                Archived
              </span>
            )}
          </h1>
          {channel.kind === "group" ? (
            <p className="truncate text-sm text-text-muted">
              Group of {channel.people.length}. Only the people in it can read it.
            </p>
          ) : channel.topic ? (
            <p className="truncate text-sm text-text-muted" title={channel.topic}>
              {channel.topic}
            </p>
          ) : null}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <People slug={slug} channel={channel} />
        <Link
          to={`/w/${slug}/search?channel=${String(channel.id)}`}
          aria-label={`Search in ${isConversation(channel) ? title : `#${channel.name}`}`}
          title="Search in this conversation"
          className="grid size-9 place-items-center rounded-xl border border-border text-text-muted transition-colors hover:border-border-strong hover:text-text focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
        >
          <Icon name="search" />
        </Link>
      </div>
    </header>
  );
}

function Conversation({
  slug,
  channel,
  me,
  canMentionChannel,
  canSeeIssues,
}: {
  slug: string;
  channel: Channel;
  me: User;
  canMentionChannel: boolean;
  canSeeIssues: boolean;
}) {
  const client = useQueryClient();
  const timeline = useTimeline(slug, channel.id);
  const joinChannel = useJoinChannel(slug);
  const [params, setParams] = useSearchParams();
  const candidates = useMentionCandidates(slug, channel, me, canMentionChannel);
  const scroller = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const [atBottom, setAtBottom] = useState(true);
  const [missed, setMissed] = useState(0);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const messages = timeline.data?.messages ?? [];
  const newest = messages.at(-1)?.seq ?? undefined;
  const threadParam = Number(params.get("thread"));
  const openThread = Number.isInteger(threadParam) && threadParam > 0 ? threadParam : null;
  useReadMarker(slug, channel, newest, atBottom);

  // Follow new messages only when the reader is already at the bottom, never yank them away
  // from something older they are reading.
  const seen = useRef(newest);
  useLayoutEffect(() => {
    const box = scroller.current;
    if (box && nearBottom.current) box.scrollTop = box.scrollHeight;
    else if (newest !== undefined && seen.current !== undefined && newest > seen.current)
      setMissed((count) => count + newest - (seen.current ?? newest));
    seen.current = newest;
  }, [newest]);

  useEffect(() => {
    const box = scroller.current;
    if (!box) return;
    const track = () => {
      nearBottom.current = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
      setAtBottom(nearBottom.current);
      if (nearBottom.current) setMissed(0);
    };
    box.addEventListener("scroll", track);
    return () => {
      box.removeEventListener("scroll", track);
    };
  }, []);

  function toLatest() {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }

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

  async function send(body: string, clientId: string, attachments: number[]) {
    remember(
      client,
      slug,
      channel.id,
      await sendMessage(slug, channel.id, body, clientId, attachments),
    );
  }

  return (
    <div className="flex h-dvh">
      <section aria-label={title} className="flex min-w-0 flex-1 flex-col">
        <Header slug={slug} channel={channel} me={me} title={title} />

        <div className="relative min-h-0 flex-1">
          <div
            ref={scroller}
            className="h-full overflow-y-auto px-2 sm:px-4"
            aria-live="polite"
            aria-relevant="additions"
          >
            {timeline.data?.hasMore && (
              <div className="flex justify-center py-3">
                <button
                  type="button"
                  onClick={() => void older()}
                  disabled={loadingOlder}
                  className="rounded-full border border-border bg-surface px-4 py-1 text-sm font-semibold text-text-muted shadow-sm transition-colors hover:border-border-strong hover:text-text disabled:opacity-60"
                >
                  {loadingOlder ? "Loading" : "Show earlier messages"}
                </button>
              </div>
            )}
            {timeline.isPending && (
              <p role="status" className="p-6 text-text-muted">
                Loading messages
              </p>
            )}
            {timeline.data && messages.length === 0 && <Welcome channel={channel} title={title} />}
            {timeline.data && (
              <Messages
                messages={messages}
                channel={channel}
                me={me}
                slug={slug}
                onOpenThread={showThread}
                canSeeIssues={canSeeIssues}
              />
            )}
          </div>
          {!atBottom && (
            <button
              type="button"
              onClick={toLatest}
              className="settle absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full bg-text px-4 py-1.5 text-sm font-semibold text-bg shadow-lg transition-transform hover:-translate-y-0.5 focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
            >
              <Icon name="down" />
              {missed > 0
                ? `${String(missed)} new ${missed === 1 ? "message" : "messages"}`
                : "Jump to latest"}
            </button>
          )}
        </div>

        <div className="px-3 pb-3 sm:px-6 sm:pb-4">
          <TypingLine people={typers} />
          {channel.is_member && !channel.archived ? (
            <Composer
              id="composer"
              label={conversation ? `Message ${title}` : `Message #${channel.name}`}
              stored={storedIds(timeline.data?.messages, me.id)}
              send={send}
              upload={(file) => uploadFile(slug, channel.id, file)}
              candidates={candidates}
              onTyping={() => {
                sendTyping(channel.id, null);
              }}
            />
          ) : channel.archived ? (
            <p className="rounded-2xl bg-surface-sunken px-4 py-3 text-sm text-text-muted">
              This channel is archived. You can read it, but not post.
            </p>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-surface px-4 py-3 shadow-sm">
              <p className="text-text-muted">You are reading #{channel.name}. Join to post.</p>
              <button
                type="button"
                disabled={joinChannel.isPending}
                onClick={() => {
                  joinChannel.mutate(channel.id);
                }}
                className="btn-lamp rounded-xl bg-accent px-4 py-1.5 font-semibold text-on-accent hover:bg-accent-hover disabled:opacity-60"
              >
                Join #{channel.name}
              </button>
            </div>
          )}
        </div>
      </section>

      {openThread !== null && (
        <ThreadPanel
          key={openThread}
          slug={slug}
          channel={channel}
          me={me}
          seq={openThread}
          candidates={candidates}
          canSeeIssues={canSeeIssues}
          onClose={() => {
            showThread(null);
          }}
        />
      )}
    </div>
  );
}
