# Open gotchas, in full

The evidence behind the one-line gotchas in `SKILL.md`. Each is a failure that
raises no error.

## Why the claim is one call to `campaign-claim take`

A hand-written claim block read `git rev-parse --verify origin/main` in the
sub-issue's checkout. Without that ref, `git rev-parse` exits non-zero and *still
prints* `origin/main`; inside `$(...)` nothing read the exit status, GitHub
answered `422`, and `422` is what this skill teaches means "already claimed" — so
a free sub-issue was abandoned. The script reads the sha from the remote into a
checked variable and needs no second form for a repo-less campaign; its own
comments carry the rest.

## A request that sounds new is usually a follow-up

The gate's survey (`AGENTS.md` § Routing an arriving request) is what this
procedure rests on; skipping it produces a second campaign over the same scope,
and nothing errors — you get two campaign issues that both look right. Two sessions
each running that survey honestly produce the same pair, which is why step 3
surveys a second time.

## You may not be this campaign's session

The binding read in step 1 decides it, before anything else, because a campaign
bound elsewhere is not yours to scaffold, sync or launch into. Nothing after it
asks whose directory this is: every session of a bound campaign shares the one
tree, and the only files in it that belong to a single session are its claim
records. Everything durable is written
as read-then-write against GitHub rather than as "mine because I made it": the
campaign issue body is compared before it is overwritten, the directory may already
exist, and the shared checkout is left on its default branch so a re-run cannot
move it under somebody's delegate.

## Order: the campaign issue before the directory

Filing the campaign issue after scaffolding gives the directory a slug with no ID behind
it and branches named for a number you have not got yet. Order matters here and
nowhere else in the procedure.

## A delegate does not inherit the campaign `AGENTS.md`

It does not pick the file up from its parent directories. It reaches the
delegate as `CLAUDE.local.md`, written into the clone and excluded in that
clone's `.git/info/exclude`; a file in the delegate's own cwd loads because it
is there. This replaced `--append-system-prompt-file <campaign>/AGENTS.md`,
whose text never reached the transcript, so a delegate that received nothing
read exactly like one that received everything and ignored it — which is why
that flag needed a canary and this does not
(`.claude/skills/assuming-role/references/launching.md`, probed 2026-09-04). Where the campaign file does
arrive, it sits beside
the repository's own conventions: adding a principle is free, contradicting one
hands the delegate a conflict it cannot resolve, and it will pick a side without
telling you.

## `gh issue create` without `--parent` succeeds

It returns a URL and a live issue that belongs to no campaign, and only a later
listing that comes back short shows anything is wrong.

## `noclobber` on this machine

This machine's zsh sets `noclobber` and leaves `APPEND_CREATE` unset. Plain `>`
onto a file that exists fails with `file exists`, and plain `>>` onto a file that
does not exist yet fails with `no such file or directory`, which reads like a
missing directory. Write `>|` and `>>|`. Neither failure stops the steps around
it, so a fill that never happened still reports success.

## The campaign directory is invisible to `git status`

`git status` in the base root will never show it. That is the allowlist
working, not a missing file. And never run one git command across `repos/*`:
each is its own repository with its own remote.
