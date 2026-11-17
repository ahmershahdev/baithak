import { useState, type SubmitEvent } from "react";
import { useOutletContext } from "react-router";

import type { ApiErrors } from "../../api/client";
import { ApiError, useInvitations, useInvite, useRevokeInvitation } from "../../api/workspaces";
import { Button, ErrorMessage, Field, Notice } from "../../components/ui";
import {
  ConfirmButton,
  PageHeader,
  Panel,
  RoleBadge,
  Select,
  When,
} from "../../components/workspace";
import { textField } from "../../forms";
import { invitable, isAdmin, ROLE_LABELS } from "../../roles";
import type { WorkspaceContext } from "./Shell";

type InvitableRole = Exclude<ReturnType<typeof invitable>[number], "owner">;

export function Invitations() {
  const { workspace } = useOutletContext<WorkspaceContext>();
  const admin = isAdmin(workspace.role);
  const pending = useInvitations(workspace.slug, admin);
  const invite = useInvite(workspace.slug);
  const revoke = useRevokeInvitation(workspace.slug);
  const [errors, setErrors] = useState<ApiErrors>({ fields: {} });
  const [sentTo, setSentTo] = useState<string | null>(null);

  if (!admin) {
    return (
      <div className="flex flex-col gap-8">
        <PageHeader title="Invitations" />
        <ErrorMessage>Only owners and admins can invite people.</ErrorMessage>
      </div>
    );
  }

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const email = textField(form, "email");
    setErrors({ fields: {} });
    setSentTo(null);
    invite.mutate(
      { email, role: textField(form, "role") as InvitableRole },
      {
        onSuccess: (invitation) => {
          setSentTo(invitation.email);
          formElement.reset();
        },
        onError: (failure) => {
          setErrors(
            failure instanceof ApiError
              ? failure.problems
              : { detail: "Could not reach Baithak. Try again.", fields: {} },
          );
        },
      },
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Invitations"
        intro="Invite people by email. The link works once, for that address only, and expires after 7 days."
      />
      <Panel className="settle p-5 sm:p-6">
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          {errors.detail && <ErrorMessage>{errors.detail}</ErrorMessage>}
          {sentTo && <Notice>Invitation sent to {sentTo}.</Notice>}
          <div className="grid items-start gap-4 sm:grid-cols-[minmax(0,1fr)_10rem]">
            <Field
              label="Email"
              name="email"
              type="email"
              inputMode="email"
              autoComplete="off"
              placeholder="teammate@company.com"
              required
              errors={errors.fields.email}
            />
            <div className="flex flex-col gap-2">
              <label htmlFor="invite-role" className="text-sm font-semibold">
                Role
              </label>
              <Select id="invite-role" name="role" defaultValue="member" className="h-12" full>
                {invitable(workspace.role).map((role) => (
                  <option key={role} value={role}>
                    {ROLE_LABELS[role]}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          <Button type="submit" busy={invite.isPending} busyLabel="Sending" className="self-start">
            Send invitation
          </Button>
        </form>
      </Panel>

      <section className="flex flex-col gap-3">
        <h2 className="font-display text-xl font-semibold">Waiting for an answer</h2>
        {pending.data?.length === 0 && <p className="text-text-muted">No open invitations.</p>}
        {pending.data && pending.data.length > 0 && (
          <Panel className="settle">
            <ul className="divide-y divide-border">
              {pending.data.map((invitation) => (
                <li key={invitation.id} className="flex flex-wrap items-center gap-4 px-5 py-4">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold">{invitation.email}</p>
                    <p className="text-sm text-text-subtle">
                      {invitation.invited_by ? `by @${invitation.invited_by}, ` : ""}
                      expires <When iso={invitation.expires_at} />
                    </p>
                  </div>
                  <RoleBadge role={invitation.role} />
                  <ConfirmButton
                    label="Revoke"
                    confirmLabel="Yes, revoke"
                    busy={revoke.isPending}
                    onConfirm={() => {
                      revoke.mutate(invitation.id);
                    }}
                  />
                </li>
              ))}
            </ul>
          </Panel>
        )}
      </section>
    </div>
  );
}
