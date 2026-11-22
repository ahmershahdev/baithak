# Architecture

How Baithak is built and why. Change it in the same pull request that changes the code.

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
pings and typing notices over it; read markers go through the REST API. Long work runs in
Celery, never inside a request or a consumer.

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

## Data model

```
user              email (unique), username (handle), display_name, email_verified_at,
                  lockout (failed_attempts, lock_level, locked_until, banned_at),
                  notify_by_email, quiet_start, quiet_end, time_zone
workspace         id, name, slug, created_by
member            workspace_id, user_id, role (owner, admin, member, guest), joined_at
audit_event       workspace_id, actor_id, action, model, object_id, changes (JSON), at

channel           workspace_id, name, kind (public, private, direct, group), topic, archived_at, last_seq, last_event
channel_member    channel_id, user_id, last_read_seq
message           channel_id, seq (null for a reply kept in its thread), event, author_id, parent_id,
                  thread_seq, also_in_channel, reply_count, last_reply_at, body, client_id,
                  mentions (users), mentions_channel, kind (message, activity), edited_at,
                  deleted_at, created_at
reaction          message_id, user_id, emoji (one per person and emoji)
attachment        workspace_id, channel_id, message_id (null until sent), uploader_id, name,
                  content_type, size, storage_key, preview_key, width, height

project           workspace_id, key (unique per workspace), name, description, next_number, archived_at
issue             workspace_id, project_id, number (unique per project), title, description, status,
                  priority, assignee_id, due, labels, created_by, closed_at, message_id (unique)
label             workspace_id, project_id, name, color (one of the six brand hues)
webhook           workspace_id, channel_id, kind (github, incoming), repo (github), name
                  (incoming), token (github: as in the URL; incoming: its SHA-256),
                  secret (github HMAC key), created_by
webhook_delivery  workspace_id, webhook_id, event, external_id, text (until done), status
                  (pending, posted, ignored, failed), detail, attempts, message_id,
                  received_at, finished_at
notification      user_id, kind, channel_id and message_id, or issue_id; actor_id, read_at, emailed_at
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

## Direct and group messages

A conversation is a channel of kind `direct` (two people) or `group` (three to nine), so
messages, threads, unread counts, mentions, reactions and live events work in it unchanged.
`POST .../channels/conversations/` with the other people's ids opens it: the channel name is a
key made from the sorted ids (`~3-7-12`, `apps/core/conversations.py`), so the same people
always get the same conversation, and "~" can't appear in a channel name a person picks.
Opening it again brings back anyone who left. `can_read` treats it like a private channel
(members only, admins included); it has no name, topic or archive to manage, and nobody can be
added, which starts a new one instead. Channels list a conversation's `people` for its title.
The audit log records that one was started, with its kind and size, not who is in it.

## Threads

A reply is a message row with `parent` set; threads are one level deep. Replies are numbered
`thread_seq` inside their thread (`reply_count` on the parent is that counter, deleted replies
included) and live under `.../messages/{seq}/replies/{thread_seq}/`. A reply kept in its thread
takes no channel `seq`, so it doesn't appear in channel history or change unread counts; "also
send to channel" gives it a `seq` too, and it shows in both places as one row. Every reply takes
the channel's next `event`, and the parent then takes one more with its new `reply_count` and
`last_reply_at`, all under the channel lock. So threads need no events or catch-up of their
own: a client catching up by event gets the replies and the new counts, and the web app copies
each channel message into any open thread (`routeMessages` in `frontend/src/api/chat.ts`).

## Mentions

`apps/core/mentions.py` finds `@handle` and `@channel` in a body: not after a word character,
`@` or `.` (so email addresses don't count), and a trailing `.`, `_` or `-` is read as the end
of the sentence. On every send and edit, `apps/chat/mentions.py` keeps only workspace members
who can read the channel (the one `can_read` rule), so a mention can't reveal a private channel,
and `@channel` counts only from someone who isn't a guest. The result is stored on the message
(`mentions`, `mentions_channel`) for notifications in M4; deleting a message clears it. The web
app highlights only what the server confirmed, and the composer offers people after `@`: the
channel's members for a private channel, the workspace's non-guests for a public one.

## Reactions

A reaction is one row per person and emoji. `apps/core/reactions.py` accepts exactly one
emoji (pictographs, flags, keycaps, skin tones, ZWJ and tag sequences; no text), lets only
people who can post react, never to a deleted message, and caps a message at 20 different
emoji (anyone can still join one already there). Adding or taking back a reaction gives the
message a new channel event under the channel lock, so it reaches sockets and catch-up like an
edit, and the message is sent with its reactions grouped by emoji in first-used order.
Deleting a message removes its reactions. Reactions are user data, so they are not audited.
The picker's emoji are code point escapes in `frontend/src/chat/reactions.ts`.

## Presence and typing

Online status is a Redis sorted set per workspace (`presence:<workspace id>`). Each open socket
is an entry `<user id>:<connection>` scored by when it lapses: now + 60 s on connect and on
every ping (the web app pings every 25 s). A person is online while any entry is alive, so a
second tab closing doesn't take them offline and a crashed tab drops off on its own. Each
socket also joins a workspace group, and every new socket gets the list (`presence`). A
person's first socket coming or last one going is not sent at once: each server process
gathers a workspace's changes for a second and sends them as one `presence_changes` message.
One by one, N people arriving together meant N x N messages, and the channel layer drops
whatever is past a socket's queue of 100, so most were lost and online dots went wrong; the
load check showed it. A tab
that crashes is not announced; others see it on their next connect. Rules in
`apps/core/presence.py`, the Redis side in `apps/chat/presence.py`.

Typing is not stored. The client sends `{"type": "typing", "channel", "thread"}` at most every
3 s while typing; the consumer drops it unless the person is in the channel (and it isn't
archived) and it is 3 s since their last notice for that place, then relays it to the
channel's group. Other tabs show it for 5 s, and clear it when that person's message arrives.

## Files

A file is uploaded on its own (`POST .../channels/{id}/files/`, multipart, members who can post,
60 an hour) and then sent by id with a message or reply (`attachments`, up to 10). Until then it
belongs to its uploader alone; sending takes it under the channel lock and only if it is still
unsent, theirs and in that channel, so two sends can't share one. `apps/core/files.py` judges
the type from the first 4 KB of the file, never from the name or the browser's claim: PNG, JPEG,
GIF, WebP, PDF, zip (Office files are zip) and UTF-8 text, up to 25 MB. SVG is refused and HTML
is just text, so nothing uploaded can run script here. Names lose folders and control
characters.

Files live under `FILES_ROOT` (default `backend/var/files`, ignored by git; a volume in
production), which nothing serves. They are read back only through
`/api/v1/workspaces/{slug}/files/{token}/`: the token is signed (Django `signing`) with the file
and version and works for 12 hours, and the view also requires workspace membership and
`can_read` on the file's channel, so leaving a private channel takes its files away too.
Responses carry `nosniff` and a sandboxing CSP; only images are shown inline, everything else
downloads. Celery makes a WebP preview (720 px, upright, metadata dropped) of each image, skipping
anything over 40 million pixels, then gives the message a new event so open tabs get the
preview. Deleting a message deletes its files after the commit. Uploads are not audited, like
messages; deleting someone else's message still is.

## Search

`GET .../search/messages/` and `.../search/files/` use MySQL FULLTEXT indexes on
`chat_message.body` and `files_attachment.name` (raw SQL migrations; Django has no FULLTEXT index
for MySQL). Every query starts from `readable_channels`, so nothing in a channel or conversation
the person can't open is ever found, admins included. `apps/core/search.py` keeps only word
characters from the input and drops words InnoDB never indexes (under 3 letters, its default
stopwords), then requires every word as a prefix (`+deploy* +notes*`, bound as a parameter of a
`MATCH ... AGAINST ... IN BOOLEAN MODE` expression). Results are newest first, 20 a page, with a
`before_id` cursor, and can be narrowed by channel, author and day. Deleted messages and files
not yet sent are never found. InnoDB adds rows to a FULLTEXT index at commit, so search tests use
real transactions.

`.../search/issues/` matches one FULLTEXT index over `issues_issue (title, description)` (MATCH
must name exactly the index's columns). It follows the projects rule, not `readable_channels`:
guests get 404. The author filter is who opened the issue, and the channel filter means "opened
from a message in that channel", only for a channel the person can read.

## Notifications

Sending a message (and editing it, for people newly named) creates one `notification` per
recipient, with the strongest reason (`apps/core/notifications.py`): named with `@handle`, then
in a direct or group conversation, then `@channel`. Mentions were already limited to people who
can read the channel; conversation and `@channel` recipients are channel members. Authors are
never told about their own messages, and nobody is told twice about one message. Reading a
channel past a message marks its notifications read (the read marker and posting both do), on
every device; replies kept in a thread are cleared from the list or by opening them. Every
change sends `notifications` to the person's sockets, which refetch. The list only shows
notifications from channels the person can still read. Deleting a message deletes its
notifications. These rows also drive the email notifications.

Assigning an issue to someone else creates an `assigned` notification about the issue (no
channel or message), naming who assigned it; assigning yourself or saving without a change tells
nobody (`assignee_to_tell`). If the issue moves to someone else before the first assignee reads
theirs, that unread notification is deleted. They show while the person can see projects, so
someone made a guest stops seeing them; opening one (or Mark all read) clears it. They are not
emailed.

Celery beat runs `email_unread` every 5 minutes. A mention or direct message (not `@channel`)
still unread after 10 minutes and not yet emailed is mailed to a confirmed address, one email
per person for everything waiting, unless the person turned emails off, is in their quiet hours
(start and end times in their own time zone, which may cross midnight;
`apps/core/notifications.py`), is online in that workspace (presence), or can no longer read the
channel. Notifications are claimed (`emailed_at`) before the mail goes out so two runs can't
both send, and handed back if sending fails so the retry sends them. Settings live on the
account (`/api/v1/auth/notifications/`), the same in every workspace. Development runs beat
inside the one worker (`--beat`); production runs one separate beat process.

## Load check

`python manage.py load_check --clients 500` (dev only: makes an invented "load-check"
workspace; `--cleanup` removes it) opens one real WebSocket per user against a running server,
waits for join announcements to drain, posts messages the normal way and times each from send
until every client has it. Measured 2026-11-22 on the development stack (Windows Docker, Daphne
through `runserver`, the client in the same container), 500 clients, 20 messages:

| Run | Connected | Online lists right | Deliveries | p50 | p95 | max |
|---|---|---|---|---|---|---|
| Before batching join announcements | 500 of 500, 60 s | not checked (most announcements dropped) | 10000 of 10000 | 784 ms | 1447 ms | 1499 ms |
| Pub/sub layer, before batching | 457 of 500, 136 s | not checked | 9140 of 9140 | 517 ms | 1443 ms | 1537 ms |
| Batched announcements (in use) | 500 of 500, 57 s | 500 of 500 | 10000 of 10000 | 1215 ms | 1849 ms | 3357 ms |
| Pub/sub layer, batched | 500 of 500, 41 s | 500 of 500 | 10000 of 10000 | 2631 ms | 5872 ms | 6396 ms |

Every message reached every connected client, and with batching every client ends up with the
right online list. Runs on this machine vary a lot from one to the next, so the delivery times
are an order of magnitude, not a comparison. Most of the time is fan-out: the default layer
stores a group message once per socket and the server pops them one Redis round trip at a time;
pub/sub publishes once per process. Connecting is limited by per-socket setup (session, user and
channel queries on Django's single database thread, presence in Redis) and by join
announcements, which grow with the square of the crowd. These are development numbers; rerun on
the production setup.

## Issues

Projects belong to a workspace and are for members and up; guests, who only have direct and
group messages, get 404 like outsiders. Admins and owners create, rename and archive projects and keep
their labels; members open and change issues; an archived project is read only
(`apps/core/issues.py`). An issue is `KEY-number`: the number comes from `project.next_number`,
taken under a lock on the project row in the same transaction that saves the issue, and issues
are never deleted (they are canceled), so numbers have no gaps; a 4-thread race test checks it.
Done and canceled are closed and set `closed_at`; reopening clears it. Assignees must be members
of the workspace who can see projects; labels must belong to the issue's project. Every project,
label and issue change is audited with what changed (an issue's description only as "changed",
so the log doesn't copy it).

The board is a column per status, each fetched with `order=priority` (most pressing first, up
to 100, with `total` so a long column says how many more are in the list). Dropping a card on
another column changes its status: the card moves at once, goes back if the API refuses, and
the columns are fetched again either way. Dragging uses the browser's own drag and drop, which
needs a mouse, so every card also has a status menu for the keyboard and phones.

An issue can be opened from a message (`from_message` on create): a channel message, not a reply
and not deleted, at most one issue each (`issue.message_id` is unique, so a race loses with
400). Reading the message goes through `channel_access`, so a message the person can't read is
404. That message's thread is the issue's discussion. Both ends show the link: the message
carries `issue` (only the ref, project and number; it goes out on the channel's socket group, so
everyone in it gets the ref, but only project readers get the title or a way in), and the issue
carries `thread` (channel and seq), null for readers who can't read that channel. Opening the
issue gives the message a new event, so open sockets and catch-up see the link. The issue page embeds the
thread with its composer.

What happens to such an issue is said in that thread, as replies of kind `activity` written in
the name of the person who did it: "opened BAI-7: title" when it is opened, then one line per
change ("BAI-7: moved it to Done, set priority to high", phrased by `describe` in
`apps/core/issues.py` from the audit diff). Status changes also go to the channel, so they count
as unread there; everything else stays in the thread. Activity lines are not read for mentions,
notify nobody and can't be edited (their author or an admin can still delete one). An archived
channel takes no posts, so there the message only gets a new event. Issues not opened from a
message post nowhere.

An issue's history is its audit rows (`.../issues/{n}/history/`, oldest first, the latest 200),
readable by anyone who can see the issue, each turned into the same phrases.

## GitHub

An admin connects a repository (`owner/name`) to a channel that isn't archived on the
workspace Settings page (`.../integrations/webhooks/`, admins only, audited). The answer
carries the payload URL (`/api/v1/hooks/github/<token>/`) and a generated secret, shown
only then, to paste into GitHub's webhook settings. Each connection has its own secret, so
one leak touches one repository. The secret is stored as is, since checking an HMAC needs
the key.

A delivery is looked up by its token (unknown: 404), then its `X-Hub-Signature-256` is
checked against the raw body in constant time before anything is parsed (wrong: 401;
`apps/core/github.py`). The view has no session authentication, so no CSRF, and a
`hooks` throttle of 300 a minute per address. `ping` answers 200. Pull requests (opened,
reopened, marked ready, merged, closed) and issues (opened, closed, reopened) from the
connected repository are queued to become one message each (202, see Webhook
deliveries); everything else answers 202 and posts nothing. GitHub's
`X-GitHub-Delivery` is the message's `client_id`, so a redelivery is stored once.

Those messages are kind `integration`: no author, `sender_name` "GitHub", never read for
mentions, notify nobody, and nobody can edit them. They end with the item's link, which
must start with `https://github.com/`; the web app shows those links as links in app
messages only, with an App tag next to the name.

