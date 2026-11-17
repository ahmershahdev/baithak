# Project status

Last updated: 2026-11-17. Update at the end of every work session.

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

## Next session

1. Accounts API: sign up, sign in, sign out, password reset, email verification. Adds Django REST
   Framework and drf-spectacular, session auth with CSRF, the OpenAPI schema and generated
   frontend types.
2. Workspaces, members, roles (owner, admin, member, guest), invitations; the workspace-scoped
   manager; the audit log.
3. The access test that runs against every endpoint.
4. Sign-in and workspace screens in the web app.

## Open questions

- jsdom is held at 29.x so tests run on Node 22.12; 30 and later need Node 22.22 or 24.15. Lift
  it once the local Node is upgraded.

- Presence design (see [architecture.md](architecture.md)).
- Guest permissions and the allowed message formatting.
- Typefaces, spacing and type scale (see [design.md](design.md)).
- `apps/core` 100% branch coverage gate: add a separate coverage run for it once it has code.
