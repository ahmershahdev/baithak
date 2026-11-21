import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { catchUp, chatKeys, updateChannel, type Channel } from "../api/chat";
import { LiveSocket, socketUrl, type Status } from "./socket";
import { applyEvent, type Message, type Timeline } from "./timeline";
import { applyRead, countMessage } from "./unread";

/** Keep this workspace's open channels and unread counts live. Returns the connection status. */
export function useLive(slug: string, meId: number): Status {
  const client = useQueryClient();
  const [status, setStatus] = useState<Status>("connecting");

  useEffect(() => {
    const timelines = () =>
      client
        .getQueryCache()
        .findAll({ queryKey: ["workspaces", slug, "timeline"] })
        .map((query) => query.queryKey[3])
        .filter((id): id is number => typeof id === "number");
    const refreshChannels = () =>
      void client.invalidateQueries({ queryKey: chatKeys.channels(slug) });

    const live = new LiveSocket({
      url: socketUrl(slug),
      onStatus: setStatus,
      onReconnected: () => {
        // Whatever happened while the socket was down is in the database; fetch it.
        for (const id of timelines()) void catchUp(client, slug, id);
        refreshChannels();
      },
      onEvent: (event) => {
        if (event.type === "message") {
          const message = event.message as Message;
          updateChannel(client, slug, event.channel, (channel) =>
            countMessage(channel, message, meId),
          );
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
        } else if (event.type === "channel" || event.type === "subscribed") {
          refreshChannels();
        }
      },
    });
    return () => {
      live.stop();
    };
  }, [client, slug, meId]);

  return status;
}
