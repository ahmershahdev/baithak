import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, readErrors } from "./client";
import type { components } from "./schema";
import { ApiError } from "./workspaces";

export type Webhook = components["schemas"]["Webhook"];
export type NewWebhook = components["schemas"]["NewWebhook"];

const webhooksKey = (slug: string) => ["workspaces", slug, "webhooks"] as const;

function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined)
    throw new ApiError(result.response.status, readErrors(result.error));
  return result.data;
}

export function useWebhooks(slug: string) {
  return useQuery({
    queryKey: webhooksKey(slug),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/workspaces/{slug}/integrations/webhooks/", {
          params: { path: { slug } },
        }),
      ),
  });
}

export function useConnectRepo(slug: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { channel_id: number; repo: string }) =>
      unwrap(
        await api.POST("/api/v1/workspaces/{slug}/integrations/webhooks/", {
          params: { path: { slug } },
          body: { kind: "github", ...body },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: webhooksKey(slug) }),
  });
}

export function useRemoveWebhook(slug: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const result = await api.DELETE(
        "/api/v1/workspaces/{slug}/integrations/webhooks/{webhook_id}/",
        {
          params: { path: { slug, webhook_id: id } },
        },
      );
      if (!result.response.ok) throw new ApiError(result.response.status, readErrors(result.error));
    },
    onSuccess: () => client.invalidateQueries({ queryKey: webhooksKey(slug) }),
  });
}
