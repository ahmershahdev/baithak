import { useQuery } from "@tanstack/react-query";

import { fetchHealth, type HealthStatus } from "./api";

function StatusRow({ label, status }: { label: string; status: HealthStatus | undefined }) {
  const text = status === undefined ? "Checking" : status === "ok" ? "Running" : "Not reachable";
  const dot =
    status === undefined
      ? "bg-presence-offline"
      : status === "ok"
        ? "bg-presence-online"
        : "bg-presence-busy";
  return (
    <li className="flex items-center justify-between gap-4 py-3">
      <span>{label}</span>
      <span className="flex items-center gap-2 text-text-muted">
        <span aria-hidden="true" className={`size-2.5 rounded-full ${dot}`} />
        {text}
      </span>
    </li>
  );
}

export function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 10_000 });
  const backend = health.isError ? "error" : health.data ? "ok" : undefined;

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-8 px-4 py-12">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">Baithak</h1>
        <p className="mt-2 text-text-muted">
          Team chat and issue tracking in one place. Nothing to sign in to yet; this page shows
          whether the local backend is up.
        </p>
      </header>
      <section
        aria-labelledby="services"
        className="rounded-lg border border-border bg-surface px-4 shadow-sm"
      >
        <h2 id="services" className="sr-only">
          Services
        </h2>
        <ul className="divide-y divide-border">
          <StatusRow label="Backend" status={backend} />
          <StatusRow label="Database" status={health.data?.database} />
          <StatusRow label="Redis" status={health.data?.redis} />
        </ul>
      </section>
      {health.isError && (
        <p className="rounded-lg bg-danger-soft px-4 py-3 text-danger-soft-text" role="alert">
          The backend did not answer. Start it with <code>docker compose up -d</code> from the
          repository root.
        </p>
      )}
    </main>
  );
}
