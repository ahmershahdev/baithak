# AGENTS.md

Guide for coding agents and contributors. Short on purpose: details live in `docs/`, read only when
a task needs them. When a decision changes, update the matching doc in the same PR.

Baithak: real-time team chat (workspaces, channels, threads, direct messages, files, search) with a
small issue tracker linked to chat threads and GitHub webhooks, in English.
Owner: Syed Ahmer Shah, <https://ahmershah.dev>, support@ahmershah.dev. Goes live at
`baithak.ahmershah.dev`.

## Read on demand

| Task touches | Read |
|---|---|
| Starting a session | [docs/status.md](docs/status.md) |
| What is done and what is left | [docs/roadmap.md](docs/roadmap.md) |
| Parts, data model, real-time design, every decision | [docs/architecture.md](docs/architecture.md) |
| Colors, themes, anything visual | [docs/design.md](docs/design.md) |

## Stack

Python 3.12, Django 5.2, Django REST Framework, drf-spectacular, Django Channels (ASGI, Daphne or
Uvicorn), Celery, MySQL 8.4 (utf8mb4, InnoDB, FULLTEXT; never SQLite, even in tests), Redis.
React, TypeScript (strict), Vite, Tailwind CSS, TanStack Query. pytest, pytest-asyncio,
factory_boy, Vitest, Playwright. Ruff, mypy (strict), ESLint, Prettier. Docker Compose for dev and
prod.

## Layout

```
backend/config/        settings/{base,dev,test,prod}.py, urls, asgi, routing, celery
backend/apps/core/     pure logic (permissions, unread counting, mention parsing, ordering):
                       no Django imports, 100% branch coverage
backend/apps/{accounts,workspaces,chat,files,search,issues,integrations,notifications}/
backend/tests/         mirrors apps/
frontend/              React app
docs/                  roadmap, architecture, status
```

## Hard rules

- `apps/core` is plain Python; views, consumers, serializers and tasks only call it.
- Every workspace-owned model has `workspace` and is queried through the workspace-scoped manager.
  A channel, message, file or issue the person can't see is `404`, never `403`. Every new
  endpoint and WebSocket event goes into the access tests.
- One permission check, in `apps/core`, decides who can read a channel; the REST API, WebSocket
  consumers, search and notifications all use it.
- Messages are saved before they are broadcast. Each channel has an increasing sequence number;
  clients catch up from their last sequence after a reconnect, never by trusting the socket alone.
- WebSocket consumers never query the database inside a loop per receiver; fan-out goes through
  the Channels Redis layer, one group per channel.
- Edits and deletes keep the message row (`edited_at`, `deleted_at`); the text of a deleted
  message is removed, the row stays so threads and counts don't break.
- Uploaded files are checked by content type and size, stored outside the web root, and served
  through signed, expiring links. Image previews are made in Celery.
- Webhook payloads are verified (GitHub signature) before anything is read from them.
- Every create, update and delete on workspace data, members and roles writes an audit log row.
- Secrets only from environment variables. Never commit `.env`, dumps, keys, tokens or real
  messages. Seed data is invented.
- API changes update the OpenAPI schema and the frontend types in the same PR.
- No new dependency without a reason in the PR. Pin exact versions.
- The maintainer reviews `apps/core` and must be able to explain every line of it.
- No emojis in code, UI text or docs (reactions are user data, not UI text).

## Comments

Default is no comment. Write one only for what the code can't say: why it's done this way, a
protocol or ordering rule with its source, or a trap for the next person. Not: restating the code,
section banners, history, owner-less TODOs, or filler (simply, robust, seamless, ensure, leverage,
comprehensive).

## Workflow

- Branches `feat/...`, `fix/...`, `docs/...`, `chore/...`. `main` takes PRs only, squash-merged.
- Each PR belongs to a milestone and closes its issue when there is one.
- Commit messages: short, imperative, no prefixes.
- Releases: `v0.x` pre-releases until launch, `v1.0.0` at launch; tag the merge commit, then
  `gh release create vX.Y.Z --verify-tag --generate-notes` (add `--prerelease` before 1.0).
- Update `docs/status.md` at the end of every session.
