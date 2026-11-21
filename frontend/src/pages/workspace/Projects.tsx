import { useState, type SubmitEvent } from "react";
import { Link, useOutletContext } from "react-router";

import { useCreateProject, useProjects } from "../../api/issues";
import { ApiError } from "../../api/workspaces";
import { Button, ErrorMessage, Field } from "../../components/ui";
import { PageHeader, Panel } from "../../components/workspace";
import { isAdmin } from "../../roles";
import type { WorkspaceContext } from "./Shell";

export function Projects() {
  const { workspace } = useOutletContext<WorkspaceContext>();
  const projects = useProjects(workspace.slug);
  const create = useCreateProject(workspace.slug);
  const [form, setForm] = useState({ key: "", name: "", description: "" });

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    create.mutate(form, {
      onSuccess: () => {
        setForm({ key: "", name: "", description: "" });
      },
    });
  }

  const fields = create.error instanceof ApiError ? create.error.problems.fields : {};

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Projects"
        intro="Issues live in projects. Each issue is numbered in its project, like BAI-12."
      />
      {projects.data && projects.data.length === 0 && (
        <p className="text-text-muted">No projects yet.</p>
      )}
      {projects.data && projects.data.length > 0 && (
        <Panel className="settle">
          <ul aria-label="Projects" className="divide-y divide-border">
            {projects.data.map((project) => (
              <li key={project.key}>
                <Link
                  to={`/w/${workspace.slug}/projects/${project.key}`}
                  className="flex items-center gap-4 px-5 py-4 hover:bg-bg-subtle"
                >
                  <span className="rounded-md bg-surface-sunken px-2 py-0.5 font-mono text-sm font-semibold">
                    {project.key}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span
                      className={`block truncate font-semibold ${project.archived ? "text-text-subtle line-through" : ""}`}
                    >
                      {project.name}
                    </span>
                    {project.description && (
                      <span className="block truncate text-sm text-text-muted">
                        {project.description}
                      </span>
                    )}
                  </span>
                  <span className="text-sm text-text-muted tabular-nums">
                    {project.open_issues} open
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Panel>
      )}
      {isAdmin(workspace.role) && (
        <Panel className="p-6">
          <h2 className="mb-4 font-display text-lg font-semibold">New project</h2>
          <form onSubmit={submit} className="flex flex-col gap-4">
            <div className="grid gap-4 sm:grid-cols-[10rem_1fr]">
              <Field
                label="Key"
                name="key"
                value={form.key}
                onChange={(event) => {
                  setForm({ ...form, key: event.target.value.toUpperCase() });
                }}
                placeholder="BAI"
                maxLength={10}
                autoCapitalize="characters"
                spellCheck={false}
                required
                errors={fields.key}
              />
              <Field
                label="Name"
                name="name"
                value={form.name}
                onChange={(event) => {
                  setForm({ ...form, name: event.target.value });
                }}
                placeholder="Baithak web app"
                maxLength={80}
                required
                errors={fields.name}
              />
            </div>
            <Field
              label="What it is for (optional)"
              name="description"
              value={form.description}
              onChange={(event) => {
                setForm({ ...form, description: event.target.value });
              }}
              maxLength={2000}
              errors={fields.description}
            />
            {create.error && !(create.error instanceof ApiError) && (
              <ErrorMessage>Could not reach Baithak. Try again.</ErrorMessage>
            )}
            <Button
              type="submit"
              busy={create.isPending}
              busyLabel="Creating"
              className="self-start"
            >
              Create project
            </Button>
          </form>
        </Panel>
      )}
    </div>
  );
}
