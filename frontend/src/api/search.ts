import { useInfiniteQuery } from "@tanstack/react-query";

import { api, readErrors } from "./client";
import type { components } from "./schema";
import { ApiError } from "./workspaces";

export type MessageHit = components["schemas"]["MessageHit"];
export type FileHit = components["schemas"]["FileHit"];
export type IssueHit = components["schemas"]["IssueHit"];
export type SearchKind = "messages" | "files" | "issues";

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

/** One kind's results, a page at a time; nothing is asked until there are words. */
function useSearch<T extends { next?: number | null }>(
  slug: string,
  kind: SearchKind,
  params: SearchParams,
  fetchPage: (beforeId: number | undefined) => Promise<T>,
) {
  return useInfiniteQuery({
    queryKey: ["workspaces", slug, "search", kind, params],
    queryFn: ({ pageParam }) => fetchPage(pageParam),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (last) => last.next ?? undefined,
    enabled: params.q.trim().length > 0,
  });
}

const query = (slug: string, params: SearchParams, beforeId: number | undefined) => ({
  params: { path: { slug }, query: { ...params, before_id: beforeId } },
});

export function useMessageSearch(slug: string, params: SearchParams) {
  return useSearch(slug, "messages", params, async (beforeId) =>
    unwrap(
      await api.GET("/api/v1/workspaces/{slug}/search/messages/", query(slug, params, beforeId)),
    ),
  );
}

export function useFileSearch(slug: string, params: SearchParams) {
  return useSearch(slug, "files", params, async (beforeId) =>
    unwrap(await api.GET("/api/v1/workspaces/{slug}/search/files/", query(slug, params, beforeId))),
  );
}

export function useIssueSearch(slug: string, params: SearchParams) {
  return useSearch(slug, "issues", params, async (beforeId) =>
    unwrap(
      await api.GET("/api/v1/workspaces/{slug}/search/issues/", query(slug, params, beforeId)),
    ),
  );
}
