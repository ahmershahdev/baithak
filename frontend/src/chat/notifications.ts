import type { Notification } from "../api/notifications";

/** "Bilal mentioned you in general", for a notification's first line. A conversation is named
 * by its people, so a direct message just says who wrote. */
export function describe(notification: Notification, where: string): string {
  const author = notification.message.author;
  const name = author ? author.display_name || author.username : "Someone";
  if (notification.kind === "mention") return `${name} mentioned you in ${where}`;
  if (notification.kind === "direct") return `${name} wrote to you`;
  return `${name} wrote to everyone in ${where}`;
}

/** A short line of the message, for the list. */
export function preview(body: string, max = 140): string {
  const flat = body.replace(/\s+/g, " ").trim();
  if (flat.length <= max) return flat;
  return `${flat.slice(0, max - 1).trimEnd()}…`;
}
