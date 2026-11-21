import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, readErrors } from "./client";
import type { components } from "./schema";
import { ApiError } from "./workspaces";

export type Notification = components["schemas"]["Notification"];

export const notificationKeys = {
  all: (slug: string) => ["workspaces", slug, "notifications"] as const,
};

function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined)
    throw new ApiError(result.response.status, readErrors(result.error));
  return result.data;
}

/** Kept fresh by the socket's "notifications" event, which refetches it. */
export function useNotifications(slug: string) {
  return useInfiniteQuery({
    queryKey: notificationKeys.all(slug),
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/api/v1/workspaces/{slug}/notifications/", {
          params: { path: { slug }, query: { before_id: pageParam } },
        }),
      ),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (last) => last.next ?? undefined,
  });
}

export function useMarkNotificationsRead(slug: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (which: { ids: number[] } | { all: true }) =>
      unwrap(
        await api.POST("/api/v1/workspaces/{slug}/notifications/read/", {
          params: { path: { slug } },
          body: "ids" in which ? { ids: which.ids, all: false } : { all: true },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: notificationKeys.all(slug) }),
  });
}
