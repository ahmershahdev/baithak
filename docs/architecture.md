# Architecture (planned)

This is the design before any code. Change it in the same pull request that changes the code.

## Parts

```
React web app  ──REST──>  Django + DRF (ASGI)  ──>  MySQL 8.4 (all workspaces, one schema)
      │                         │              ──>  Redis (channel layer, presence, cache)
      └──WebSocket──>  Channels consumers  ──group send──>  every open tab in the channel
                                │
                                v
                          Celery workers  ──>  emails, previews, webhook deliveries, search
```

The web app reads and writes through the REST API. The WebSocket carries live events (new,
edited and deleted messages, reactions, typing, presence, read markers) and the client sends only
typing and read markers over it. Long work runs in Celery, never inside a request or a consumer.

## Apps

| App | Owns |
|---|---|
| `accounts` | users, sign-in, email verification, profile, notification settings |
| `workspaces` | workspaces, members, roles, invitations, audit log |
| `chat` | channels, channel members, messages, threads, reactions, read markers, consumers |
| `files` | uploads, previews, signed links |
| `search` | FULLTEXT queries over messages, files and issues, filtered by access |
| `issues` | projects, issues, labels, boards, links to threads |
| `integrations` | GitHub and incoming webhooks, delivery log |
| `notifications` | in-app and email notifications, quiet hours |
| `core` | pure logic: permission checks, mention parsing, unread counting, ordering |

## Data model (first draft)

```
workspace         id, name, slug, created_by
member            workspace_id, user_id, role (owner, admin, member, guest), joined_at
audit_event       workspace_id, user_id, action, model, object_id, changes (JSON), at

channel           workspace_id, name, kind (public, private, direct, group), topic, archived_at, last_seq, last_event
channel_member    channel_id, user_id, last_read_seq, muted
message           channel_id, seq, event, author_id, thread_root_id, body, client_id, edited_at, deleted_at, created_at
reaction          message_id, user_id, emoji
attachment        workspace_id, message_id, uploader_id, name, content_type, size, storage_key

project           workspace_id, key, name, next_number
issue             project_id, number, title, status, priority, assignee_id, due, thread_message_id
label / issue_label
webhook           workspace_id, channel_id, kind (github, incoming), secret, repo
webhook_delivery  webhook_id, received_at, event, status, error
notification      user_id, kind, object_id, read_at
```

`message (channel_id, seq)` is unique: `seq` comes from `channel.last_seq`, taken under
`select_for_update` in the same transaction as the insert, so every client sees one order.

Each channel also has `last_event`, bumped (under the same lock) by every send, edit and delete
and stored on the message as `event`. `seq` is a message's place in the channel and never
changes; `event` is the last change to it. Unread counts use `seq`; catching up after a
reconnect asks for `?after_event=N`, which returns new, edited and deleted messages in the order
they changed, so nothing that happened while the socket was down is missed.

## Sending a message

1. The REST call checks access through `apps/core`, then in one transaction locks the channel row,
   takes the next `seq`, saves the message and its mentions.
2. After the commit (`transaction.on_commit`), the message is sent to the channel's Channels
   group; every connected member's consumer forwards it.
3. A client that sees a gap in `seq` (or reconnects) asks the API for messages after its last
   `seq`. The socket speeds things up; the database is the truth.
4. Mentions and direct messages create notifications in Celery; email goes out only if the person
   hasn't read them after a delay and isn't in quiet hours.

## The socket

One WebSocket per open workspace tab, `ws/workspaces/<slug>/`, authenticated by the session
cookie and checked against `ALLOWED_HOSTS` for Origin. A non-member is closed with 4404, a
signed-out visitor with 4401. On connect the consumer joins the group of every channel
`readable_channels` allows (`chat.channel.<id>`) and the person's own group (`chat.user.<id>`).

| Server sends | When |
|---|---|
| `{"type": "subscribed", "channels": [...]}` | on connect, and whenever access changes |
| `{"type": "message", "channel", "event", "message"}` | a message was sent, edited or deleted |
| `{"type": "channel", "channel", "data"}` | a channel was renamed, given a topic, archived |
| `{"type": "pong"}` | answer to `{"type": "ping"}` |

Joining, leaving, being added, a role change or removal sends `chat.access` to the person's
group; each of their sockets works out its channels again and drops the ones it may no longer
read (or closes with 4404 if they left the workspace). Messages are only ever sent through the
REST API, so they are saved before anyone hears them.

## The web app's side

