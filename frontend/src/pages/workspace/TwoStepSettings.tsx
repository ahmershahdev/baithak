import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";

import { api, readErrors } from "../../api/client";
import type { components } from "../../api/schema";
import { ApiError } from "../../api/workspaces";
import { PasswordField } from "../../components/PasswordField";
import { QrCode } from "../../components/QrCode";
import { Button, ErrorMessage, Field, Notice, QuietButton } from "../../components/ui";
import { Panel } from "../../components/workspace";
import { textField } from "../../forms";

type Setup = components["schemas"]["TwoStepSetup"];

const KEY = ["me", "two-step"] as const;
const UNREACHABLE = "Could not reach Baithak. Try again.";

/** "JBSW Y3DP EHPK 3PXP": easier to read off a screen and type into a phone. */
export function groupedKey(secret: string): string {
  return secret.replace(/(.{4})/g, "$1 ").trim();
}

function problemOf(error: unknown): string {
  return readErrors(error).detail ?? Object.values(readErrors(error).fields).flat().join(" ");
}

function CodeField({ label = "Code from the app" }: { label?: string }) {
  return (
    <Field
      label={label}
      name="code"
      inputMode="numeric"
      autoComplete="one-time-code"
      maxLength={11}
      placeholder="123 456"
      required
      className="font-mono tracking-widest"
    />
  );
}

function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const [copied, setCopied] = useState(false);
  const text = `Baithak recovery codes\n\n${codes.join("\n")}\n\nEach code works once.\n`;
  return (
    <div className="flex flex-col gap-4">
      <Notice>
        Save these recovery codes somewhere safe, such as a password manager. If you lose your
        phone, each one signs you in once. They are shown only now.
      </Notice>
      <ul
        aria-label="Recovery codes"
        className="grid grid-cols-2 gap-2 rounded-xl border border-border bg-bg p-4 font-mono text-sm sm:grid-cols-3"
      >
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-3">
        <a
          href={`data:text/plain;charset=utf-8,${encodeURIComponent(text)}`}
          download="baithak-recovery-codes.txt"
          className="rounded-xl border border-border-strong px-4 py-2 text-sm font-semibold hover:bg-bg-subtle"
        >
          Download
        </a>
        <QuietButton
          type="button"
          onClick={() => {
            void navigator.clipboard.writeText(text).then(() => {
              setCopied(true);
            });
          }}
        >
          {copied ? "Copied" : "Copy"}
        </QuietButton>
        <Button type="button" onClick={onDone} className="ml-auto">
          I have saved them
        </Button>
      </div>
    </div>
  );
}

function SetUp({ setup, onEnabled }: { setup: Setup; onEnabled: (codes: string[]) => void }) {
  const [problem, setProblem] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const enable = useMutation({
    mutationFn: async (code: string) =>
      api.POST("/api/v1/auth/two-step/enable/", { body: { code } }),
    onSuccess: ({ data, error }) => {
      if (data) onEnabled(data.recovery_codes);
      else setProblem(problemOf(error));
    },
    onError: () => {
      setProblem(UNREACHABLE);
    },
  });

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setProblem(null);
    enable.mutate(textField(new FormData(event.currentTarget), "code"));
  }

  return (
    <ol className="flex flex-col gap-6">
      <li className="flex flex-col gap-3">
        <p className="font-semibold">1. Add Baithak to your authenticator app</p>
        <p className="text-sm text-text-muted">
          Any app that makes 6-digit codes works, such as Google Authenticator, Microsoft
          Authenticator, 1Password or Aegis. Scan the code with it.
        </p>
        <div className="flex flex-wrap items-start gap-6">
          <QrCode text={setup.uri} label="QR code for your authenticator app" />
          <div className="flex min-w-0 flex-col gap-3">
            <p className="text-sm text-text-muted">Can&rsquo;t scan? Enter this key by hand:</p>
            <code
              aria-label="Key for your app"
              className="rounded-xl border border-border bg-bg px-4 py-2 font-mono text-lg tracking-wider break-all select-all"
            >
              {groupedKey(setup.secret)}
            </code>
            <QuietButton
              type="button"
              className="self-start"
              onClick={() => {
                void navigator.clipboard.writeText(setup.secret).then(() => {
                  setCopied(true);
                });
              }}
            >
              {copied ? "Copied" : "Copy key"}
            </QuietButton>
            <a href={setup.uri} className="text-sm font-semibold text-accent-text underline">
              On this phone? Open it in your authenticator app
            </a>
          </div>
        </div>
      </li>
      <li>
        <form onSubmit={submit} className="flex flex-col gap-3" noValidate>
          <p className="font-semibold">2. Enter the code the app shows</p>
          <CodeField />
          {problem && <ErrorMessage>{problem}</ErrorMessage>}
          <Button type="submit" busy={enable.isPending} busyLabel="Checking" className="self-start">
            Turn on two-step sign-in
          </Button>
        </form>
      </li>
    </ol>
  );
}

interface Confirmation {
  password: string;
  code: string;
}

interface Outcome {
  ok: boolean;
  error?: unknown;
  codes: string[] | null;
}

async function turnOff(body: Confirmation): Promise<Outcome> {
  const { response, error } = await api.POST("/api/v1/auth/two-step/disable/", { body });
  return { ok: response.ok, error, codes: null };
}

