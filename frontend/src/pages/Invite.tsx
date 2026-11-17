import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { api, readErrors } from "../api/client";
import { keys, type InvitationPreview } from "../api/workspaces";
import { useMe } from "../auth";
import { AuthLayout, Button, ErrorMessage, TextLink } from "../components/ui";
import { ROLE_LABELS } from "../roles";

function usePreview(token: string) {
  return useQuery({
    queryKey: ["invitation", token],
    enabled: token !== "",
    retry: false,
    // Reading a preview changes nothing on the server, so it is safe to load like a page.
    queryFn: async (): Promise<InvitationPreview | null> => {
      const { data } = await api.POST("/api/v1/invitations/preview/", { body: { token } });
      return data ?? null;
    },
  });
}

export function Invite() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const client = useQueryClient();
  const me = useMe();
  const preview = usePreview(token);
  const [error, setError] = useState<string | null>(null);
  const here = `/invite?token=${encodeURIComponent(token)}`;

  const accept = useMutation({
    mutationFn: async () => api.POST("/api/v1/invitations/accept/", { body: { token } }),
    onSuccess: async ({ data, error: apiError }) => {
      if (data) {
        await client.invalidateQueries({ queryKey: keys.all });
        await client.invalidateQueries({ queryKey: ["me"] });
        void navigate(`/w/${data.slug}`);
      } else {
        setError(readErrors(apiError).detail ?? "This invitation could not be accepted.");
      }
    },
    onError: () => {
      setError("Could not reach Baithak. Try again.");
    },
  });

  if (!token || preview.data === null) {
    return (
      <AuthLayout title="This invitation has closed">
        <ErrorMessage>
          The link was already used, revoked, or is more than 7 days old. Ask whoever invited you to
          send a new one.
        </ErrorMessage>
        <p className="mt-6 text-text-muted">
          <TextLink to="/">Go to Baithak</TextLink>
        </p>
      </AuthLayout>
    );
  }

  if (preview.isPending || me.isPending) {
    return (
      <p role="status" className="p-8 text-text-muted">
        Loading
      </p>
    );
  }

  if (preview.isError) {
    return (
      <AuthLayout title="Something went wrong">
        <ErrorMessage>Could not reach Baithak. Try again.</ErrorMessage>
      </AuthLayout>
    );
  }

  const invitation = preview.data;
  const from = invitation.invited_by ? `@${invitation.invited_by}` : "Someone";
  return (
    <AuthLayout
      title={`Join ${invitation.workspace}`}
      intro={
        <>
          {from} invited <strong className="text-text">{invitation.email}</strong> to sit in as{" "}
          {ROLE_LABELS[invitation.role].toLowerCase()}.
        </>
      }
    >
      <div className="flex flex-col gap-5">
        {error && <ErrorMessage>{error}</ErrorMessage>}
        {me.data ? (
          <>
            <Button
              type="button"
              busy={accept.isPending}
              busyLabel="Joining"
              onClick={() => {
                setError(null);
                accept.mutate();
              }}
            >
              Accept and join
            </Button>
            <p className="text-sm text-text-muted">
              Signed in as {me.data.email}. The invitation only works for the address it was sent
              to.
            </p>
          </>
        ) : (
          <>
            <p className="text-text-muted">
              Sign in with the invited address, or create an account with it, and you will come
              straight back here.
            </p>
            <div className="flex flex-wrap gap-3">
              <TextLink to={`/signin?next=${encodeURIComponent(here)}`}>Sign in</TextLink>
              <span className="text-text-subtle">or</span>
              <TextLink to={`/signup?next=${encodeURIComponent(here)}`}>Create an account</TextLink>
            </div>
          </>
        )}
      </div>
    </AuthLayout>
  );
}
