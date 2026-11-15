# Contributing

Baithak is in its planning stage. Issues and ideas are welcome; for code, please open an issue
first so we can agree on the approach. Questions go to
[Discussions](https://github.com/ahmershahdev/baithak/discussions).

## Pull requests

- One change per pull request, into `main`, squash-merged.
- Branch names: `feat/...`, `fix/...`, `docs/...`, `chore/...`.
- Tests and linters must pass. Logic in `backend/apps/core` needs 100% branch coverage.
- New endpoints and WebSocket events need an access test (a channel you can't see is `404`).
- Never put real messages, files, tokens or personal data in issues, tests or seed data.
- Read [AGENTS.md](AGENTS.md) for the code rules and [docs/](docs/) for the design.
