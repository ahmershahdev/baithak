import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { merge, type Message, type Timeline } from "../chat/timeline";
import { api, readErrors } from "./client";
import type { components } from "./schema";
import { ApiError } from "./workspaces";

export type Channel = components["schemas"]["Channel"];
export type ChannelKind = components["schemas"]["KindEnum"];

export const chatKeys = {
  channels: (slug: string) => ["workspaces", slug, "channels"] as const,
  timeline: (slug: string, id: number) => ["workspaces", slug, "timeline", id] as const,
};

function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined)
    throw new ApiError(result.response.status, readErrors(result.error));
  return result.data;
}

const path = (slug: string, channel_id: number) => ({ path: { slug, channel_id } });

export function useChannels(slug: string) {
  return useQuery({
    queryKey: chatKeys.channels(slug),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/workspaces/{slug}/channels/", { params: { path: { slug } } })),
  });
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

export async function loadOlder(client: QueryClient, slug: string, id: number) {
  const key = chatKeys.timeline(slug, id);
  const current = client.getQueryData<Timeline>(key);
  const first = current?.messages[0];
  if (!current || !first) return;
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
      if (!page.has_more) return;
    }
  } finally {
    catchingUp.delete(flag);
  }
}

/** Put a message this tab got from the API into its timeline. Live events advance lastEvent. */
export function remember(client: QueryClient, slug: string, id: number, message: Message) {
  client.setQueryData<Timeline>(chatKeys.timeline(slug, id), (now) =>
    now ? { ...now, messages: merge(now.messages, [message]) } : now,
  );
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
      const result = await api.POST("/api/v1/workspaces/{slug}/channels/{channel_id}/leave/", {
        params: path(slug, id),
      });
      if (!result.response.ok) throw new ApiError(result.response.status, readErrors(result.error));
    },
    onSuccess: () => client.invalidateQueries({ queryKey: chatKeys.channels(slug) }),
  });
}

export async function sendMessage(slug: string, id: number, body: string, clientId: string) {
  return unwrap(
    await api.POST("/api/v1/workspaces/{slug}/channels/{channel_id}/messages/", {
      params: path(slug, id),
      body: { body, client_id: clientId },
    }),
  );
}

export async function editMessage(slug: string, id: number, seq: number, body: string) {
  return unwrap(
    await api.PATCH("/api/v1/workspaces/{slug}/channels/{channel_id}/messages/{seq}/", {
      params: { path: { slug, channel_id: id, seq } },
      body: { body },
    }),
  );
}

export async function deleteMessage(slug: string, id: number, seq: number) {
  const result = await api.DELETE(
    "/api/v1/workspaces/{slug}/channels/{channel_id}/messages/{seq}/",
    { params: { path: { slug, channel_id: id, seq } } },
  );
  if (!result.response.ok) throw new ApiError(result.response.status, readErrors(result.error));
}
