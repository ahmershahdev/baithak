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

- Mentions: `@handle` and `@channel` parsed in `apps/core/mentions.py`, kept only for people
  who can read the channel, stored on each message and recomputed on edit. Guests can't use
  `@channel`. The web app highlights confirmed mentions, marks messages that mention you, and
  the composer suggests people after `@` (arrow keys, Enter or Tab, Escape). The unread badge
  now uses the `unread` token.

- Fixed: the "Reconnecting" banner every few seconds. redis-py 8 reads time out at 5 s, the
  same as channels_redis's blocking wait, so idle sockets crashed; the channel layer's Redis
  socket timeout is now 30 s (#30).
- Dropdowns (role on members and invitations, channel visibility) are a themed listbox
  (`components/Select.tsx`) instead of native selects, whose open list ignored the theme.

- Reactions on messages and replies: one emoji each (checked in `apps/core/reactions.py`), up
  to 20 different per message, live through the message's event. Chips show counts and who
  reacted, pressed when one is yours; a React action opens a picker of 16. Vitest's per-test
  timeout is now 15 s: typing tests passed the 5 s default when every core was busy.

- Direct and group messages: conversations are channels of kind `direct` or `group`, opened
  (found or started) through `.../channels/conversations/`, readable only by their people. The
  sidebar has a Direct messages section titled by the other people's names, and `/w/<slug>/dm`
  picks one person or up to eight.
- Fixed: signing in from an invitation link sometimes landed on home. The signed-out guard sent
  people to `/` while the page sent them to `next`; both now go to `next`.

- Typing indicator and online status: a Redis sorted set per workspace with a 60 s lapse,
  kept alive by pings; first socket in and last out are announced to the workspace. Typing
  notices go over the socket, at most every 3 s per person and place, shown for 5 s. Presence
  dots on members, direct messages and the conversation header; "Bilal is typing" under the
  channel and thread. M3 is complete.

- M3 released as `v0.3.0`, milestone closed.
- M4 started: file and image uploads. Files are sniffed by content (images, PDF, zip/Office,
  text; 25 MB), kept under `FILES_ROOT` outside anything served, sent with messages and replies
  by id, and downloaded through 12-hour signed links that also check the channel. Celery makes
  WebP previews. The composer attaches by button, paste or drop; messages show images and file
  cards. New dependency: Pillow 13.0.0.

- Search: messages and file names through MySQL FULLTEXT, always through `readable_channels`,
  every word as a prefix, newest first with a cursor, filters for channel, person and day. A
  search box tops the sidebar; `/w/<slug>/search` has filters, Messages and Files tabs,
  highlighted words and links into the channel or thread. Issues join search in M5.

- In-app notifications: a row per recipient for mentions, direct and group messages and
  `@channel`, cleared by reading the channel, live through the socket, only from channels the
  person can still read. A Notifications link with an unread count in the sidebar, and a page
  with Mark all read. Assigned issues join in M5.

- Email notifications: Celery beat mails mentions and direct messages left unread for 10
  minutes, one digest per person, skipping quiet hours (in their time zone), people online in
  that workspace and channels they can no longer read. `/w/<slug>/me` has the settings (email
  on or off, quiet hours, time zone), linked as Settings next to Sign out.

- Load check: `python manage.py load_check` opens N real sockets in an invented workspace and
  times delivery from send to arrival. Numbers in `docs/architecture.md`. Found and fixed: redis-py
  8 caps a pool at 100 connections and raised when 500 sockets closed at once (channel layer pool
  now 2000).

- Online status fixed for crowds: join and leave announcements are batched per workspace,
  about one message a second (`presence_changes`), instead of one per person to everyone. The
  load check now also checks every client's online list: 500 of 500 right with 500 online.

- M5 started: projects and issues. Projects (key like `BAI`, admins manage), labels in the six
  brand hues, issues numbered `BAI-1` without gaps (project row lock, never deleted), status,
  priority, assignee, due date, labels; all audited. Screens: Projects in the workspace nav, a
  project's issues with Open and Closed, filters and quick add, label editing for admins, and an
  issue page with editable fields. Guests don't see projects.

## Next session

M5, in this order:

1. Board view with columns by status; drag to change status.
2. Create an issue from a message; the issue's discussion is a thread linked both ways.
3. Issue changes posted into the linked channel; issue history in the audit log.
4. Notify people when an issue is assigned to them (the in-app notifications from M4).

## Open questions

- reCAPTCHA sends visitor data to Google; mention it in the privacy notes before launch.

- Decided: an unverified person can sign in but can't create or join a workspace (enforce in the
  workspaces API).
- openapi-typescript declares TypeScript 5 as its peer; `frontend/package.json` overrides it to
  the project's 6.0. Drop the override when it supports 6.

- jsdom is held at 29.x so tests run on Node 22.12; 30 and later need Node 22.22 or 24.15. Lift
  it once the local Node is upgraded.

- Guest permissions and the allowed message formatting.
- Typefaces, spacing and type scale (see [design.md](design.md)).
- `apps/core` 100% branch coverage gate: add a separate coverage run for it once it has code.
