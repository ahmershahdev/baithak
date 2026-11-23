import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, readErrors } from "../../api/client";
import { ApiError } from "../../api/workspaces";
import { Button, ErrorMessage, Notice, QuietButton } from "../../components/ui";
import { Panel, When } from "../../components/workspace";

const KEY = ["me", "devices"] as const;

function DeviceIcon({ name }: { name: string }) {
  const phone = /iPhone|Android/.test(name);
  return (
    <span
      aria-hidden="true"
      className="grid size-10 shrink-0 place-items-center rounded-xl bg-surface-sunken text-text-muted"
    >
      <svg
        viewBox="0 0 20 20"
        className="size-5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      >
        {phone ? (
          <path d="M6.5 2.5h7v15h-7z M9 15h2" strokeLinejoin="round" />
        ) : (
          <path d="M3.5 4.5h13v9h-13z M1.5 16h17" strokeLinejoin="round" />
        )}
      </svg>
    </span>
  );
}

export function DeviceSettings() {
  const client = useQueryClient();
  const [problem, setProblem] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const devices = useQuery({
    queryKey: KEY,
    queryFn: async () => {
      const result = await api.GET("/api/v1/auth/devices/");
      if (!result.data) throw new ApiError(result.response.status, readErrors(result.error));
      return result.data;
    },
  });

  function settled(message: string | null, failure: string | null) {
    setDone(message);
    setProblem(failure);
    void client.invalidateQueries({ queryKey: KEY });
  }

  const one = useMutation({
    mutationFn: async (id: number) =>
      api.DELETE("/api/v1/auth/devices/{device_id}/", { params: { path: { device_id: id } } }),
    onSuccess: ({ response }) => {
      settled(
        response.ok ? "That device is signed out." : null,
        response.ok ? null : "Could not sign it out.",
      );
    },
    onError: () => {
      settled(null, "Could not reach Baithak. Try again.");
    },
  });
  const others = useMutation({
    mutationFn: async () => api.POST("/api/v1/auth/devices/sign-out-others/"),
    onSuccess: ({ data }) => {
      const count = data?.signed_out ?? 0;
      settled(
        count === 1
          ? "1 other device is signed out."
          : `${String(count)} other devices are signed out.`,
        null,
      );
    },
    onError: () => {
      settled(null, "Could not reach Baithak. Try again.");
    },
  });

  const list = devices.data ?? [];
  const hasOthers = list.some((device) => !device.current);
  return (
    <Panel className="settle flex flex-col gap-4 p-6">
      <h2 className="font-display text-lg font-semibold">Signed-in devices</h2>
      <p className="text-text-muted">
        Where your account is signed in. Signing a device out also closes its open tabs&rsquo; live
        connection. If you don&rsquo;t recognise one, sign it out and change your password.
      </p>
      {devices.isPending && (
        <p role="status" className="text-text-muted">
          Loading
        </p>
      )}
      {devices.isError && <ErrorMessage>Could not load your devices.</ErrorMessage>}
      {problem && <ErrorMessage>{problem}</ErrorMessage>}
      {done && <Notice>{done}</Notice>}
      {list.length > 0 && (
        <ul
          aria-label="Devices"
          className="flex flex-col divide-y divide-border rounded-xl border border-border"
        >
          {list.map((device) => (
            <li key={device.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <DeviceIcon name={device.name} />
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 font-semibold">
                  {device.name}
                  {device.current && (
                    <span className="rounded-full bg-success-soft px-2 py-0.5 text-xs font-semibold text-success-soft-text">
                      This device
                    </span>
                  )}
                </p>
                <p className="text-sm text-text-subtle">
                  Active <When iso={device.last_seen_at} />, signed in{" "}
                  <When iso={device.created_at} />
                </p>
              </div>
              {!device.current && (
                <QuietButton
                  type="button"
                  aria-label={`Sign out ${device.name}`}
                  disabled={one.isPending}
                  onClick={() => {
                    one.mutate(device.id);
                  }}
                >
                  Sign out
                </QuietButton>
              )}
            </li>
          ))}
        </ul>
      )}
      {hasOthers && (
        <Button
          type="button"
          busy={others.isPending}
          busyLabel="Signing out"
          className="self-start"
          onClick={() => {
            others.mutate();
          }}
        >
          Sign out everywhere else
        </Button>
      )}
    </Panel>
  );
}
