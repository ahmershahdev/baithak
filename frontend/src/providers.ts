/** Why a provider sign-in came back to /signin?error=..., from apps/accounts/views.py. */
export const PROVIDER_PROBLEMS: Record<string, string> = {
  cancelled: "Signing in with Google was cancelled.",
  failed: "Signing in with Google did not work. Try again.",
  unverified: "Your Google account's email address isn't verified, so it can't sign in here.",
  inactive: "This account is turned off. Write to support if you need help.",
  locked: "This account is locked after too many wrong attempts. Try again later.",
};
