import { useAuthConfig } from "../captcha";

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" className="size-5 shrink-0" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M45.1 24.5c0-1.6-.1-3.1-.4-4.5H24v8.5h11.8c-.5 2.8-2.1 5.1-4.4 6.7v5.5h7.1c4.2-3.8 6.6-9.5 6.6-16.2z"
      />
      <path
        fill="#34A853"
        d="M24 46c5.9 0 10.9-2 14.5-5.3l-7.1-5.5c-2 1.3-4.5 2.1-7.4 2.1-5.7 0-10.5-3.8-12.2-9H4.5v5.7C8.1 41.1 15.5 46 24 46z"
      />
      <path
        fill="#FBBC05"
        d="M11.8 28.3c-.4-1.3-.7-2.8-.7-4.3s.3-3 .7-4.3V14H4.5C3 17 2 20.4 2 24s1 7 2.5 10l7.3-5.7z"
      />
      <path
        fill="#EA4335"
        d="M24 10.7c3.2 0 6.1 1.1 8.4 3.3l6.3-6.3C34.9 4.2 29.9 2 24 2 15.5 2 8.1 6.9 4.5 14l7.3 5.7c1.7-5.2 6.5-9 12.2-9z"
      />
    </svg>
  );
}

/** "Continue with Google" and an "or" rule, when the site has Google sign-in set up. */
export function ProviderSignIn({ next }: { next: string | null }) {
  const config = useAuthConfig();
  if (!config.data?.providers.includes("google")) return null;
  const start = `/api/v1/auth/oidc/google/start/${next ? `?next=${encodeURIComponent(next)}` : ""}`;
  return (
    <div className="flex flex-col gap-5">
      <a
        href={start}
        className="flex h-12 items-center justify-center gap-3 rounded-xl border border-border-strong bg-surface font-semibold transition-colors hover:bg-bg-subtle focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:outline-none"
      >
        <GoogleMark />
        Continue with Google
      </a>
      <p className="flex items-center gap-3 text-xs font-semibold text-text-subtle uppercase">
        <span className="h-px flex-1 bg-border" />
        or
        <span className="h-px flex-1 bg-border" />
      </p>
    </div>
  );
}
