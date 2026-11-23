# Project status

Last updated: 2026-11-23. Update at the end of every work session.

## Where we are

Pre-release **`v0.6.0`**. Milestones M1 to M6 are done and released; M7 (docs and launch) is in
progress, with its last two items on hold.

| Milestone | State | Release |
|---|---|---|
| M1. Platform skeleton | Done | `v0.1.0` |
| M2. Channels and live messages | Done | `v0.2.0` |
| M3. Threads, direct messages and presence | Done | `v0.3.0` |
| M4. Files, search and notifications | Done | `v0.4.0` |
| M5. Issue tracker | Done | `v0.5.0` |
| M6. Integrations | Done | `v0.6.0` |
| M7. Docs and launch | In progress | `v1.0.0` at launch |

`main` is green: `backend`, `frontend`, three CodeQL jobs and SonarCloud, all required by the
"Protect main" ruleset. No open pull requests.

## M7 so far

- **Demo data** (#56): `manage.py seed_demo` makes two invented teams, Chai and Code and
  Monsoon Press, with about 120 days of conversations, threads, reactions and issues.
- **README** (#57): what Baithak does, demo data steps and five screenshots taken by
  `npm run screenshots` (Playwright, signed in with a session made in the backend container).
  New dependency: `@playwright/test` 1.65.1, also meant for the end-to-end tests.
- **Sidebar fix** (#58): the signed-in name is no longer cut to one letter (Settings and Sign out
  moved under it), and the workspace nav no longer shrinks and hides Settings and Audit log.
- **Account deletion** (#60): Settings has Delete your account, confirmed with the password. The
  user row goes; messages, files and issues stay with no author and show as "Deleted account".
  Workspaces with nobody else are deleted with their files; the last owner of a shared workspace
  must hand it over first (`apps/core/roles.on_account_deletion`). Authorless messages are never
  grouped, and two different apps' messages no longer merge.
- **Privacy page** (#59): `/privacy`, open to everyone and linked from the sign-in screens and
  the sidebar. Covers what is kept, cookies, reCAPTCHA (Google) and Resend, retention, account
  deletion, and an answer to requests within two weeks.
- **Dependencies** (#45 to #48): Vitest 5.1.1, user-event 14.6.13, TanStack Query 5.108.0,
  React Router 8.5.2, jest-dom 8.0.0 and mysqlclient 2.3.2.
- **Guests use direct messages only**: a guest can't be added to any channel and is taken out of
  every channel on becoming one (a migration clears existing rows); conversations stay. The
  sidebar and channel browser show guests direct messages only. The demo guests now talk to
  their teams in group conversations.
- **Message formatting**: Discord-style Markdown (bold, italic, underline, strike, spoilers,
  inline code and code blocks, quotes, lists, headings, links), parsed on the client into React
  elements so no user text becomes HTML. Handles inside code no longer notify anyone. The
  composer's hint shows the syntax on hover.
- **Channel redesign**: the channel fills the page; a header with members and channel search;
  day dividers; icon message actions; hover times on grouped messages; a formatting bar and
  growing text box in the composer; a "jump to latest" pill with a count of new messages.
- **Privacy page rewrite**: a reading layout with a breadcrumb and a table of contents; a short
  summary; tables for what is kept, cookies and storage, and how long things are kept; who else
  sees data; how it is protected (planned protections named as planned, not live); rights,
  children and changes. Contact form messages, which are stored, are now listed. The contact
  page has a breadcrumb too.
- **File safety**: every upload is scanned before anyone can open it, on its own Celery queue:
  full-file checks (images decode, PDFs without scripts or launch actions, zips without
  passwords, macros or bomb ratios, UTF-8 text), then ClamAV (new `clamav` container,
  `clamav/clamav:1.5.5`). Refused files lose their bytes and say why in the message; scanning
  fails closed and retries, with a sweeper for stuck files. Files and previews are AES-256-GCM
  at rest in 64 KiB chunks with key rotation (`ENCRYPTION_KEYS`, required in
  production); `manage.py encrypt_files` converts older files. File search shows clean files
  only. New direct dependency: `cryptography` 50.0.2 (already installed through another
  package).
- **Two-step sign-in**: authenticator-app codes (TOTP written in `apps/core`, RFC test
  vectors), each usable once; ten recovery codes, hashed; the key sealed with AES-256-GCM;
  wrong codes on the lockout ladder; emails on every change. Sign-in asks for the code after the
  password; Settings sets it up with a QR code, the key to type in, or an `otpauth://` link.
  New dependency: `uqr` 0.1.3 (no dependencies of its own) for the QR code. The setting
  `FILES_ENCRYPTION_KEYS` is now `ENCRYPTION_KEYS`, as it covers secrets too.
- **Signed-in devices**: Settings lists each device (browser and system, last active, "This
  device") with Sign out, and "Sign out everywhere else". A signed-out device's open tabs lose
  their socket at once. Deactivating an account, a password reset and deleting the account end
  every session and socket.
- **Continue with Google**: on the sign-in and sign-up pages when `GOOGLE_CLIENT_ID` is set.
  OIDC code flow with PKCE, state and nonce; ID tokens checked with `joserfc` (new dependency,
  1.8.0). Accounts link by Google's stable id; a verified address links, an unverified account
  with that address is taken over, otherwise a new account. Skips two-step, not lockout.
- **Docs refresh**: README with the logo, badges and a table of documents; CONTRIBUTING rewritten
  with a code of conduct section; new `CODE_OF_CONDUCT.md`; SECURITY.md with supported versions,
  response times and scope; stale lines fixed in design, architecture, roadmap and this file.

## Next

Before the tests and the deploy, one pull request each, in this order (decided 2026-11-23):

1. Channel redesign (done above).
2. Privacy page rewrite, and breadcrumbs on the privacy and contact pages (done above).
3. File safety (done above). Message text at rest is still to come: InnoDB tablespace
   encryption, set up with the database (see architecture.md, Encryption at rest).
4. Sign-in, in four pull requests: two-step sign-in and signed-in devices (both done above);
   then OIDC, in two parts: Continue with Google (done above), then company SSO per
   workspace; then SAML.
5. Abuse hardening: limits on socket connection floods, contact spam per email address, a
   replay window on webhooks, a review of race conditions.
6. A security review against current OWASP guidance, written up in `docs/`.

Decided: messages are encrypted on the server, not end to end, so search, mentions, email
digests and integrations keep working. Passwords stay Argon2id; adding bcrypt on top would add
no strength.

Then, when the maintainer says go:

1. End-to-end tests with Playwright for the main flows, including two browsers in one channel.
2. Deploy at `baithak.ahmershah.dev` and tag `v1.0.0`. Hosting is not confirmed yet.

Before launch, answer the open questions below. The repository has only `main`; merged
branches are deleted on GitHub.

## Held back on purpose

- Dependabot holds Django at 5.2, Python at 3.12, MySQL at 8.4 and TypeScript at 6.0.
- jsdom is held at 29.x so tests run on Node 22.12; 30 and later need Node 22.22 or 24.15. Lift
  it once the local Node (22.19 now) is upgraded.
- openapi-typescript declares TypeScript 5 as its peer; `frontend/package.json` overrides it to
  6.0. Drop the override when it supports 6.

## Open questions

- A theme picker (light, dark, system) stored per person; today the system setting decides.
- Spacing, radius and type scale tokens (see [design.md](design.md)).
- Whether HolidayOps working days feed quiet hours and issue due dates.

Decided and no longer open: guests use direct and group messages only and can't be added to
any channel; messages use Discord-style formatting; an unverified person can sign in but can't
create or join a workspace; Fraunces and Instrument Sans are the typefaces; `apps/core` has its own 100% branch
coverage gate in CI.

## History

What each milestone delivered. Details and the reasons behind them are in
[architecture.md](architecture.md); the pull requests are on GitHub.

### M1. Platform skeleton (`v0.1.0`)

- Django 5.2 with `dev`, `test` and `prod` settings, ASGI through Channels and Daphne, Celery,
  `/health/` checking MySQL and Redis; Vite, React 19, TypeScript 6 (strict), Tailwind 4 with
  only the semantic tokens; `npm run dev` starts the Compose stack and Vite.
- CI (`backend` with MySQL and Redis services, `frontend`, CodeQL) required on `main`;
  SonarCloud on pull requests; Dependabot for Actions, uv, npm, Docker and Compose.
- Accounts: sign up, sign in by email, verification, password reset; session auth with CSRF on
  anonymous calls too; email from Celery through Resend. Argon2id, reCAPTCHA v3 with a v2
  checkbox, honeypot, CSP and `no-store` on API responses.
- Workspaces, members and roles (rules in `apps/core/roles.py`), invitations by email (7 days,
  single use), the audit log, and the access test that calls every workspace endpoint as an
  outsider. Brand: logo, favicons, Fraunces and Instrument Sans, the sign-in scene.

### M2. Channels and live messages (`v0.2.0`)

- Public and private channels with topics, archive, join, leave and add; `#general` in every
  workspace; private channels are `404` to outsiders.
- Messages with `client_id` against duplicates, edit, delete (row kept, text removed), history
  by `before`, catch-up by `after_event`; `seq` and `event` move under the channel row lock.
- WebSockets with session auth and an Origin check, one group per channel, broadcast after
  commit, subscriptions that follow access without reconnecting. The web app reconnects with
  backoff and every open channel catches up.

### M3. Threads, direct messages and presence (`v0.3.0`)

- Account protection (#26, right after `v0.2.0`): a lockout ladder (1 hour, 4 hours, a week,
  then a ban), 6-digit reset codes, stronger password rules, a handle blocklist with look-alike
  folding, live availability checks, and the contact page.
- Unread counts and read markers that only move forward (`apps/core/unread.py`), the same on
  every device, with a "New" line.
- Threads one level deep with reply counts and "also send to channel"; mentions
  (`apps/core/mentions.py`) with autocomplete; reactions (`apps/core/reactions.py`).
- Direct and group messages as channels of kind `direct` and `group`.
- Typing and online status in Redis with a 60-second lapse; join and leave announcements batched
  per workspace. Fixed: idle sockets dropping every few seconds (Redis socket timeout, #30).

### M4. Files, search and notifications (`v0.4.0`)

- Uploads sniffed by content (25 MB), stored under `FILES_ROOT`, downloaded through 12-hour
  signed links; WebP previews in Celery. New dependency: Pillow 13.0.0.
- Search over messages and file names with MySQL FULLTEXT, always through
  `readable_channels`, with channel, person and day filters.
- In-app notifications, and email digests for unread mentions and direct messages after 10
  minutes, skipping quiet hours and people online.
- Load check (`manage.py load_check`): 500 real sockets in one channel; numbers in
  [architecture.md](architecture.md).

### M5. Issue tracker (`v0.5.0`)

- Projects with keys, labels in the six brand hues, issues numbered without gaps, status,
  priority, assignee and due date, all audited; a board with drag to change status.
- Issues from messages: the message shows the issue's key and the issue page shows its thread
  as the discussion; issue changes are posted as activity lines in that thread.
- Assigned issues notify the assignee; issues are searchable (not for guests).

### M6. Integrations (`v0.6.0`)

- GitHub webhook per repository and channel, verified by signature before reading, posting
  pull request and issue events as "GitHub".
- Incoming webhooks with a secret URL (only its SHA-256 stored), 30 calls a minute each.
- Every delivery logged; posting happens in Celery with up to six tries; logs pruned after 30
  days.
