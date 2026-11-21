import { useState } from "react";
import { useNavigate, useOutletContext } from "react-router";

import {
  ApiError,
  useChangeRole,
  useMembers,
  useRemoveMember,
  type Member,
} from "../../api/workspaces";
import { Select } from "../../components/Select";
import { ErrorMessage } from "../../components/ui";
import {
  Avatar,
  ConfirmButton,
  PageHeader,
  Panel,
  RoleBadge,
  When,
} from "../../components/workspace";
import { canManage, grantable, ROLE_LABELS, type Role } from "../../roles";
import { useOnline } from "../../chat/live";
import type { WorkspaceContext } from "./Shell";

function problem(error: unknown): string {
  return error instanceof ApiError
    ? (error.problems.detail ?? error.message)
    : "Could not reach Baithak. Try again.";
}

function Row({
  member,
  myRole,
  isMe,
  online,
}: {
  member: Member;
  myRole: Role;
  isMe: boolean;
  online: boolean;
}) {
  const { workspace } = useOutletContext<WorkspaceContext>();
  const navigate = useNavigate();
  const changeRole = useChangeRole(workspace.slug);
  const remove = useRemoveMember(workspace.slug);
  const [error, setError] = useState<string | null>(null);
  const manageable = !isMe && canManage(myRole, member.role);
  const name = member.display_name || member.username;

  return (
    <li className="flex flex-col gap-2 px-5 py-4">
      <div className="flex flex-wrap items-center gap-4">
        <Avatar name={name} colorKey={member.username} online={online} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">
            {name} {isMe && <span className="font-normal text-text-subtle">(you)</span>}
          </p>
          <p className="truncate text-sm text-text-subtle">
            @{member.username} · joined <When iso={member.joined_at} />
          </p>
        </div>
        {manageable ? (
          <Select
            aria-label={`Role of ${name}`}
            value={member.role}
            disabled={changeRole.isPending}
            options={grantable(myRole).map((role) => ({ value: role, label: ROLE_LABELS[role] }))}
            onChange={(role) => {
              setError(null);
              changeRole.mutate(
                { userId: member.user_id, role },
                {
                  onError: (failure) => {
                    setError(problem(failure));
                  },
                },
              );
            }}
          />
        ) : (
          <RoleBadge role={member.role} />
        )}
        {(manageable || isMe) && (
          <ConfirmButton
            label={isMe ? "Leave" : "Remove"}
            confirmLabel={isMe ? "Yes, leave" : `Yes, remove ${name}`}
            busy={remove.isPending}
            onConfirm={() => {
              setError(null);
              remove.mutate(member.user_id, {
                onSuccess: () => {
                  if (isMe) void navigate("/");
                },
                onError: (failure) => {
                  setError(problem(failure));
                },
              });
            }}
          />
        )}
      </div>
      {error && <ErrorMessage>{error}</ErrorMessage>}
    </li>
  );
}

export function Members() {
  const { workspace, me } = useOutletContext<WorkspaceContext>();
  const members = useMembers(workspace.slug);
  const online = useOnline(workspace.slug);

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Members"
        intro="Everyone in this workspace. Owners and admins can change roles and remove people; anyone can leave."
      />
      {members.isError && <ErrorMessage>{problem(members.error)}</ErrorMessage>}
      {members.data && (
        <Panel className="settle">
          <ul className="divide-y divide-border">
            {members.data.map((member) => (
              <Row
                key={member.user_id}
                member={member}
                myRole={workspace.role}
                isMe={member.user_id === me.id}
                online={online.has(member.user_id)}
              />
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}
