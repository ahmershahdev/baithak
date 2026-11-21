import type { components } from "../api/schema";

export type Reaction = components["schemas"]["Reaction"];

/** The picker's choices, as code point escapes (AGENTS.md: no emoji characters in code). */
export const QUICK_REACTIONS: readonly { emoji: string; name: string }[] = [
  { emoji: "\u{1F44D}", name: "thumbs up" },
  { emoji: "❤️", name: "red heart" },
  { emoji: "\u{1F602}", name: "tears of joy" },
  { emoji: "\u{1F389}", name: "party popper" },
  { emoji: "\u{1F64F}", name: "folded hands" },
  { emoji: "\u{1F440}", name: "eyes" },
  { emoji: "\u{1F525}", name: "fire" },
  { emoji: "✅", name: "check mark" },
  { emoji: "\u{1F914}", name: "thinking face" },
  { emoji: "\u{1F62E}", name: "surprised face" },
  { emoji: "\u{1F622}", name: "crying face" },
  { emoji: "\u{1F44F}", name: "clapping hands" },
  { emoji: "\u{1F680}", name: "rocket" },
  { emoji: "\u{1F4AF}", name: "hundred points" },
  { emoji: "☕", name: "hot drink" },
  { emoji: "\u{1F64C}", name: "raising hands" },
];

const NAMES = new Map(QUICK_REACTIONS.map((r) => [r.emoji, r.name]));

export function emojiName(emoji: string): string {
  return NAMES.get(emoji) ?? emoji;
}

export function reactedByMe(reaction: Reaction, meId: number): boolean {
  return reaction.users.some((user) => user.id === meId);
}

/** "You and Bilal reacted with fire", for the chip's label and tooltip. */
export function whoReacted(reaction: Reaction, meId: number): string {
  const names = reaction.users.map((user) =>
    user.id === meId ? "You" : user.display_name || user.username,
  );
  const mine = names.indexOf("You");
  if (mine > 0) names.unshift(...names.splice(mine, 1));
  const shown =
    names.length > 3 ? [...names.slice(0, 3), `${String(names.length - 3)} more`] : names;
  const list =
    shown.length === 1 ? shown[0] : `${shown.slice(0, -1).join(", ")} and ${shown.at(-1) ?? ""}`;
  return `${list ?? ""} reacted with ${emojiName(reaction.emoji)}`;
}
