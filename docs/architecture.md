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

channel           workspace_id, name, kind (public, private, direct, group), topic, archived_at, last_seq
channel_member    channel_id, user_id, last_read_seq, muted
message           channel_id, seq, author_id, thread_root_id, body, edited_at, deleted_at, created_at
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

## Sending a message

1. The REST call checks access through `apps/core`, then in one transaction locks the channel row,
   takes the next `seq`, saves the message and its mentions.
2. After the commit (`transaction.on_commit`), the message is sent to the channel's Channels
   group; every connected member's consumer forwards it.
3. A client that sees a gap in `seq` (or reconnects) asks the API for messages after its last
   `seq`. The socket speeds things up; the database is the truth.
4. Mentions and direct messages create notifications in Celery; email goes out only if the person
   hasn't read them after a delay and isn't in quiet hours.

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
| English only, no i18n library | One language keeps M1 smaller; strings stay in components until a second language is planned |

## Open questions

- Presence at scale: per-connection keys with expiry in Redis, or a heartbeat set per workspace.
- Whether guests can start direct messages, and which channels they can be added to.
- Message formatting: a small Markdown subset rendered on the client, and which parts are allowed.
- Whether HolidayOps working days feed quiet hours and issue due dates.
