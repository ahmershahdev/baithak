# Baithak

**Team chat and issue tracking in one place, in real time.**

Baithak (بیٹھک, the room where people sit together and talk) is for small teams that keep their
conversations in one app and their work in another, and lose the link between the two. A workspace
has channels, threads and direct messages that update live, and a small issue tracker where every
issue can start from a message and keep its discussion in a thread. GitHub pull request events
arrive in the channel that follows the repository. The app speaks English and Urdu, right to left
where needed.

> Status: planning. Nothing is built yet. See [docs/roadmap.md](docs/roadmap.md) for the
> milestones and [docs/status.md](docs/status.md) for where the work is.

## What it will do

- **Workspaces and channels.** Public and private channels, members and roles, invitations, and
  channel topics.
- **Messages.** Live messages over WebSockets, threads, direct and group messages, mentions,
  reactions, edits and deletes, typing and online status, and unread counts that stay right
  across devices.
- **Files and search.** File and image uploads with previews, and full-text search over messages,
  files and issues, limited to what the person can see.
- **Issues.** Issues with labels, assignees, priorities and due dates, a board per project, and an
  issue created from any message with its discussion kept in a thread.
- **Integrations.** GitHub webhooks posting pull request and issue events into a channel, and
  incoming webhooks for other tools.
- **Notifications.** In-app and email notifications for mentions, direct messages and assigned
  issues, with quiet hours.

## Stack

| Part | Tools |
|---|---|
| API and real time | Python 3.12, Django 5.2, Django REST Framework, drf-spectacular, Django Channels |
| Jobs | Celery (email, previews, webhooks, search indexing) |
| Data | MySQL 8.4 (InnoDB, FULLTEXT search), Redis (channel layer, presence, queue, cache) |
| Web | React, TypeScript (strict), Vite, Tailwind CSS, TanStack Query, i18next |
| Quality | pytest, pytest-asyncio, factory_boy, Vitest, Playwright, Ruff, mypy, ESLint, Prettier, GitHub Actions, CodeQL |
| Run | Docker Compose |

## Why it exists

The hard parts of a chat app are not the message box: they are messages that reach every open tab
in order, unread counts that agree on a phone and a laptop, a reconnect that loses nothing, and
search that never shows a message from a channel you can't open. Baithak is built around those
rules, with tests for each.

## Documentation

- [docs/roadmap.md](docs/roadmap.md): milestones M1 to M7 and what "done" means
- [docs/architecture.md](docs/architecture.md): parts, data model, real-time design and decisions
- [docs/status.md](docs/status.md): current state, updated every session
- [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md)

## Related

- [HolidayOps](https://github.com/ahmershahdev/holidayops): business-day calendars for countries
  and companies.
- [MarketClock](https://github.com/ahmershahdev/marketclock): trading days and settlement dates
  for stock exchanges.
- [OfflineShelf](https://github.com/ahmershahdev/offlineshelf): Wikipedia reading lists for
  offline use.
- [Karobar ERP](https://github.com/ahmershahdev/karobar-erp): stock, sales, accounts and payroll
  for small businesses.

## License

[MIT](LICENSE).
