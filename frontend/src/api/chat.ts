import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import type { Attachment } from "../chat/files";
import { CHANNEL_CANDIDATE, type Candidate } from "../chat/mentions";
import { merge, updateThread, type Message, type Thread, type Timeline } from "../chat/timeline";
import { applyRead } from "../chat/unread";
import { api, readErrors, type User } from "./client";
import type { components } from "./schema";
import { ApiError, useMembers } from "./workspaces";

export type Channel = components["schemas"]["Channel"];
export type ChannelKind = components["schemas"]["ChannelCreateKindEnum"];

export const chatKeys = {
  channels: (slug: string) => ["workspaces", slug, "channels"] as const,
  timeline: (slug: string, id: number) => ["workspaces", slug, "timeline", id] as const,
  threads: (slug: string) => ["workspaces", slug, "thread"] as const,
  channelMembers: (slug: string, id: number) =>
    ["workspaces", slug, "channel-members", id] as const,
  thread: (slug: string, id: number, seq: number) =>
    ["workspaces", slug, "thread", id, seq] as const,
};

function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined)
    throw new ApiError(result.response.status, readErrors(result.error));
  return result.data;
}

function expectOk(result: { error?: unknown; response: Response }) {
  if (!result.response.ok) throw new ApiError(result.response.status, readErrors(result.error));
}

const path = (slug: string, channel_id: number) => ({ path: { slug, channel_id } });

export function useChannels(slug: string) {
  return useQuery({
    queryKey: chatKeys.channels(slug),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/workspaces/{slug}/channels/", { params: { path: { slug } } })),
  });
}

/** Who to offer after "@": the channel's members when it is private, else the workspace's. */
export function useMentionCandidates(
  slug: string,
  channel: Channel,
  me: User,
  canMentionChannel: boolean,
): Candidate[] {
  // Anything but a public channel is read only by its members.
  const isPrivate = channel.kind !== "public";
  const workspace = useMembers(slug);
  const inChannel = useQuery({
    queryKey: chatKeys.channelMembers(slug, channel.id),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/workspaces/{slug}/channels/{channel_id}/members/", {
          params: path(slug, channel.id),
        }),
      ),
    enabled: isPrivate,
  });
  const people = isPrivate
    ? (inChannel.data ?? [])
    : (workspace.data ?? []).filter((member) => member.role !== "guest");
  return [
    ...people
      .filter((person) => person.user_id !== me.id)
      .map(({ username, display_name }) => ({ username, display_name })),
    ...(canMentionChannel ? [CHANNEL_CANDIDATE] : []),
  ];
}

async function latest(slug: string, id: number): Promise<Timeline> {
  const page = unwrap(
    await api.GET("/api/v1/workspaces/{slug}/channels/{channel_id}/messages/", {
      params: path(slug, id),
    }),
  );
  return { messages: page.messages, lastEvent: page.last_event, hasMore: page.has_more };
}