## Incoming webhooks

An admin makes one for a channel with a name ("Deploy bot"); the answer carries its URL
(`/api/v1/hooks/incoming/<token>/`), shown only then. The URL is the only proof, so only
the token's SHA-256 is stored (`apps/core/webhooks.py`): a database leak gives no working
URL, and a plain hash is enough because the token is random, not a password. To change
the URL, remove the webhook and make another.

A call posts `{"text": "..."}` (up to 4000 characters), answered 202, and is queued to
become a kind `integration` message under the webhook's name, like GitHub's (no mentions, no notifications, no links
but GitHub's). Unknown URL: 404; archived channel: 409. Each webhook allows 30 calls a
minute counted by webhook, not by address, so a leaked URL called from many machines
still can't flood its channel (`PerWebhookThrottle`).

## Webhook deliveries

Every delivery that passes its check (GitHub's signature, an incoming webhook's URL)
gets a `webhook_delivery` row; unsigned calls don't, so nobody can fill the log without
the secret. One with nothing to post is finished at once, with why (`Connected.`,
`Another repository.`, `Not JSON.`, `No usable text.`). One to post is saved as pending
with its text, and `deliver` is queued after commit (`queue` in `apps/integrations/tasks.py`).

The task posts it and marks it posted, linking the message. Any error is written to
`detail` and retried after 30 s, 1, 2, 4 and 8 minutes (at most an hour; six tries in
all, `apps/core/webhooks.py`), then marked failed. A pending row survives a crash, and
the post's `client_id` is fixed per delivery, so a retry after a post that did commit
doesn't post twice; a channel archived meanwhile ends it as ignored. Only pending rows
are acted on, so a duplicated task does nothing. The text is cleared once done.

Admins see a webhook's latest 50 deliveries on Settings
(`.../webhooks/{id}/deliveries/`). Celery beat deletes finished ones after 30 days.

## Demo data

`python manage.py seed_demo --password ...` makes two invented teams, Chai and Code (a
software studio with a client guest) and Monsoon Press (a newsroom with a freelance guest), each
guest talking to their team in a group conversation,
from `apps/workspaces/demo_content.py`: about 120 days of channel messages in office hours,
threads, mentions, reactions and a project of issues each, every third one raised from a
message. It goes through the app's own services (posting, issues), then backdates rows, so
sequence numbers, threads and unread counts are real; the owner is left a few unread
messages. People sign in as handle@slug.example; their email notifications are off and
`.example` is a reserved domain, so nothing is ever mailed. A second run refuses unless
given `--reset`, which deletes the two workspaces and their people first. The full run
takes about five minutes (`--days` makes it shorter).

## Unread counts

Each `channel_member` keeps `last_read_seq`, the newest message the person has read. Unread =
`channel.last_seq - last_read_seq` minus the deleted messages after the marker (rules in
`apps/core/unread.py`; the channel list counts the deleted ones in one subquery). The marker only
moves forward: `POST .../channels/{id}/read/` with a `seq` updates the row only where the stored
marker is lower, so two devices reporting at once can't move it back. Posting moves the author's
marker to their own message, and joining or being added starts it at the channel's `last_seq`, so
old history is not unread. Every move is sent to the person's user group as a `read` event, so
all their devices agree. Someone reading a public channel they are not in has no marker.

The web app counts live: a new message from someone else past the marker adds one, deleting
one takes it off, and the list fetched after a reconnect replaces the count. An open channel is
reported read while the tab is visible and scrolled to the bottom. The "New" line is placed
when the channel opens and stays there while the marker moves past it.

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
| Default Redis channel layer kept after the load check | Both layers deliver everything once join announcements are batched, and pub/sub showed no steady gain on the development machine; measure again on the production setup |
| Pillow for image previews | Decoding and resizing images safely needs a real image library; it is the standard one, with decompression-bomb limits |
| Read markers are not in the audit log | They are one person's place in a channel, not workspace data, and they change on every read |
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
| Guests use direct and group messages only | Guests are outside collaborators. They can't be added to any channel, public or private, and `can_read` refuses them one even if a row is left over (`apps/core/channels.can_be_in`). Becoming a guest removes someone from every channel, with an audit row each, and keeps their conversations; a guest made a member joins the default channels. To work in channels, an admin makes them a member |
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
| Account deletion keeps the person's posts, anonymised | `POST /auth/delete-account/` with the password. The user row is deleted, so memberships, reactions and notifications cascade and messages, files and issues keep their rows with no author (shown as "Deleted account"); threads and issues still read. Workspaces where they are the only member go with them, files and all. The last owner of a workspace with other people is refused (409, with the list) until they hand it over: `apps/core/roles.on_account_deletion`. Each workspace left gets a `member.remove` audit row with `reason: account deleted` |
| English only, no i18n library | One language keeps M1 smaller; strings stay in components until a second language is planned |

## Open questions

- Message formatting: a small Markdown subset rendered on the client, and which parts are allowed.
- Whether HolidayOps working days feed quiet hours and issue due dates.