async function renewCodes(body: Confirmation): Promise<Outcome> {
  const { response, data, error } = await api.POST("/api/v1/auth/two-step/recovery-codes/", {
    body,
  });
  return { ok: response.ok, error, codes: data?.recovery_codes ?? null };
}

function Confirmed({
  request,
  submitLabel,
  danger = false,
  onDone,
  onCancel,
}: {
  request: (body: Confirmation) => Promise<Outcome>;
  submitLabel: string;
  danger?: boolean;
  onDone: (codes: string[] | null) => void;
  onCancel: () => void;
}) {
  const [problem, setProblem] = useState<string | null>(null);
  const send = useMutation({
    mutationFn: request,
    onSuccess: ({ ok, error, codes }) => {
      if (ok) onDone(codes);
      else setProblem(problemOf(error));
    },
    onError: () => {
      setProblem(UNREACHABLE);
    },
  });

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setProblem(null);
    const form = new FormData(event.currentTarget);
    send.mutate({ password: textField(form, "password"), code: textField(form, "code") });
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <PasswordField
        label="Your password"
        name="password"
        autoComplete="current-password"
        required
      />
      <CodeField label="Code from the app, or a recovery code" />
      {problem && <ErrorMessage>{problem}</ErrorMessage>}
      <div className="flex flex-wrap gap-3">
        <button
          type="submit"
          disabled={send.isPending}
          className={`h-11 rounded-xl px-5 font-semibold disabled:opacity-70 ${
            danger
              ? "bg-danger-fill text-on-danger hover:opacity-90"
              : "bg-accent text-on-accent hover:bg-accent-hover"
          }`}
        >
          {send.isPending ? "Checking" : submitLabel}
        </button>
        <QuietButton type="button" onClick={onCancel}>
          Cancel
        </QuietButton>
      </div>
    </form>
  );
}

type Mode = "idle" | "setup" | "codes" | "off" | "renew";

export function TwoStepSettings() {
  const client = useQueryClient();
  const [mode, setMode] = useState<Mode>("idle");
  const [setup, setSetup] = useState<Setup | null>(null);
  const [codes, setCodes] = useState<string[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const status = useQuery({
    queryKey: KEY,
    queryFn: async () => {
      const result = await api.GET("/api/v1/auth/two-step/");
      if (!result.data) throw new ApiError(result.response.status, readErrors(result.error));
      return result.data;
    },
  });
  const start = useMutation({
    mutationFn: async () => api.POST("/api/v1/auth/two-step/setup/"),
    onSuccess: ({ data, error }) => {
      if (data) {
        setSetup(data);
        setMode("setup");
      } else setProblem(problemOf(error));
    },
    onError: () => {
      setProblem(UNREACHABLE);
    },
  });

  function showCodes(next: string[]) {
    setCodes(next);
    setMode("codes");
    void client.invalidateQueries({ queryKey: KEY });
  }

  const enabled = status.data?.enabled ?? false;
  return (
    <Panel className="settle flex flex-col gap-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-lg font-semibold">Two-step sign-in</h2>
        {status.data && (
          <span
            className={`rounded-full px-3 py-0.5 text-xs font-semibold ${
              enabled
                ? "bg-success-soft text-success-soft-text"
                : "bg-surface-sunken text-text-muted"
            }`}
          >
            {enabled ? "On" : "Off"}
          </span>
        )}
      </div>
      <p className="text-text-muted">
        After your password, Baithak also asks for a code from an app on your phone, so a stolen
        password alone can&rsquo;t get into your account.
      </p>
      {status.isError && <ErrorMessage>Could not load two-step sign-in.</ErrorMessage>}
      {problem && <ErrorMessage>{problem}</ErrorMessage>}

      {mode === "setup" && setup && <SetUp setup={setup} onEnabled={showCodes} />}
      {mode === "codes" && (
        <RecoveryCodes
          codes={codes}
          onDone={() => {
            setCodes([]);
            setMode("idle");
          }}
        />
      )}
      {(mode === "off" || mode === "renew") && (
        <Confirmed
          request={mode === "off" ? turnOff : renewCodes}
          submitLabel={mode === "off" ? "Turn off two-step sign-in" : "Make new recovery codes"}
          danger={mode === "off"}
          onDone={(fresh) => {
            if (fresh) showCodes(fresh);
            else {
              setMode("idle");
              void client.invalidateQueries({ queryKey: KEY });
            }
          }}
          onCancel={() => {
            setMode("idle");
          }}
        />
      )}

      {mode === "idle" && status.data && !enabled && (
        <Button
          type="button"
          busy={start.isPending}
          busyLabel="Starting"
          className="self-start"
          onClick={() => {
            setProblem(null);
            start.mutate();
          }}
        >
          Set up two-step sign-in
        </Button>
      )}
      {mode === "idle" && enabled && status.data && (
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-sm text-text-muted">
            {status.data.recovery_codes_left === 1
              ? "1 recovery code left."
              : `${String(status.data.recovery_codes_left)} recovery codes left.`}
          </p>
          <QuietButton
            type="button"
            onClick={() => {
              setMode("renew");
            }}
          >
            New recovery codes
          </QuietButton>
          <QuietButton
            type="button"
            className="text-danger"
            onClick={() => {
              setMode("off");
            }}
          >
            Turn off
          </QuietButton>
        </div>
      )}
    </Panel>
  );
}
