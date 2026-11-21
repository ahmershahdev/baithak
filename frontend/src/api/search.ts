import { useInfiniteQuery } from "@tanstack/react-query";

import { api, readErrors } from "./client";
import type { components } from "./schema";
import { ApiError } from "./workspaces";

export type MessageHit = components["schemas"]["MessageHit"];
export type FileHit = components["schemas"]["FileHit"];
export type SearchKind = "messages" | "files";

export interface SearchParams {
  q: string;
  channel?: number;
  author?: string;
  after?: string;
  before?: string;
}

function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined)
    throw new ApiError(result.response.status, readErrors(result.error));
  return result.data;
}

export function useMessageSearch(slug: string, params: SearchParams) {
  return useInfiniteQuery({
    queryKey: ["workspaces", slug, "search", "messages", params],
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/api/v1/workspaces/{slug}/search/messages/", {
          params: { path: { slug }, query: { ...params, before_id: pageParam } },
        }),
      ),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (last) => last.next ?? undefined,
    enabled: params.q.trim().length > 0,
  });
}

export function useFileSearch(slug: string, params: SearchParams) {
  return useInfiniteQuery({
    queryKey: ["workspaces", slug, "search", "files", params],
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/api/v1/workspaces/{slug}/search/files/", {
          params: { path: { slug }, query: { ...params, before_id: pageParam } },
        }),
      ),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (last) => last.next ?? undefined,
    enabled: params.q.trim().length > 0,
  });
}
