import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, readErrors } from "./client";
import type { components } from "./schema";
import { ApiError } from "./workspaces";

export type Project = components["schemas"]["Project"];
export type Issue = components["schemas"]["Issue"];
export type IssueLabel = components["schemas"]["Label"];
export type IssueChanges = components["schemas"]["PatchedIssueWriteRequest"];

export interface IssueFilters {
  open?: "true" | "false";
  assignee?: string;
  label?: number;
  priority?: string;
}

const keys = {
  projects: (slug: string) => ["workspaces", slug, "projects"] as const,
  project: (slug: string, key: string) => ["workspaces", slug, "projects", key] as const,
  issues: (slug: string, key: string) => ["workspaces", slug, "projects", key, "issues"] as const,
  labels: (slug: string, key: string) => ["workspaces", slug, "projects", key, "labels"] as const,
};

function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined)
    throw new ApiError(result.response.status, readErrors(result.error));
  return result.data;
}

const at = (slug: string, key: string) => ({ path: { slug, key } });

export function useProjects(slug: string) {
  return useQuery({
    queryKey: keys.projects(slug),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/workspaces/{slug}/projects/", { params: { path: { slug } } })),
  });
}

export function useCreateProject(slug: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { key: string; name: string; description: string }) =>
      unwrap(
        await api.POST("/api/v1/workspaces/{slug}/projects/", { params: { path: { slug } }, body }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.projects(slug) }),
  });
}

export function useProject(slug: string, key: string) {
  return useQuery({
    queryKey: keys.project(slug, key),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/workspaces/{slug}/projects/{key}/", { params: at(slug, key) })),
    retry: false,
  });
}

export function useLabels(slug: string, key: string) {
  return useQuery({
    queryKey: keys.labels(slug, key),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/workspaces/{slug}/projects/{key}/labels/", {
          params: at(slug, key),
        }),
      ),
  });
}

export function useCreateLabel(slug: string, key: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { name: string; color: IssueLabel["color"] }) =>
      unwrap(
        await api.POST("/api/v1/workspaces/{slug}/projects/{key}/labels/", {
          params: at(slug, key),
          body,
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.labels(slug, key) }),
  });
}

export function useIssues(slug: string, key: string, filters: IssueFilters) {
  return useInfiniteQuery({
    queryKey: [...keys.issues(slug, key), filters],
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/api/v1/workspaces/{slug}/projects/{key}/issues/", {
          params: {
            path: { slug, key },
            query: {
              assignee: filters.assignee,
              label: filters.label,
              priority: filters.priority,
              open: filters.open === undefined ? undefined : filters.open === "true",
              before: pageParam,
            },
          },
        }),
      ),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (last) => last.next ?? undefined,
  });
}

export function useIssue(slug: string, key: string, number: number) {
  return useQuery({
    queryKey: [...keys.issues(slug, key), "one", number],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/workspaces/{slug}/projects/{key}/issues/{number}/", {
          params: { path: { slug, key, number } },
        }),
      ),
    retry: false,
  });
}

export function useCreateIssue(slug: string, key: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { title: string }) =>
      unwrap(
        await api.POST("/api/v1/workspaces/{slug}/projects/{key}/issues/", {
          params: at(slug, key),
          body,
        }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.issues(slug, key) });
      void client.invalidateQueries({ queryKey: keys.projects(slug) });
    },
  });
}

export function useUpdateIssue(slug: string, key: string, number: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: IssueChanges) =>
      unwrap(
        await api.PATCH("/api/v1/workspaces/{slug}/projects/{key}/issues/{number}/", {
          params: { path: { slug, key, number } },
          body,
        }),
      ),
    onSuccess: (issue) => {
      client.setQueryData([...keys.issues(slug, key), "one", number], issue);
      void client.invalidateQueries({ queryKey: keys.issues(slug, key) });
      void client.invalidateQueries({ queryKey: keys.projects(slug) });
    },
  });
}
