# Contributing

Thanks for wanting to help. Baithak is a pre-release team chat with an issue tracker, built in
the open by one maintainer. Bug reports, ideas and small fixes are all welcome.

Everyone taking part follows the [code of conduct](#code-of-conduct).

## Ways to help

- **Report a bug.** Open an issue with what you did, what you expected and what happened, plus
  your browser. Never paste real messages, files or tokens.
- **Suggest an idea.** Start a thread in
  [Discussions](https://github.com/ahmershahdev/baithak/discussions) first; ideas that fit the
  [roadmap](docs/roadmap.md) move to issues.
- **Fix something.** For anything bigger than a typo, open or comment on an issue first so we
  agree on the approach before you write code.
- **Security problems** go through [SECURITY.md](SECURITY.md), never a public issue.

## Set up

Follow [Run it locally](README.md#run-it-locally) in the README: Docker with Compose and
Node 22.12 or later, then `npm install` and `npm run dev`. Seed the demo data to have something
to click through.

Read before you start:

- [AGENTS.md](AGENTS.md): the hard rules (workspace scoping, `404` not `403`, messages saved
  before they are broadcast, audit rows, comments) and the layout of the code
- [docs/architecture.md](docs/architecture.md): how the parts fit and why
- [docs/design.md](docs/design.md): colors, themes and type, for anything visual

## Pull requests

- One change per pull request, into `main`, squash-merged.
- Branch names: `feat/...`, `fix/...`, `docs/...`, `chore/...`.
- Commit messages and PR titles: short and imperative, no prefixes ("Add reactions to replies").
- Fill in the pull request template, and link the issue it closes.
- Every check must pass: `backend`, `frontend`, CodeQL and SonarCloud. Run them locally first;
  the commands are in the [README](README.md#checks).

## What a change needs

- **Tests.** Logic in `backend/apps/core` is plain Python with 100% branch coverage. New
  endpoints and WebSocket events go into the access test (a channel you can't see is `404`).
- **The API contract.** A change to the API regenerates `backend/openapi.yaml` and
  `frontend/src/api/schema.d.ts` in the same pull request.
- **Docs.** A changed decision updates [docs/architecture.md](docs/architecture.md) or
  [docs/design.md](docs/design.md), and finished roadmap items are ticked.
- **Dependencies.** None added without a reason in the pull request, and every version pinned
  exactly.
- **Data.** Seed and test data are invented. No real messages, files, tokens or personal data.
- **Text.** English, no emojis in code, UI text or docs, and comments only where a reader would
  otherwise get it wrong.

## Code of conduct

Baithak is named after the room where people sit together and talk, and its project spaces
should feel the same: welcoming to people of every background and level of experience. Be kind
and patient, disagree about ideas rather than people, and give feedback that helps. Harassment,
insults and sharing anyone's private information are not tolerated.

The full text, with how to report a problem and what happens next, is in
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report anything that breaks it to
[support@ahmershah.dev](mailto:support@ahmershah.dev) with "Conduct" in the subject.

## License

By contributing, you agree that your contribution is released under the project's
[MIT license](LICENSE).
