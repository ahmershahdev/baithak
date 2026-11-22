import type { Notification } from "../api/notifications";
import { resultHref } from "./search";

/** Who it is from: whoever assigned the issue, or wrote the message. */
export function sender(notification: Notification) {
  return notification.issue ? notification.actor : (notification.message?.author ?? null);
}

/** "Bilal mentioned you in general", for a notification's first line. A conversation is named
 * by its people, so a direct message just says who wrote. */
export function describe(notification: Notification, where: string): string {
  const person = sender(notification);
  const name = person ? person.display_name || person.username : "Someone";
  if (notification.issue) return `${name} assigned you ${notification.issue.ref}`;
  if (notification.kind === "mention") return `${name} mentioned you in ${where}`;
  if (notification.kind === "direct") return `${name} wrote to you`;
  return `${name} wrote to everyone in ${where}`;
}

/** Where opening it goes: the issue, or the message in its channel or thread. */
export function notificationHref(slug: string, notification: Notification): string {
  const { issue, message, channel } = notification;
  if (issue) return `/w/${slug}/projects/${issue.project}/issues/${String(issue.number)}`;
  return resultHref(slug, channel ?? 0, message?.parent_seq ?? null);
}

/** The second line: the issue's title, or a short line of the message. */
export function notificationText(notification: Notification): string {
  if (notification.issue) return notification.issue.title;
  return preview(notification.message?.body ?? "") || "Shared a file";
}

/** A short line of the message, for the list. */
export function preview(body: string, max = 140): string {
  const flat = body.replace(/\s+/g, " ").trim();
  if (flat.length <= max) return flat;
  return `${flat.slice(0, max - 1).trimEnd()}…`;
}
