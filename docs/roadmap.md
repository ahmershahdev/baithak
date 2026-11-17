# Roadmap

Each milestone is a set of small pull requests into `main`. A milestone is done when its
checklist is ticked, CI is green and [status.md](status.md) is updated. Each feature ships with its
screens in the same milestone. Target dates are plans, not deadlines; GSoC, Outreachy and
upstream pull requests come first.

Done for the whole project means: a live demo, a README with setup steps and screenshots, tests
in CI, and seed data.

## M1. Platform skeleton (target 2026-12-06)

- [x] Django project, settings per environment (`dev`, `test`, `prod`), health endpoint
- [x] ASGI with Django Channels, MySQL 8.4, Redis and one Celery worker in Docker Compose (MySQL in
      tests too, never SQLite)
- [x] pytest with coverage and pytest-asyncio, Ruff, mypy (strict); Vite + React + TypeScript app
      with Vitest, ESLint
- [x] GitHub Actions: `backend`, `frontend`, CodeQL; add them as required checks in the ruleset
- [x] Dependabot for Actions, Python, npm and Docker
- [x] Accounts: sign up, sign in, password reset, email verification
- [ ] Workspaces, members, roles (owner, admin, member, guest), invitations
- [ ] Workspace-scoped managers and an access test that runs against every endpoint
- [ ] Audit log for changes to workspaces, members and roles

## M2. Channels and live messages (target 2026-12-27)

- [ ] Public and private channels, channel members, topics, archive
- [ ] One permission check in `apps/core` for reading a channel, used by REST and WebSockets
- [ ] WebSocket connection with session auth; one Channels group per channel
- [ ] Send, edit and delete messages; saved first, then broadcast with a per-channel sequence
- [ ] Message history with cursor pagination; catch-up from the last sequence after a reconnect
- [ ] Reconnect with backoff in the web app; nothing lost or duplicated (test with a dropped socket)

## M3. Threads, direct messages and presence (target 2027-01-17)

- [ ] Threads with reply counts and "also send to channel"
- [ ] Direct and group messages
- [ ] Mentions (`@person`, `@channel`) parsed in `apps/core`, with autocomplete
- [ ] Reactions
- [ ] Typing indicator and online status in Redis, with expiry
- [ ] Unread counts and last-read markers per person and channel, the same on every device

## M4. Files, search and notifications (target 2027-02-07)

- [ ] File and image uploads: type and size checks, signed expiring links, previews in Celery
- [ ] Full-text search (MySQL FULLTEXT) over messages, files and issues, filtered by the
      permission check; filters by channel, person and date
- [ ] In-app notifications for mentions, direct messages and assigned issues
- [ ] Email notifications for unread mentions (Celery), with quiet hours per person
- [ ] Load check: one channel with 500 connected clients, message delivery time measured

## M5. Issue tracker (target 2027-03-07)

- [ ] Projects in a workspace, issues with labels, assignees, priority and due date
- [ ] Issue numbers per project, without gaps
- [ ] Board view with columns by status; drag to change status
- [ ] Create an issue from a message; the issue's discussion is a thread linked both ways
- [ ] Issue changes posted into the linked channel; issue history in the audit log

## M6. Integrations (target 2027-04-04)

- [ ] GitHub webhook: signature verified, pull request and issue events posted into the channel
      that follows the repository
- [ ] Incoming webhooks with a secret URL per channel, rate limited
- [ ] Webhook deliveries logged with their result; failed ones retried by Celery

## M7. Docs and launch (target 2027-05-30)

- [ ] Seed data: two invented teams with a few months of conversations and issues
- [ ] README setup steps and screenshots
- [ ] End-to-end tests with Playwright for the main flows, including two browsers in one channel
- [ ] Deploy at `baithak.ahmershah.dev`; tag `v1.0.0`
