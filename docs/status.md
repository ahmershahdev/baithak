# Project status

Last updated: 2026-11-17. Update at the end of every work session.

## Where we are

Planning. The repository, roadmap, architecture draft, rulesets and GitHub milestones are set up.
Color palette and light/dark tokens are in `frontend/src/styles/tokens.css` with a WCAG contrast
check (see [design.md](design.md)). The interface is English only; Urdu and right to left are out of
scope. No app code yet. Next: M1 (platform skeleton), see
[roadmap.md](roadmap.md).

## Next session

1. M1: Django project with settings per environment and ASGI (Channels), Docker Compose with
   MySQL 8.4, Redis and one Celery worker, pytest, Ruff, mypy; Vite + React + TypeScript app.
2. Add the `backend`, `frontend` and `codeql` CI jobs, then make them required checks in the
   "Protect main" ruleset (`.github/rulesets/protect-main.json` and the repository settings).
   The `frontend` job runs `node frontend/scripts/check-contrast.mjs`.
3. Import `tokens.css` in the Vite app and map the semantic tokens into the Tailwind theme.

## Open questions

- Presence design (see [architecture.md](architecture.md)).
- Guest permissions and the allowed message formatting.
- Typefaces, spacing and type scale (see [design.md](design.md)).
