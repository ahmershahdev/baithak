import type { ZxcvbnFactory } from "@zxcvbn-ts/core";

export interface Strength {
  /** 0 (guessable in seconds) to 4 (very hard to guess). */
  score: 0 | 1 | 2 | 3 | 4;
  warning: string | null;
  suggestion: string | null;
}

let checker: Promise<ZxcvbnFactory> | null = null;

// The dictionaries are large, so they load the first time someone types a new password, in
// their own chunk, and never on pages without a password field.
function load(): Promise<ZxcvbnFactory> {
  checker ??= Promise.all([
    import("@zxcvbn-ts/core"),
    import("@zxcvbn-ts/language-common"),
    // Only the English messages: the English word list is another 1.2 MB, and the common
    // list (leaked passwords, names, keyboard patterns) catches what matters for a password.
    import("@zxcvbn-ts/language-en/dist/translations"),
  ]).then(
    ([core, common, en]) =>
      new core.ZxcvbnFactory({
        translations: en.default,
        graphs: common.adjacencyGraphs,
        dictionary: common.dictionary,
      }),
  );
  return checker;
}

/** Scores a password the way an attacker would guess it; `related` are the person's own words. */
export async function measure(password: string, related: string[]): Promise<Strength> {
  const result = (await load()).check(password, related.filter(Boolean));
  return {
    score: result.score,
    warning: result.feedback.warning || null,
    suggestion: result.feedback.suggestions[0] ?? null,
  };
}