export function useTimeline(slug: string, id: number) {
  return useQuery({
    queryKey: chatKeys.timeline(slug, id),
    queryFn: () => latest(slug, id),
    // Kept fresh by the socket and by catch-up after a reconnect, not by refetching.
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}

async function wholeThread(slug: string, id: number, seq: number): Promise<Thread> {
  const params = { path: { slug, channel_id: id, seq } };
  const url = "/api/v1/workspaces/{slug}/channels/{channel_id}/messages/{seq}/replies/" as const;
  const first = unwrap(await api.GET(url, { params }));
  const thread: Thread = { parent: first.parent, replies: first.replies };
  let more = first.has_more;
  while (more) {
    const after = thread.replies.at(-1)?.thread_seq ?? 0;
    const page = unwrap(await api.GET(url, { params: { ...params, query: { after } } }));
    thread.replies.push(...page.replies);
    more = page.has_more;
  }
  return thread;
}

export function useThread(slug: string, id: number, seq: number) {
  return useQuery({
    queryKey: chatKeys.thread(slug, id, seq),
    queryFn: () => wholeThread(slug, id, seq),
    // The channel's events keep it current (routeMessages), as with timelines.
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

/** Put messages from the channel (live, catch-up or an API answer) into every open thread. */
export function routeMessages(client: QueryClient, slug: string, id: number, messages: Message[]) {
  for (const query of client
    .getQueryCache()
    .findAll({ queryKey: ["workspaces", slug, "thread", id] })) {
    const seq = query.queryKey[4];
    if (typeof seq !== "number") continue;
    client.setQueryData<Thread>(query.queryKey, (now) =>
      now ? updateThread(now, seq, messages) : now,
    );
  }
}

export async function loadOlder(client: QueryClient, slug: string, id: number) {
  const key = chatKeys.timeline(slug, id);
  const current = client.getQueryData<Timeline>(key);
  const first = current?.messages[0];
  if (!current || first?.seq == null) return;
  const page = unwrap(
    await api.GET("/api/v1/workspaces/{slug}/channels/{channel_id}/messages/", {
      params: { ...path(slug, id), query: { before: first.seq } },
    }),
  );
  client.setQueryData<Timeline>(key, (now) =>
    now ? { ...now, messages: merge(now.messages, page.messages), hasMore: page.has_more } : now,
  );
}

const catchingUp = new Set<string>();

/** Fetch every change after the last event this tab applied, page by page. */
export async function catchUp(client: QueryClient, slug: string, id: number) {
  const key = chatKeys.timeline(slug, id);
  const flag = key.join("/");
  if (catchingUp.has(flag)) return;
  catchingUp.add(flag);
  try {
    for (;;) {
      const current = client.getQueryData<Timeline>(key);
      if (!current) return;
      const page = unwrap(
        await api.GET("/api/v1/workspaces/{slug}/channels/{channel_id}/messages/", {
          params: { ...path(slug, id), query: { after_event: current.lastEvent } },
        }),
      );
      client.setQueryData<Timeline>(key, (now) =>
        now
          ? {
              ...now,
              messages: merge(now.messages, page.messages),
              lastEvent: Math.max(now.lastEvent, page.messages.at(-1)?.event ?? now.lastEvent),
            }
          : now,
      );
      routeMessages(client, slug, id, page.messages);
      if (!page.has_more) return;
    }
  } finally {
    catchingUp.delete(flag);
  }
}

/** Put a message this tab got from the API where it is shown. Live events advance lastEvent. */
export function remember(client: QueryClient, slug: string, id: number, message: Message) {
  client.setQueryData<Timeline>(chatKeys.timeline(slug, id), (now) =>
    now ? { ...now, messages: merge(now.messages, [message]) } : now,
  );
  routeMessages(client, slug, id, [message]);
}

export function useCreateChannel(slug: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { name: string; kind: ChannelKind; topic: string }) =>
      unwrap(
        await api.POST("/api/v1/workspaces/{slug}/channels/", { params: { path: { slug } }, body }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: chatKeys.channels(slug) }),
  });
}

export function useStartConversation(slug: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (userIds: number[]) =>
      unwrap(
        await api.POST("/api/v1/workspaces/{slug}/channels/conversations/", {
          params: { path: { slug } },
          body: { user_ids: userIds },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: chatKeys.channels(slug) }),
  });
}

export function useJoinChannel(slug: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await api.POST("/api/v1/workspaces/{slug}/channels/{channel_id}/join/", {
          params: path(slug, id),
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: chatKeys.channels(slug) }),
  });
}

export function useLeaveChannel(slug: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      expectOk(
        await api.POST("/api/v1/workspaces/{slug}/channels/{channel_id}/leave/", {
          params: path(slug, id),
        }),
      );
    },
    onSuccess: () => client.invalidateQueries({ queryKey: chatKeys.channels(slug) }),
  });
}

export function updateChannel(
  client: QueryClient,
  slug: string,
  id: number,
  change: (channel: Channel) => Channel,
) {
  client.setQueryData<Channel[]>(chatKeys.channels(slug), (now) =>
    now?.map((channel) => (channel.id === id ? change(channel) : channel)),
  );
}

