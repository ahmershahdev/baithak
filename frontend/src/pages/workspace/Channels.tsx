import { useState, type SubmitEvent } from "react";
import { Link, useNavigate, useOutletContext } from "react-router";

import { useChannels, useCreateChannel, useJoinChannel, type ChannelKind } from "../../api/chat";
import type { ApiErrors } from "../../api/client";
import { ApiError } from "../../api/workspaces";
import { isConversation } from "../../chat/conversations";
import { Button, ErrorMessage, Field } from "../../components/ui";
import { Select } from "../../components/Select";
import { ChannelIcon, PageHeader, Panel } from "../../components/workspace";
import { textField } from "../../forms";
import type { WorkspaceContext } from "./Shell";

export function Channels() {
  const { workspace } = useOutletContext<WorkspaceContext>();
  const navigate = useNavigate();
  const channels = useChannels(workspace.slug);
  const create = useCreateChannel(workspace.slug);
  const joinChannel = useJoinChannel(workspace.slug);
  const [errors, setErrors] = useState<ApiErrors>({ fields: {} });
  const base = `/w/${workspace.slug}`;
  const guest = workspace.role === "guest";

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setErrors({ fields: {} });
    create.mutate(
      {
        name: textField(form, "name"),
        kind: textField(form, "kind") as ChannelKind,
        topic: textField(form, "topic"),
      },
      {
        onSuccess: (channel) => {
          void navigate(`${base}/c/${String(channel.id)}`);
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
        title="Channels"
        intro="Public channels are open to everyone here except guests. Private ones only show up for the people in them."
      />
      {channels.data && (
        <Panel className="settle">
          <ul className="divide-y divide-border">
            {channels.data
              .filter((channel) => !isConversation(channel))
              .map((channel) => (
                <li key={channel.id} className="flex flex-wrap items-center gap-4 px-5 py-4">
                  <div className="min-w-0 flex-1">
                    <Link
                      to={`${base}/c/${String(channel.id)}`}
                      className="inline-flex items-center gap-1.5 font-semibold hover:underline"
                    >
                      <ChannelIcon kind={channel.kind} />
                      {channel.name}
                    </Link>
                    <p className="truncate text-sm text-text-subtle">
                      {channel.archived ? "Archived. " : ""}
                      {channel.topic || (channel.kind === "private" ? "Private" : "Public")}
                    </p>
                  </div>
                  {channel.is_member ? (
                    <span className="text-sm text-text-subtle">Joined</span>
                  ) : (
                    !channel.archived && (
                      <button
                        type="button"
                        onClick={() => {
                          joinChannel.mutate(channel.id, {
                            onSuccess: () => {
                              void navigate(`${base}/c/${String(channel.id)}`);
                            },
                          });
                        }}
                        disabled={joinChannel.isPending}
                        className="rounded-lg border border-border-strong px-3 py-1.5 text-sm font-semibold hover:bg-bg-subtle focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
                      >
                        Join
                      </button>
                    )
                  )}
                </li>
              ))}
          </ul>
        </Panel>
      )}
      {!guest && (
        <section className="flex flex-col gap-3">
          <h2 className="font-display text-xl font-semibold">New channel</h2>
          <Panel className="p-5 sm:p-6">
            <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
              {errors.detail && <ErrorMessage>{errors.detail}</ErrorMessage>}
              <div className="grid items-start gap-4 sm:grid-cols-[minmax(0,1fr)_10rem]">
                <Field
                  label="Name"
                  name="name"
                  placeholder="design-review"
                  autoCapitalize="none"
                  spellCheck={false}
                  maxLength={81}
                  required
                  hint="Lowercase letters, digits, hyphens and underscores."
                  errors={errors.fields.name}
                />
                <div className="flex flex-col gap-2">
                  <label htmlFor="channel-kind" className="text-sm font-semibold">
                    Who can see it
                  </label>
                  <Select
                    id="channel-kind"
                    name="kind"
                    defaultValue="public"
                    large
                    full
                    options={[
                      { value: "public", label: "Everyone" },
                      { value: "private", label: "Invited only" },
                    ]}
                  />
                </div>
              </div>
              <Field
                label="Topic (optional)"
                name="topic"
                placeholder="What this channel is for"
                maxLength={250}
                errors={errors.fields.topic}
              />
              <Button
                type="submit"
                busy={create.isPending}
                busyLabel="Creating"
                className="self-start"
              >
                Create channel
              </Button>
            </form>
          </Panel>
        </section>
      )}
    </div>
  );
}
