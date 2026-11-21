import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useEffect, useRef, useState } from "react";

import { catchUp, chatKeys, routeMessages, updateChannel, type Channel } from "../api/chat";
import {
  activeTypers,
  addTyper,
  applyPresence,
  clearTyper,
  placeKey,
  TYPING_SEND_MS,
  type TypingState,
} from "./presence";
import { LiveSocket, socketUrl, type Status } from "./socket";
import { applyEvent, type Message, type Timeline } from "./timeline";
import { applyRead, countMessage } from "./unread";

const presenceKey = (slug: string) => ["workspaces", slug, "presence"] as const;
const typingKey = (slug: string) => ["workspaces", slug, "typing"] as const;

/** Tell the others in a channel (or one of its threads) that I am typing. */
export type SendTyping = (channel: number, thread: number | null) => void;

export const TypingContext = createContext<SendTyping>(() => undefined);

/** Keep this workspace's open channels, unread counts, presence and typing live. */
export function useLive(slug: string, meId: number): { status: Status; sendTyping: SendTyping } {
  const client = useQueryClient();
  const [status, setStatus] = useState<Status>("connecting");
  const socket = useRef<LiveSocket | null>(null);
  const lastTyping = useRef(new Map<string, number>());

  useEffect(() => {
    const timelines = () =>
      client
        .getQueryCache()
        .findAll({ queryKey: ["workspaces", slug, "timeline"] })
        .map((query) => query.queryKey[3])
        .filter((id): id is number => typeof id === "number");
    const refreshChannels = () =>
      void client.invalidateQueries({ queryKey: chatKeys.channels(slug) });
    const typing = (change: (state: TypingState) => TypingState) => {
      client.setQueryData<TypingState>(typingKey(slug), (now) => change(now ?? {}));
    };

    const live = new LiveSocket({
      url: socketUrl(slug),
      onStatus: setStatus,
      onReconnected: () => {
        // Whatever happened while the socket was down is in the database; fetch it.
        for (const id of timelines()) void catchUp(client, slug, id);
        refreshChannels();
        void client.invalidateQueries({ queryKey: chatKeys.threads(slug) });
        void client.invalidateQueries({ queryKey: ["workspaces", slug, "notifications"] });
      },
      onEvent: (event) => {
        if (event.type === "message") {
          const message = event.message as Message;
          if (message.author) {
            const authorId = message.author.id;
            typing((state) =>
              clearTyper(state, placeKey(event.channel, message.parent_seq), authorId),
            );
          }
          updateChannel(client, slug, event.channel, (channel) =>
            countMessage(channel, message, meId),
          );
          routeMessages(client, slug, event.channel, [message]);
          const key = chatKeys.timeline(slug, event.channel);
          const timeline = client.getQueryData<Timeline>(key);
          if (!timeline) return;
          const result = applyEvent(timeline, event.event, message);
          if (result.kind === "applied") client.setQueryData(key, result.timeline);
          if (result.kind === "gap") {
            void catchUp(client, slug, event.channel);
            refreshChannels();
          }
        } else if (event.type === "read") {
          const channels = client.getQueryData<Channel[]>(chatKeys.channels(slug));
          const channel = channels?.find((c) => c.id === event.channel);
          if (!channel) return;
          const next = applyRead(channel, event.last_read_seq);
          if (next) updateChannel(client, slug, event.channel, () => next);
          else refreshChannels();
        } else if (event.type === "presence") {
          client.setQueryData(presenceKey(slug), event.online);
        } else if (event.type === "presence_change") {
          client.setQueryData<number[]>(presenceKey(slug), (now) =>
            applyPresence(now ?? [], event.user, event.online),
          );
        } else if (event.type === "typing") {
          typing((state) =>
            addTyper(state, placeKey(event.channel, event.thread), event.user, Date.now()),
          );
        } else if (event.type === "notifications") {
          void client.invalidateQueries({ queryKey: ["workspaces", slug, "notifications"] });
        } else if (event.type === "channel" || event.type === "subscribed") {
          refreshChannels();
        }
      },
    });
    socket.current = live;
    return () => {
      socket.current = null;
      live.stop();
    };
  }, [client, slug, meId]);

  const sendTyping = useCallback<SendTyping>((channel, thread) => {
    const key = placeKey(channel, thread);
    const now = Date.now();
    if (now - (lastTyping.current.get(key) ?? 0) < TYPING_SEND_MS) return;
    if (socket.current?.send({ type: "typing", channel, thread })) {
      lastTyping.current.set(key, now);
    }
  }, []);

  return { status, sendTyping };
}

/** Ids of the people online in this workspace, as the socket last said. */
export function useOnline(slug: string): Set<number> {
  // Only the socket writes this; the query is how components read and follow it.
  const online = useQuery<number[]>({
    queryKey: presenceKey(slug),
    queryFn: () => [],
    initialData: [],
    staleTime: Infinity,
    enabled: false,
  });
  return new Set(online.data);
}

/** Who else is typing in one place right now; notices fade on their own. */
export function useTypers(slug: string, channel: number, thread: number | null) {
  const state = useQuery<TypingState>({
    queryKey: typingKey(slug),
    queryFn: () => ({}),
    initialData: {},
    staleTime: Infinity,
    enabled: false,
  });
  const key = placeKey(channel, thread);
  const [now, setNow] = useState(() => Date.now());
  const pending = (state.data[key] ?? []).some((typer) => typer.until > now);

  useEffect(() => {
    // Ticks only while someone shows as typing here, so their notice can fade.
    if (!pending) return;
    const timer = setInterval(() => {
      setNow(Date.now());
    }, 1_000);
    return () => {
      clearInterval(timer);
    };
  }, [pending]);

  return activeTypers(state.data, key, now);
}
