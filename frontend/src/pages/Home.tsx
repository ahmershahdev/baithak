import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";
import { Link, useNavigate } from "react-router";

import { api, type ApiErrors, type User } from "../api/client";
import { ApiError, useCreateWorkspace } from "../api/workspaces";
import { ME } from "../auth";
import { Scene, Wordmark } from "../components/brand";
import { Button, ErrorMessage, Field, Notice, QuietButton } from "../components/ui";
import { textField } from "../forms";

function ConfirmEmailBanner({ user }: { user: User }) {
  const [resent, setResent] = useState(false);
  const resend = useMutation({
    mutationFn: async () => api.POST("/api/v1/auth/verify-email/resend/"),
    onSuccess: () => {
      setResent(true);
    },
  });
  if (resent) return <Notice>A new link is on its way to {user.email}.</Notice>;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-warning-soft px-4 py-3 text-warning-soft-text">
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
  );
}

function CreateForm({ user }: { user: User }) {
  const navigate = useNavigate();
  const create = useCreateWorkspace();
  const [errors, setErrors] = useState<ApiErrors>({ fields: {} });

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrors({ fields: {} });
    create.mutate(textField(new FormData(event.currentTarget), "name"), {
      onSuccess: (workspace) => {
        void navigate(`/w/${workspace.slug}`);
      },
      onError: (failure) => {
        setErrors(
          failure instanceof ApiError
            ? failure.problems
            : { detail: "Could not reach Baithak. Try again.", fields: {} },
        );
      },
    });
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5" noValidate>
      {errors.detail && <ErrorMessage>{errors.detail}</ErrorMessage>}
      <Field
        label="Workspace name"
        name="name"
        placeholder="Karachi Product Team"
        maxLength={80}
        required
        disabled={!user.email_verified}
        hint="Usually your team or company. You can rename it later."
        errors={errors.fields.name}
      />
      <Button
        type="submit"
        busy={create.isPending}
        busyLabel="Creating the workspace"
        disabled={!user.email_verified}
        className="self-start"
      >
        Create workspace
      </Button>
    </form>
  );
}

/** Home without a workspace yet, and the "new workspace" page. */
export function Home({ user, adding = false }: { user: User; adding?: boolean }) {
  const client = useQueryClient();
  const signOut = useMutation({
    mutationFn: async () => api.POST("/api/v1/auth/signout/"),
    onSuccess: () => {
      client.removeQueries({ predicate: (query) => query.queryKey[0] !== ME[0] });
      client.setQueryData(ME, null);
    },
  });

  return (
    <div className="min-h-dvh bg-bg">
      <header className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-5 py-6">
        <Link
          to="/"
          className="rounded-md focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
        >
          <Wordmark />
          <span className="sr-only">Baithak home</span>
        </Link>
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
      <main className="mx-auto grid max-w-5xl items-center gap-12 px-5 pt-6 pb-16 md:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="settle flex flex-col gap-6">
          <div>
            <h1 className="wonky font-display text-4xl font-semibold tracking-tight sm:text-5xl">
              {adding ? "A new room" : `Welcome, ${user.display_name || user.username}`}
            </h1>
            <p className="mt-3 max-w-prose text-lg text-text-muted">
              {adding
                ? "Give the new workspace a name. You will be its owner."
                : "Start a workspace for your team, or open the invitation link someone sent you."}
            </p>
          </div>
          {!user.email_verified && <ConfirmEmailBanner user={user} />}
          <CreateForm user={user} />
          {adding && (
            <Link to="/" className="text-sm font-semibold text-text-muted hover:text-text">
              Back to your workspaces
            </Link>
          )}
        </div>
        <div className="hidden md:block">
          <Scene />
        </div>
      </main>
    </div>
  );
}
