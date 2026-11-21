import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";

import { api, readErrors } from "../../api/client";
import type { components } from "../../api/schema";
import { ApiError } from "../../api/workspaces";
import { Select } from "../../components/Select";
import { Button, ErrorMessage, Notice } from "../../components/ui";
import { PageHeader, Panel } from "../../components/workspace";

type Settings = components["schemas"]["NotificationSettings"];

const KEY = ["me", "notification-settings"] as const;
const ZONES = Intl.supportedValuesOf("timeZone");
const BROWSER_ZONE = Intl.DateTimeFormat().resolvedOptions().timeZone;

const timeClass =
  "h-10 rounded-lg border border-border-strong bg-bg px-3 text-sm outline-none focus-visible:border-focus-ring focus-visible:ring-4 focus-visible:ring-focus-ring/20 disabled:opacity-50";

/** "22:00:00" from the API as "22:00" for a time input. */
const hhmm = (value: string | null | undefined) => (value ? value.slice(0, 5) : "");

export function MySettings() {
  const settings = useQuery({
    queryKey: KEY,
    queryFn: async () => {
      const result = await api.GET("/api/v1/auth/notifications/");
      if (!result.data) throw new ApiError(result.response.status, readErrors(result.error));
      return result.data;
    },
  });
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Your settings" intro="These apply to you in every workspace." />
      {settings.isPending && (
        <p role="status" className="text-text-muted">
          Loading
        </p>
      )}
      {settings.isError && <ErrorMessage>Could not load your settings.</ErrorMessage>}
      {settings.data && <EmailForm saved={settings.data} />}
    </div>
  );
}

function EmailForm({ saved }: { saved: Settings }) {
  const client = useQueryClient();
  const [byEmail, setByEmail] = useState(saved.notify_by_email ?? true);
  const [quiet, setQuiet] = useState(Boolean(saved.quiet_start && saved.quiet_end));
  const [start, setStart] = useState(hhmm(saved.quiet_start) || "22:00");
  const [end, setEnd] = useState(hhmm(saved.quiet_end) || "08:00");
  const [zone, setZone] = useState(saved.time_zone);
  const [done, setDone] = useState(false);
  const save = useMutation({
    mutationFn: async (body: Settings) => {
      const result = await api.PATCH("/api/v1/auth/notifications/", { body });
      if (!result.data) throw new ApiError(result.response.status, readErrors(result.error));
      return result.data;
    },
    onSuccess: (data) => {
      client.setQueryData(KEY, data);
      setDone(true);
    },
  });

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setDone(false);
    save.mutate({
      notify_by_email: byEmail,
      quiet_start: quiet ? start : null,
      quiet_end: quiet ? end : null,
      time_zone: zone,
    });
  }

  const problem =
    save.error instanceof ApiError
      ? Object.values(save.error.problems.fields).flat().join(" ") ||
        (save.error.problems.detail ?? save.error.message)
      : save.error
        ? "Could not reach Baithak. Try again."
        : null;

  return (
    <Panel className="settle p-6">
      <form onSubmit={submit} className="flex flex-col gap-6">
        <fieldset className="flex flex-col gap-2">
          <legend className="font-display text-lg font-semibold">Email</legend>
          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              checked={byEmail}
              onChange={(event) => {
                setByEmail(event.target.checked);
              }}
              className="mt-1 size-4 accent-accent"
            />
            <span>
              Email me about mentions and direct messages I haven&apos;t read
              <span className="block text-sm text-text-muted">
                After ten minutes, and never while you have Baithak open in that workspace.
              </span>
            </span>
          </label>
        </fieldset>

        <fieldset className="flex flex-col gap-3" disabled={!byEmail}>
          <legend className="font-display text-lg font-semibold">Quiet hours</legend>
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={quiet}
              onChange={(event) => {
                setQuiet(event.target.checked);
              }}
              className="size-4 accent-accent"
            />
            No emails between
          </label>
          <div className="flex flex-wrap items-center gap-3 pl-7">
            <label className="flex items-center gap-2 text-sm">
              <span className="sr-only">Quiet from</span>
              <input
                type="time"
                value={start}
                disabled={!quiet}
                onChange={(event) => {
                  setStart(event.target.value);
                }}
                className={timeClass}
              />
            </label>
            <span className="text-sm text-text-muted">and</span>
            <label className="flex items-center gap-2 text-sm">
              <span className="sr-only">Quiet until</span>
              <input
                type="time"
                value={end}
                disabled={!quiet}
                onChange={(event) => {
                  setEnd(event.target.value);
                }}
                className={timeClass}
              />
            </label>
          </div>
          <div className="flex flex-wrap items-center gap-3 pl-7">
            <span className="text-sm text-text-muted">Your time zone</span>
            <Select
              aria-label="Time zone"
              value={zone}
              onChange={setZone}
              options={ZONES.map((name) => ({ value: name, label: name.replace(/_/g, " ") }))}
            />
            {zone !== BROWSER_ZONE && ZONES.includes(BROWSER_ZONE) && (
              <button
                type="button"
                onClick={() => {
                  setZone(BROWSER_ZONE);
                }}
                className="text-sm font-semibold text-accent-text hover:underline"
              >
                Use {BROWSER_ZONE.replace(/_/g, " ")}
              </button>
            )}
          </div>
        </fieldset>

        {problem && <ErrorMessage>{problem}</ErrorMessage>}
        {done && <Notice>Saved.</Notice>}
        <Button type="submit" busy={save.isPending} busyLabel="Saving" className="self-start">
          Save
        </Button>
      </form>
    </Panel>
  );
}