`frontend/src/chat/timeline.ts` keeps each open channel as `{messages, lastEvent, hasMore}`. A
live event is applied only if it is `lastEvent + 1`; an older one is ignored, and a skipped
number means the socket missed something, so the tab asks for `?after_event=lastEvent` instead
of guessing. Messages are merged by `seq`, and the copy with the newer `event` wins, so a late
page can't undo an edit that already arrived. After a reconnect (exponential backoff from 1 s to
30 s with jitter; 4401 and 4404 are final), every open channel catches up the same way. Sends
carry a `client_id`; the message shows as "Sending" at once and is replaced by the stored copy,
whichever comes first, the API's answer or the live event, and a retry reuses the id.

## Unread counts

Each `channel_member` keeps `last_read_seq`. Unread = `channel.last_seq - last_read_seq` (minus
deleted messages counted by a query only when shown). A read marker sent from one device is
broadcast to the person's other connections so every device agrees.

## Decisions

| Decision | Why |
|---|---|
| Django + DRF + Channels | One codebase for REST and WebSockets; the same stack as Karobar and HolidayOps |
| Saved first, then broadcast, with a per-channel `seq` | Gives one order and lets a client find and fill gaps after a reconnect |
| Redis channel layer, one group per channel | Fan-out without a database query per receiver |
| MySQL FULLTEXT before a search engine | Enough for a small team's history and one less service to run; revisit if it's too slow |
| One permission function for REST, sockets, search and notifications | A private message must not leak through a second code path |
| Soft delete for messages | Threads, reply counts and sequences stay intact; the text is removed |
| Signed, expiring file links | Files are never public URLs |
| Daphne as the ASGI server | Comes with Channels and makes `runserver` serve ASGI in development, so dev and prod run the same server |
| Custom user model from the first migration | Django can't swap the user model after tables exist |
| uv with exact pins and `uv.lock` | One lock file for the image and CI; installs are fast and repeatable |
| Vite dev server proxies the API and sockets | The browser sees one origin in development as in production, so session cookies and CSRF work the same way |
| TypeScript 6.0, not 7 | typescript-eslint supports TypeScript below 6.1; move when it does |
| Session cookies with CSRF, no tokens in the browser | The web app is same-origin; an HttpOnly session cookie can't be read by injected script, and DRF and Channels both understand it |
| CSRF enforced on anonymous auth endpoints too | DRF checks CSRF only for signed-in requests; without it a hostile page could sign a visitor into another account |
| Sign in with email; `username` is the @handle | Email is what people remember; the handle (lowercase, 2 to 30 of `a-z 0-9 . _ -`) is what mentions match |
| Sign-up and password reset answer the same for known and unknown emails | The API can't be used to find out who has an account; the owner of a taken email gets a mail instead |
| Email links carry `uid` and a token built from the account's state | Verification and reset links stop working once used, with no token table; they expire after a day |
| Email through Resend's SMTP relay | Django's own SMTP backend, so no SDK dependency; the API key is the SMTP password, and without one development prints mail to the worker log |
| Celery email tasks take a user id, not a token | No usable secret passes through the broker |
| `backend/openapi.yaml` and `frontend/src/api/schema.d.ts` are committed and CI checks both | API changes show up in review, and the web app can't drift from the API |
| openapi-fetch for API calls | Every request and response is typed from `schema.d.ts`, so an API change breaks the frontend build instead of a page |
| React Router in declarative mode | Few routes so far and data is loaded through TanStack Query, so the framework and data-loader modes add nothing yet |
| Email links confirm on a click, not on page load | Mail scanners open links, and the verification link works only once |
| Role rules in `apps/core/roles.py`, compared by rank | Owner > admin > member > guest; nobody acts on or grants a rank above their own; the last owner can't step down or leave. Plain functions, so every rule is one table of test cases |
| Membership changes lock the workspace row | Two owners demoting each other at once can't leave a workspace without an owner |
| `WorkspaceScopedManager.for_workspace()` on every workspace-owned model | One way to read workspace rows, so a query can't forget its workspace |
| `tests/test_access.py` lists every workspace endpoint and fails on an unlisted one | Each new endpoint is checked for 404 to outsiders and to unknown slugs without anyone remembering to add it |
| Audit rows written in the same transaction as the change, with `{field: [old, new]}` | The log can't say something happened that was rolled back; unchanged saves write nothing |
| Member lists don't show emails | Handles are public inside a workspace; emails are not |
| Argon2id password hashing, PBKDF2 kept second | Argon2id is memory-hard; PBKDF2 stays only so older hashes verify and are rehashed on the next sign-in. No bcrypt: there are no bcrypt hashes to verify |
| reCAPTCHA v3 on every anonymous auth form, v2 checkbox only when v3 doubts | Most people never see a challenge. Empty keys turn it off locally. If Google is unreachable the request goes through, since the throttles still apply and blocking every sign-in is worse |
| Honeypot field `website` on anonymous forms | A filled honeypot gets the normal answer and nothing happens, so bots learn nothing |
| Per-account sign-in limit (5 failures in 15 minutes) next to the per-IP throttle | Stops slow guessing spread over many IPs. Counted under a hash of the email |
| `NUM_PROXIES` 0 locally, 1 in production | DRF otherwise trusts a client-sent `X-Forwarded-For`, which lets anyone dodge the IP throttle |
| API responses carry `default-src 'none'` CSP and `no-store` | JSON never needs to load or run anything; the web app's own CSP is set where it is served |
| reCAPTCHA site keys come from `GET /api/v1/auth/config/` | One `.env` at the root for everything; site keys are public by design |
| Web app CSP as a meta tag in the build, sources not a nonce | The built app has no inline scripts and is static files, so a per-request nonce adds nothing; only our files and Google's reCAPTCHA may run. `frame-ancestors` has to come from the serving proxy as a header |
| zxcvbn-ts with the common dictionary only, loaded on first keystroke | The English word list is another 1.2 MB for little gain; the strength checker never loads on pages without a new-password field |
| Invitation tokens made in the worker, stored as SHA-256 | Like the email links, no token goes through the broker, and a leaked database can't be used to join workspaces |
| Accepting needs the invited email address | A forwarded link is useless to anyone else; the link coming to that inbox also confirms the address |
| Re-inviting replaces the pending invitation | Only the newest link works, so an old forwarded email can't be used |
| `invite` throttle, 30 per hour per person | Stops anyone using Baithak to send email to strangers in bulk |
| Role rules mirrored in `frontend/src/roles.ts` | The screens only offer what the API allows; the API still decides and its refusal is shown |
| Return paths kept in sessionStorage, only same-site paths | An invitation survives sign-up and the confirmation email in the same tab; `//host` and full URLs are dropped so the link can't redirect elsewhere |
| `<meta name="referrer" content="same-origin">` on the web app | Invitation, reset and verification links carry one-time tokens that must not leak to other sites |
| Channel rules in `apps/core/channels.py`; the list query is checked against them | `can_read` decides one channel; `readable_channels` writes the same rule as SQL for lists, and a test compares the two for every role, kind and membership so they can't drift |
| Private channels are closed to admins who aren't in them | Membership, not rank, opens a private conversation; admins can still archive it once added |
| Guests see only channels they were added to | Guests are for outside collaborators; they don't browse the workspace |
| `#general` made with every workspace, joined by every non-guest | People land somewhere to talk on day one |
| Channels addressed by id in the API | Names can be renamed; ids never change |
| `client_id` on sends, unique per channel and author | A send retried after a dropped connection returns the stored message instead of a second copy |
| Messages are not audited, except an admin deleting someone else's | Content keeps its own trail (`edited_at`, `deleted_at`); moderation is a change to the workspace and is audited |
| `post` throttle, 120 sends per minute per person | Stops a stuck client or a script flooding a channel; reading history is never limited |
| Lockout ladder on the account, shared by sign-in and reset codes | 3 wrong attempts lock for 1 hour, 3 more for 4 hours, then a week of suspension, then a ban only an admin lifts (Django admin, "Unlock"). Stored on the user so it survives restarts; the owner is emailed at each step. Unknown emails get the same answers from a cache so locks don't reveal who has an account |
| Password reset by a 6-digit code, 10 minutes, one use, three tries | Stored as an HMAC with the secret key, not a plain hash, since a million codes are easy to brute-force; a new code cancels the old one; wrong codes climb the same ladder |
| Password rules in `apps/core/passwords.py`: 12 to 128 characters, 2 lower, 2 upper, 2 digits, 1 symbol | Enforced by the API; the web app shows the same rules as a checklist |
| Handles checked against `apps/core/handles.py` | Reserved names, and hate or abuse found after folding look-alikes (4 as a or e, 1 as i or l), separators and doubled letters. Words that hide inside ordinary names (grape, crisis, islamabad) are left out on purpose |
| Live email and handle availability on sign-up, throttled to 30 a minute | It does let anyone test whether an email has an account, which sign-up itself still never reveals, so the throttle is the guard |
| `GET /auth/me/` answers 204 when signed out | Being signed out is an answer, not an error, and browsers stop logging a failed request on every page |
| reCAPTCHA v2 checkbox shown on anonymous forms from the start, v3 scoring alongside | People expected to see the check; a ticked box passes, otherwise v3 decides |
| Contact form stored, then emailed to support@ahmershah.dev with Reply-To | The message survives a mail outage and can be read in the admin |
| English only, no i18n library | One language keeps M1 smaller; strings stay in components until a second language is planned |

## Open questions

- Presence at scale: per-connection keys with expiry in Redis, or a heartbeat set per workspace.
- Whether guests can start direct messages, and which channels they can be added to.
- Message formatting: a small Markdown subset rendered on the client, and which parts are allowed.
- Whether HolidayOps working days feed quiet hours and issue due dates.
