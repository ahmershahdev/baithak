import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, type User } from "../api/client";
import { ME } from "../auth";
import { Notice, QuietButton } from "../components/ui";

export function Home({ user }: { user: User }) {
  const client = useQueryClient();
  const [resent, setResent] = useState(false);

  const signOut = useMutation({
    mutationFn: async () => api.POST("/api/v1/auth/signout/"),
    onSuccess: () => {
      client.removeQueries({ predicate: (query) => query.queryKey[0] !== ME[0] });
      client.setQueryData(ME, null);
    },
  });

  const resend = useMutation({
    mutationFn: async () => api.POST("/api/v1/auth/verify-email/resend/"),
    onSuccess: () => {
      setResent(true);
    },
  });

  return (
    <main className="mx-auto flex min-h-dvh max-w-2xl flex-col gap-6 px-4 py-12">
      <header className="flex items-center justify-between gap-4">
        <p className="text-lg font-semibold tracking-tight text-accent-text">Baithak</p>
        <QuietButton
          type="button"
          onClick={() => {
            signOut.mutate();
          }}
          disabled={signOut.isPending}
        >
          Sign out
        </QuietButton>
      </header>
      {!user.email_verified &&
        (resent ? (
          <Notice>A new link is on its way to {user.email}.</Notice>
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md bg-warning-soft px-4 py-3 text-warning-soft-text">
            <p>Confirm your email to create or join a workspace.</p>
            <QuietButton
              type="button"
              onClick={() => {
                resend.mutate();
              }}
              disabled={resend.isPending}
            >
              Send the link again
            </QuietButton>
          </div>
        ))}
      <section className="rounded-lg border border-border bg-surface p-6 shadow-sm">
        <h1 className="text-xl font-semibold">Welcome, {user.display_name || user.username}</h1>
        <p className="mt-1 text-text-muted">
          Signed in as @{user.username} ({user.email}). Workspaces are coming next.
        </p>
      </section>
    </main>
  );
}
