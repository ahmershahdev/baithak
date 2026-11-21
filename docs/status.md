# Project status

Last updated: 2026-11-21. Update at the end of every work session.

## Where we are

M1 in progress. Merged so far:

- Backend skeleton (#2): Django 5.2 with `dev`, `test` and `prod` settings, ASGI through Channels
  and Daphne, Celery, a custom `accounts.User` (email unique), `/health/` checking MySQL and
  Redis. Dependencies pinned in `backend/pyproject.toml` with `uv.lock`.
- Web app skeleton (#3): Vite 8, React 19, TypeScript 6 (strict), Tailwind 4 with only the
  semantic color tokens, TanStack Query, Vitest, ESLint. Root `npm run dev` starts the Compose
  stack (MySQL 8.4, Redis, backend, worker), waits for it to be healthy and runs Vite, which proxies
  `/api`, `/ws`, `/admin` and `/health` to the backend.
- CI (#4): `backend` (MySQL and Redis service containers), `frontend` and CodeQL (Python,
  TypeScript, Actions). All five checks are required in the "Protect main" ruleset, applied to the
  repository. SonarCloud also runs on PRs.
- Dependabot for Actions, uv, npm, Docker and Compose, held to Django 5.2, Python 3.12, MySQL 8.4
  and TypeScript 6.0.
- Accounts API under `/api/v1/auth/`: CSRF cookie, sign up, sign in (by email), sign out, `me`,
  email verification with resend, password reset. Session auth; CSRF also on anonymous calls;
  `auth` throttle 10 per minute; email sent from Celery through Resend SMTP (from
  `no-reply@ahmershah.dev`, verified in Resend), retried with backoff. `backend/openapi.yaml` and
  `frontend/src/api/schema.d.ts` are generated and checked in CI.

- Auth screens: sign in, sign up, check your email, confirm email, forgot and reset password,
  and a signed-in home with sign out and a "confirm your email" banner. React Router,
  openapi-fetch typed from the schema, CSRF header added by a client middleware. Dev settings
  trust the Vite origin for CSRF.

- Workspaces API under `/api/v1/workspaces/`: list and create (needs a confirmed email; the
  creator is owner), read and rename, members with role changes and removal or leaving, and the
  audit log (cursor-paginated, admins and owners only). Role rules in `apps/core/roles.py` with a
  100% branch coverage gate in CI. `tests/test_access.py` checks every workspace endpoint for 404
  to outsiders.

- Auth hardening: Argon2id hashing, reCAPTCHA v3 with a v2 fallback (off until keys are in
  `.env`), honeypot, per-account sign-in lock, spoof-proof IP throttle, CSP and `no-store` on
  API responses. The local `.env` exists (git ignores it) with a generated secret key.

- Brand (#16): logo, favicons, Fraunces and Instrument Sans, turmeric selection, custom
  scrollbars. Auth screens redesigned: split layout with the animated arch scene, parda password
  toggle, lamplight button, strength meter, placeholders, honeypot and reCAPTCHA wiring, web app
  CSP in the build.

- Invitations API: invite by email with a role (admin and up, never owner), pending list,
  revoke, preview and accept by link (`/invite?token=...`, the signed-in email must match, 7
  days, single use). Audited and in the access test. The reCAPTCHA keys and the Resend key are
  set in the local `.env` and checked working.

- Workspace screens: home opens the last workspace used (or offers to create one), `/w/new`,
  and a workspace shell with switcher, overview, members (role changes, remove, leave),
  invitations (send, revoke), settings (rename) and the audit log (cursor paging). `/invite`
  previews the invitation, sends signed-out people through sign-in or sign-up and back, and
  accepts. M1 is complete.

- M1 released as `v0.1.0` (pre-release) and its milestone closed. Comments trimmed and the rule
  tightened in AGENTS.md.
- M2 started: channels API (public and private, topic, archive, join, leave, add members) under
  `/api/v1/workspaces/{slug}/channels/`, rules in `apps/core/channels.py`, `#general` with every
  workspace. Private channels are 404 to workspace members outside them, in the access test.

- Messages API under `.../channels/{id}/messages/`: send (with `client_id` against duplicates),
  edit, delete (row kept, text removed), history pages by `before`, catch-up by `after_event`.
  `seq` and `event` move under the channel row lock; a 4-thread race test checks they stay
  distinct and gap-free.

- WebSockets: `ws/workspaces/<slug>/` with session auth and Origin check; one group per
  channel; messages and channel changes broadcast after commit; subscriptions follow access
  (join, leave, add, role change, removal) without reconnecting.

- Chat screens: channels in the sidebar, a channel browser with create and join, and the
  channel view with history paging, grouped messages, edit and delete, and a composer whose
  sends show at once and are never doubled. The socket reconnects with backoff and every open
  channel catches up; a test drops the socket and checks nothing is lost or shown twice. Tried
  with two real tabs: a message from one appeared live in the other. M2 is complete.

- M2 released as `v0.2.0`. Account protection: lockout ladder (1 h, 4 h, a week, ban with admin
  unlock) for sign-in and reset codes with owner emails, 6-digit reset codes (10 minutes, one
  use), stronger password rules with a checklist, handle and display-name blocklist with
  look-alike folding, live email and handle availability, `/me` 204 when signed out, the
  reCAPTCHA checkbox shown up front, themed selects, and a contact page that mails
  support@ahmershah.dev.

- M3 started: unread counts and read markers. Channels carry `last_read_seq` and `unread`;
  `POST .../channels/{id}/read/` moves the marker forward only; posting, joining and being added
  move it too; each move reaches all the person's sockets as a `read` event. Rules in
  `apps/core/unread.py`. The sidebar shows a count per channel, an open channel is marked read
  at the bottom of a visible tab, and a "New" line marks where unread messages began.

- Threads: replies under `.../messages/{seq}/replies/`, one level deep, with reply counts and
  "also send to channel". A reply kept in its thread has no channel seq; each reply and the
  parent's new count are channel events, so catch-up covers threads. The web app opens a thread
  beside the channel (`?thread=<seq>`, full screen on small widths), with "N replies" and a
  Reply action on messages and a composer with "Also send to #channel".

## Next session

M3, in this order:

1. Mentions parsed in `apps/core` (`@person`, `@channel`) with autocomplete.
2. Reactions.
3. Direct and group messages.
4. Typing indicator and online status in Redis with expiry.

## Open questions

- reCAPTCHA sends visitor data to Google; mention it in the privacy notes before launch.

- Decided: an unverified person can sign in but can't create or join a workspace (enforce in the
  workspaces API).
- openapi-typescript declares TypeScript 5 as its peer; `frontend/package.json` overrides it to
  the project's 6.0. Drop the override when it supports 6.

- jsdom is held at 29.x so tests run on Node 22.12; 30 and later need Node 22.22 or 24.15. Lift
  it once the local Node is upgraded.

- Presence design (see [architecture.md](architecture.md)).
- Guest permissions and the allowed message formatting.
- Typefaces, spacing and type scale (see [design.md](design.md)).
- `apps/core` 100% branch coverage gate: add a separate coverage run for it once it has code.
