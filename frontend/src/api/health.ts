export type HealthStatus = "ok" | "error";

export interface Health {
  status: HealthStatus;
  database: HealthStatus;
  redis: HealthStatus;
}

export async function fetchHealth(): Promise<Health> {
  const response = await fetch("/health/", { headers: { Accept: "application/json" } });
  // 503 still carries a body that says which part is down.
  if (response.status !== 200 && response.status !== 503) {
    throw new Error(`Health check failed with ${String(response.status)}`);
  }
  return (await response.json()) as Health;
}
