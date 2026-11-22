import { useState, type SubmitEvent } from "react";
import { useOutletContext } from "react-router";

import type { ApiErrors } from "../../api/client";
import { ApiError, useRenameWorkspace } from "../../api/workspaces";
import { Button, ErrorMessage, Field, Notice } from "../../components/ui";
import { PageHeader, Panel } from "../../components/workspace";
import { textField } from "../../forms";
import { isAdmin } from "../../roles";
import { GitHubSettings } from "./GitHubSettings";
import type { WorkspaceContext } from "./Shell";

export function Settings() {
  const { workspace } = useOutletContext<WorkspaceContext>();
  const rename = useRenameWorkspace(workspace.slug);
  const [errors, setErrors] = useState<ApiErrors>({ fields: {} });
  const [saved, setSaved] = useState(false);

  if (!isAdmin(workspace.role)) {
    return (
      <div className="flex flex-col gap-8">
        <PageHeader title="Settings" />
        <ErrorMessage>Only owners and admins can change the workspace.</ErrorMessage>
      </div>
    );
  }

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrors({ fields: {} });
    setSaved(false);
    rename.mutate(textField(new FormData(event.currentTarget), "name"), {
      onSuccess: () => {
        setSaved(true);
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
    <div className="flex flex-col gap-8">
      <PageHeader title="Settings" />
      <Panel className="settle p-5 sm:p-6">
        <form onSubmit={submit} className="flex max-w-md flex-col gap-4" noValidate>
          {errors.detail && <ErrorMessage>{errors.detail}</ErrorMessage>}
          {saved && <Notice>Saved.</Notice>}
          <Field
            label="Workspace name"
            name="name"
            defaultValue={workspace.name}
            maxLength={80}
            required
            hint={`The address stays /w/${workspace.slug}.`}
            errors={errors.fields.name}
          />
          <Button type="submit" busy={rename.isPending} busyLabel="Saving" className="self-start">
            Save
          </Button>
        </form>
      </Panel>
      <GitHubSettings slug={workspace.slug} />
    </div>
  );
}
