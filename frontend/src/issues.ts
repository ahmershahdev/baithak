import type { components } from "./api/schema";

export type Status = components["schemas"]["StatusEnum"];
export type Priority = components["schemas"]["PriorityEnum"];
export type LabelColor = components["schemas"]["ColorEnum"];

export const STATUS_LABELS: Record<Status, string> = {
  backlog: "Backlog",
  todo: "To do",
  in_progress: "In progress",
  done: "Done",
  canceled: "Canceled",
};

export const PRIORITY_LABELS: Record<Priority, string> = {
  none: "No priority",
  low: "Low",
  medium: "Medium",
  high: "High",
  urgent: "Urgent",
};

export const STATUSES = Object.keys(STATUS_LABELS) as Status[];
export const PRIORITIES = Object.keys(PRIORITY_LABELS) as Priority[];
export const LABEL_COLORS: LabelColor[] = [
  "accent",
  "ember",
  "warning",
  "success",
  "danger",
  "info",
];

// The six brand hues (docs/design.md), the same soft pairs as avatars.
const LABEL_CLASSES: Record<LabelColor, string> = {
  accent: "bg-accent-soft text-accent-soft-text",
  ember: "bg-ember-soft text-ember-soft-text",
  warning: "bg-warning-soft text-warning-soft-text",
  success: "bg-success-soft text-success-soft-text",
  danger: "bg-danger-soft text-danger-soft-text",
  info: "bg-info-soft text-info-soft-text",
};

export function labelClass(color: LabelColor): string {
  return LABEL_CLASSES[color];
}

export function isClosed(status: Status): boolean {
  return status === "done" || status === "canceled";
}

/** "Due Dec 1", "Due today", "Overdue by 3 days", for a YYYY-MM-DD date and today. */
export function dueText(due: string, today: Date): string {
  const [year, month, day] = due.split("-").map(Number);
  const date = new Date(year ?? 0, (month ?? 1) - 1, day ?? 1);
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const days = Math.round((date.getTime() - start.getTime()) / 86_400_000);
  if (days === 0) return "Due today";
  if (days < 0) return `Overdue by ${String(-days)} day${days === -1 ? "" : "s"}`;
  return `Due ${date.toLocaleDateString("en", { day: "numeric", month: "short" })}`;
}

/** A title to start from: the message's first line that has text, cut to the 200 allowed. */
export function titleFrom(body: string): string {
  const line = body.split("\n").find((text) => text.trim()) ?? "";
  return line.trim().slice(0, 200);
}