/** Report reading up to `seq`. The server's answer is the truth for the count. */
export async function markRead(client: QueryClient, slug: string, id: number, seq: number) {
  updateChannel(client, slug, id, (channel) => applyRead(channel, seq) ?? channel);
  const marker = unwrap(
    await api.POST("/api/v1/workspaces/{slug}/channels/{channel_id}/read/", {
      params: path(slug, id),
      body: { seq },
    }),
  );
  updateChannel(client, slug, id, (channel) =>
    (channel.last_read_seq ?? 0) > marker.last_read_seq
      ? channel
      : { ...channel, last_read_seq: marker.last_read_seq, unread: marker.unread },
  );
}

export async function sendMessage(
  slug: string,
  id: number,
  body: string,
  clientId: string,
  attachments: number[] = [],
) {
  return unwrap(
    await api.POST("/api/v1/workspaces/{slug}/channels/{channel_id}/messages/", {
      params: path(slug, id),
      body: { body, client_id: clientId, attachments },
    }),
  );
}

export async function uploadFile(slug: string, id: number, file: File): Promise<Attachment> {
  const form = new FormData();
  form.append("file", file);
  return unwrap(
    await api.POST("/api/v1/workspaces/{slug}/channels/{channel_id}/files/", {
      params: path(slug, id),
      // The typed body stands for the multipart form; the serializer sends the real one.
      body: { file: "" },
      bodySerializer: () => form,
    }),
  );
}

export async function sendReply(
  slug: string,
  id: number,
  seq: number,
  body: string,
  clientId: string,
  alsoInChannel: boolean,
  attachments: number[] = [],
) {
  return unwrap(
    await api.POST("/api/v1/workspaces/{slug}/channels/{channel_id}/messages/{seq}/replies/", {
      params: { path: { slug, channel_id: id, seq } },
      body: { body, client_id: clientId, also_in_channel: alsoInChannel, attachments },
    }),
  );
}

const MESSAGE = "/api/v1/workspaces/{slug}/channels/{channel_id}/messages/{seq}/" as const;
const REPLY =
  "/api/v1/workspaces/{slug}/channels/{channel_id}/messages/{seq}/replies/{thread_seq}/";

// A message with a channel seq is addressed by it; a reply kept in its thread, inside the thread.
const replyPath = (slug: string, id: number, message: Message) => ({
  slug,
  channel_id: id,
  seq: message.parent_seq ?? 0,
  thread_seq: message.thread_seq ?? 0,
});

export async function editMessage(slug: string, id: number, message: Message, body: string) {
  if (message.seq !== null) {
    const seqPath = { slug, channel_id: id, seq: message.seq };
    return unwrap(await api.PATCH(MESSAGE, { params: { path: seqPath }, body: { body } }));
  }
  const params = { path: replyPath(slug, id, message) };
  return unwrap(await api.PATCH(REPLY, { params, body: { body } }));
}

export async function deleteMessage(slug: string, id: number, message: Message) {
  if (message.seq !== null) {
    const seqPath = { slug, channel_id: id, seq: message.seq };
    expectOk(await api.DELETE(MESSAGE, { params: { path: seqPath } }));
    return;
  }
  expectOk(await api.DELETE(REPLY, { params: { path: replyPath(slug, id, message) } }));
}

/** Add or take back my emoji; the answer is the message with its new reactions. */
export async function react(
  slug: string,
  id: number,
  message: Message,
  emoji: string,
  on: boolean,
): Promise<Message> {
  if (message.seq !== null) {
    const seqPath = { slug, channel_id: id, seq: message.seq };
    return on
      ? unwrap(
          await api.POST(`${MESSAGE}reactions/`, { params: { path: seqPath }, body: { emoji } }),
        )
      : unwrap(
          await api.DELETE(`${MESSAGE}reactions/{emoji}/`, {
            params: { path: { ...seqPath, emoji } },
          }),
        );
  }
  const replyAt = replyPath(slug, id, message);
  return on
    ? unwrap(await api.POST(`${REPLY}reactions/`, { params: { path: replyAt }, body: { emoji } }))
    : unwrap(
        await api.DELETE(`${REPLY}reactions/{emoji}/`, {
          params: { path: { ...replyAt, emoji } },
        }),
      );
}
