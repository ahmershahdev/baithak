import type { Channel } from "../api/chat";

export function isConversation(channel: Channel): boolean {
  return channel.kind === "direct" || channel.kind === "group";
}

/** A channel's name, or for a conversation the other people in it. */
export function channelTitle(channel: Channel, meId: number): string {
  if (!isConversation(channel)) return channel.name;
  const others = channel.people.filter((person) => person.id !== meId);
  if (others.length === 0) return "Just you";
  return others.map((person) => person.display_name || person.username).join(", ");
}

/** People the person may pick, matching a search on handle or name. */
export function matches(
  person: { username: string; display_name: string },
  search: string,
): boolean {
  const needle = search.trim().toLowerCase().replace(/^@/, "");
  if (!needle) return true;
  return (
    person.username.includes(needle) ||
    person.display_name
      .toLowerCase()
      .split(/\s+/)
      .some((word) => word.startsWith(needle))
  );
}
