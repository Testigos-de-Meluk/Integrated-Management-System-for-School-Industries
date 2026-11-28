# Contributing

> **Status: proposal.** The current convention in `CLAUDE.md` is still authoritative:
> work on `feat/first-release`, do not push to `main`, and do not open a PR until the first
> release is ready. This document proposes a lightweight branch/PR workflow for the team;
> it becomes a rule only after the team accepts it.

## Current convention

- Integration branch: `feat/first-release`.
- `main` holds releases and deliverables, not day-to-day code.
- Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- No AI attribution in commits or PR descriptions (`Co-Authored-By: Claude...`,
  "Generated with..." are forbidden).
- Commit only when the task asks for it.
- When a teammate works on Carlos's computer, use that teammate's GitHub identity only for
  that command; see `CLAUDE.md` for the table.

## Proposed branch model

| Branch | Purpose | Lifetime |
|---|---|---|
| `main` | Releases and deliverables only | Permanent |
| `feat/first-release` | Integration branch for the first release | Permanent until release |
| `carlos` | Carlos's personal integration branch; not shared | Until integrated |
| `feat/<topic>` | One feature | Short |
| `fix/<topic>` | One bug | Short |
| `docs/<topic>` | Documentation-only change | Short |

Rules:

1. Branch from `origin/feat/first-release` (or from `carlos` for Carlos's personal work).
2. Keep topic branches small and short-lived.
3. Do not commit directly to `main`.
4. While `feat/first-release` is the integration branch, PRs target it, not `main`.
5. After the first release, the team may switch PRs to `main`.
6. Delete the topic branch after merge.
7. Do not create a permanent `test` branch. Tests run in the PR/CI, not in a branch.
8. `review` branches are not part of this model. Historical branches may be archived or deleted
   after confirming they have no unique commits.

## Workflow

```bash
git fetch origin
git switch -c feat/my-topic origin/feat/first-release
# edit, test, commit
git push -u origin feat/my-topic
```

Open a PR to `feat/first-release`:

- explain what changed and why;
- list the commands run;
- keep the diff focused;
- do not merge with failing tests;
- request one review when possible; if working alone, self-review the diff before merging.

For Carlos's personal branch:

```bash
git switch carlos
git merge origin/feat/first-release
# work, commit
```

When `carlos` is stable, open a PR from `carlos` to `feat/first-release`.

## Tests before PR

Backend:

```bash
docker compose exec backend pytest
```

Frontend, when the change touches UI or types:

```bash
docker compose exec frontend npm run typecheck
docker compose exec frontend npm run build
```

If a command cannot run, say so in the PR; do not mark the task as tested.

## Commits

Follow [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/):
`<type>(<scope>): <description>`.

- Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
- Use `!` or a `BREAKING CHANGE:` footer for incompatible changes.
- One logical change per commit.
- Imperative, English.
- Do not mix generated files, chats, worksets, or PII with code.
- No AI attribution.
- Do not commit secrets, `.env`, raw WhatsApp chats, `mapa-nombres.json` or workset data.

## Releases

- Tag releases as `vMAJOR.MINOR.PATCH` (`v0.1.0` while the project is pre-1.0).
- A release tag points to the commit that was actually delivered.
- Delete or archive merged branches; keep the tag, not a stale branch.

## Review checklist

- [ ] Branch based on `feat/first-release`.
- [ ] Focused diff.
- [ ] Tests run and reported.
- [ ] No secrets, PII or workset data.
- [ ] No direct `main` commit.
- [ ] Conventional commit message.
- [ ] PR links the issue/story when applicable.

## If the proposal is rejected

Keep the current `CLAUDE.md` rule: work on `feat/first-release`, no PR until the first release.
This document is then documentation only.
