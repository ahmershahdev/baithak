# Project status

Last updated: 2026-11-17. Update at the end of every work session.

## Where we are

M1 in progress. The backend skeleton is on `feat/backend-skeleton`: Django 5.2 with `dev`, `test`
and `prod` settings, ASGI through Channels and Daphne, a Celery app, a custom `accounts.User`
(email unique) in the first migration, and `/health/` checking MySQL and Redis (503 when either
fails). `compose.yaml` runs MySQL 8.4, Redis, the backend and one worker. pytest runs against the
Compose MySQL (coverage gate 90%, now 100%), and Ruff and mypy (strict, django-stubs) pass.
Dependencies are pinned in `backend/pyproject.toml` with `uv.lock`.

The web app skeleton is on `feat/frontend-skeleton` (PR based on the backend branch): Vite 8,
React 19, TypeScript 6 (strict), Tailwind 4 with only the semantic color tokens in the theme,
TanStack Query, Vitest and ESLint (strict type-checked). The one page shows whether the backend,
database and Redis answer. `npm run dev` at the root starts the Compose stack, waits for it to be
healthy and runs Vite, which proxies `/api`, `/ws`, `/admin` and `/health` to the backend.

## Next session

1. Merge PR #2, then retarget the frontend PR to `main`.
2. Add the `backend` (MySQL and Redis service containers, Ruff, mypy, pytest), `frontend`
   (typecheck, lint, format check, Vitest, build, `npm run contrast`) and `codeql` CI jobs, then
   make them required checks in the "Protect main" ruleset (`.github/rulesets/protect-main.json`
   and the repository settings).
3. Dependabot entries for `uv`, npm and Docker.
4. Accounts: sign up, sign in, password reset, email verification (adds DRF and drf-spectacular).

## Open questions

- jsdom is held at 29.x so tests run on Node 22.12; 30 and later need Node 22.22 or 24.15. Lift
  it once the local Node is upgraded.

- Presence design (see [architecture.md](architecture.md)).
- Guest permissions and the allowed message formatting.
- Typefaces, spacing and type scale (see [design.md](design.md)).
- `apps/core` 100% branch coverage gate: add a separate coverage run for it once it has code.
