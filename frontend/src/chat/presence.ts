import type { components } from "../api/schema";

export type Person = components["schemas"]["Author"];

/** How long a typing notice shows. The server sends at most one every 3 s per person and
 * place, so a steady typist stays shown and a stopped one fades. */
export const TYPING_SHOWN_MS = 5_000;
/** How often this tab tells the server it is typing in one place. */
export const TYPING_SEND_MS = 3_000;

export interface Typer {
  user: Person;
  until: number;
}

/** Who is typing where, keyed by placeKey. */
export type TypingState = Record<string, Typer[]>;

export function placeKey(channel: number, thread: number | null): string {
  return `${String(channel)}:${thread === null ? "" : String(thread)}`;
}

export function addTyper(state: TypingState, key: string, user: Person, now: number): TypingState {
  const others = (state[key] ?? []).filter((typer) => typer.user.id !== user.id);
  return { ...state, [key]: [...others, { user, until: now + TYPING_SHOWN_MS }] };
}

/** Their message arrived, so they are done typing it. */
export function clearTyper(state: TypingState, key: string, userId: number): TypingState {
  const typers = state[key];
  if (!typers?.some((typer) => typer.user.id === userId)) return state;
  return { ...state, [key]: typers.filter((typer) => typer.user.id !== userId) };
}

export function activeTypers(state: TypingState, key: string, now: number): Person[] {
  return (state[key] ?? []).filter((typer) => typer.until > now).map((typer) => typer.user);
}

export function typingText(people: Person[]): string | null {
  const names = people.map((person) => person.display_name || person.username);
  if (names.length === 0) return null;
  if (names.length === 1) return `${names[0] ?? ""} is typing`;
  if (names.length === 2) return `${names[0] ?? ""} and ${names[1] ?? ""} are typing`;
  return "Several people are typing";
}

export function applyPresence(online: number[], user: number, isOnline: boolean): number[] {
  const rest = online.filter((id) => id !== user);
  return isOnline ? [...rest, user] : rest;
}
