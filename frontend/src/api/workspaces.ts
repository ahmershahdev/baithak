import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, readErrors, type ApiErrors } from "./client";
import type { components } from "./schema";

export type Workspace = components["schemas"]["Workspace"];
export type Member = components["schemas"]["Member"];
export type Invitation = components["schemas"]["Invitation"];
export type AuditEvent = components["schemas"]["AuditEvent"];
export type InvitationPreview = components["schemas"]["InvitationPreview"];

export const keys = {
  all: ["workspaces"] as const,
  one: (slug: string) => ["workspaces", slug] as const,
  members: (slug: string) => ["workspaces", slug, "members"] as const,
  invitations: (slug: string) => ["workspaces", slug, "invitations"] as const,
  audit: (slug: string) => ["workspaces", slug, "audit"] as const,
};

/** A failed call, with the API's messages for the screen. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly problems: ApiErrors,
  ) {
    super(problems.detail ?? `Request failed (${String(status)})`);
  }
}

function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined)
    throw new ApiError(result.response.status, readErrors(result.error));
  return result.data;
}

function ok(result: { error?: unknown; response: Response }): void {
  if (!result.response.ok) throw new ApiError(result.response.status, readErrors(result.error));
}

export function useWorkspaces() {
  return useQuery({
    queryKey: keys.all,
    queryFn: async () => unwrap(await api.GET("/api/v1/workspaces/")),
  });
}

export function useWorkspace(slug: string) {
  return useQuery({
    queryKey: keys.one(slug),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/workspaces/{slug}/", { params: { path: { slug } } })),
    retry: false,
  });
}

export function useMembers(slug: string) {
  return useQuery({
    queryKey: keys.members(slug),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/workspaces/{slug}/members/", { params: { path: { slug } } })),
  });
}

export function useInvitations(slug: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.invitations(slug),
    enabled,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/workspaces/{slug}/invitations/", { params: { path: { slug } } }),
      ),
  });
}

export function useAuditLog(slug: string, enabled: boolean) {
  return useInfiniteQuery({
    queryKey: keys.audit(slug),
    enabled,
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/api/v1/workspaces/{slug}/audit/", {
          params: { path: { slug }, query: pageParam ? { cursor: pageParam } : {} },
        }),
      ),
    // `next` is a full URL; only its cursor is needed for the following page.
    getNextPageParam: (page) =>
      page.next ? (new URL(page.next).searchParams.get("cursor") ?? undefined) : undefined,
  });
}

export function useCreateWorkspace() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) =>
      unwrap(await api.POST("/api/v1/workspaces/", { body: { name } })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useRenameWorkspace(slug: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) =>
      unwrap(
        await api.PATCH("/api/v1/workspaces/{slug}/", {
          params: { path: { slug } },
          body: { name },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useChangeRole(slug: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ userId, role }: { userId: number; role: Member["role"] }) =>
      unwrap(
        await api.PATCH("/api/v1/workspaces/{slug}/members/{user_id}/", {
          params: { path: { slug, user_id: userId } },
          body: { role },
        }),
      ),
    onSettled: () => client.invalidateQueries({ queryKey: keys.one(slug) }),
  });
}

export function useRemoveMember(slug: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (userId: number) => {
      ok(
        await api.DELETE("/api/v1/workspaces/{slug}/members/{user_id}/", {
          params: { path: { slug, user_id: userId } },
        }),
      );
    },
    onSettled: () => client.invalidateQueries({ queryKey: keys.one(slug) }),
  });
}

export function useInvite(slug: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { email: string; role: Exclude<Member["role"], "owner"> }) =>
      unwrap(
        await api.POST("/api/v1/workspaces/{slug}/invitations/", {
          params: { path: { slug } },
          body,
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.invitations(slug) }),
  });
}

export function useRevokeInvitation(slug: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      ok(
        await api.DELETE("/api/v1/workspaces/{slug}/invitations/{invitation_id}/", {
          params: { path: { slug, invitation_id: id } },
        }),
      );
    },
    onSettled: () => client.invalidateQueries({ queryKey: keys.invitations(slug) }),
  });
}
