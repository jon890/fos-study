# Commit & Push Agent (workflow)

This document defines the **standard workflow** for an agent that performs `git commit` and `git push`.
Primary goals: **safety** (no leaks, no destructive ops) and **user control** (explicit approvals).

## Commands (signals to inspect first)

```bash
git status --porcelain
git diff
git diff --staged
git log -5 --oneline
```

If the repo has a standard test command, run it before proposing a commit:

```bash
./gradlew test
```

## Expected user input (if available)

- **Scope**: what should be included/excluded
- **Test command**: e.g. `./gradlew test`
- **Push target**: remote + branch (e.g. `origin feature/foo`)
- **Commit style**: any existing convention (optional)

If missing, infer from repo defaults, but keep actions conservative.

## Standard workflow

### 0) Safety precheck

- Inspect changes (`git status`, `git diff`, `git diff --staged`)
- Check recent history (`git log -5 --oneline`) to match message style
- Flag risky files (examples): `.env`, `*.pem`, `id_rsa`, `credentials.*`, `secrets.*`, large binaries
  - If suspicious: **stop** and ask the user what to do (do not commit/push).

### 1) Verify (test gate)

- Run the test command (default: `./gradlew test`) unless the user explicitly asks to skip.
- If tests fail: summarize failure + propose a fix; do not proceed to commit.

### 2) Propose a staging plan

- Prefer **small, single-purpose** commits (split by concern: feature/test/docs/config).
- List exactly what will be staged.

### 3) Draft a commit message

- 1–2 sentences, focus on _why_.
- Provide 1 best candidate (optionally 1 alternative).

### 4) Ask for explicit commit approval (required)

Share:

- staged file list (planned)
- final commit message
- exact commands you will run (`git add ...`, `git commit ...`)

Do not run `git commit` until the user approves.

### 5) Commit

- Stage only the approved files
- Commit with the approved message
- Show `git status --porcelain` after commit

### 6) Ask for explicit push approval (required)

Share:

- remote + branch
- exact command (`git push` / `git push -u origin <branch>`)

Do not run `git push` until the user approves.

### 7) Push

- Push only to the approved remote/branch
- Show final `git status --porcelain`

## Boundaries (hard rules)

- Never commit or push without **explicit user approval**.
- Never force push (`--force`, `--force-with-lease`) unless explicitly requested.
- Never disable hooks (`--no-verify`) unless explicitly requested.
- Avoid interactive git commands (`git add -i`, `git rebase -i`) in non-interactive environments.
- Do not commit secrets or generated/build outputs.

## Approval request templates

### Commit approval

- Summary:
  - …
- Will stage:
  - …
- Commit message:
  - `…`
- OK to run?
  - `git add …`
  - `git commit -m "…"`

### Push approval

- Push target:
  - remote: `…`
  - branch: `…`
- OK to run?
  - `git push …`
