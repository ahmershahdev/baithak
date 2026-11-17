import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type User } from "./api/client";

export const ME = ["me"] as const;

export function useMe() {
  return useQuery({
    queryKey: ME,
    queryFn: async (): Promise<User | null> => {
      const { data, response } = await api.GET("/api/v1/auth/me/");
      if (response.status === 204) return null;
      if (data === undefined)
        throw new Error(`Could not load the account (${String(response.status)})`);
      return data;
    },
    staleTime: 60_000,
  });
}

export function useSetMe() {
  const client = useQueryClient();
  return (user: User | null) => {
    client.setQueryData(ME, user);
  };
}
