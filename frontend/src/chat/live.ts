import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { catchUp, chatKeys } from "../api/chat";
import { LiveSocket, socketUrl, type Status } from "./socket";
import { applyEvent, type Message, type Timeline } from "./timeline";

/** Keep this workspace's open channels live. Returns the connection status for the screen. */
export function useLive(slug: string): Status {
  const client = useQueryClient();
  const [status, setStatus] = useState<Status>("connecting");

  useEffect(() => {
    const timelines = () =>
      client
        .getQueryCache()
        .findAll({ queryKey: ["workspaces", slug, "timeline"] })
        .map((query) => query.queryKey[3])
        .filter((id): id is number => typeof id === "number");

    const live = new LiveSocket({
      url: socketUrl(slug),
      onStatus: setStatus,
      onReconnected: () => {
        // Whatever happened while the socket was down is in the database; fetch it.
        for (const id of timelines()) void catchUp(client, slug, id);
        void client.invalidateQueries({ queryKey: chatKeys.channels(slug) });
      },
      onEvent: (event) => {
        if (event.type === "message") {
          const key = chatKeys.timeline(slug, event.channel);
          const timeline = client.getQueryData<Timeline>(key);
          if (!timeline) return;
          const result = applyEvent(timeline, event.event, event.message as Message);
          if (result.kind === "applied") client.setQueryData(key, result.timeline);
          if (result.kind === "gap") void catchUp(client, slug, event.channel);
        } else if (event.type === "channel" || event.type === "subscribed") {
          void client.invalidateQueries({ queryKey: chatKeys.channels(slug) });
        }
      },
    });
    return () => {
      live.stop();
    };
  }, [client, slug]);

  return status;
}
