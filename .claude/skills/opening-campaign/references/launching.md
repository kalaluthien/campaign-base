# Launching a delegate, in full

The procedure behind `AGENTS.md` § Delegate launch, which keeps
only the invariants. The launcher is the planner and the delegate is a
worker (`AGENTS.md` § The binding). Everything here is a probed fact about herdr 0.8.2 and the
Claude CLI on this machine, and every item is a failure that raises no error.

## The launch line

Launch in `<campaign>/repos/<repo>/`.

- **The brief is the sub-issue.** Make the launched prompt one short sentence
  naming the issue number and telling the delegate to read the body first. herdr
  types the launch line into the pane, and a terminal silently drops a line past
  1024 bytes — nothing runs and the launch looks like a slow agent — so the
  prompt has to be short either way, and a `gh issue view` is the shortest thing
  that carries a whole brief. Nothing is written, nothing goes stale against the
  issue, and the brief outlives the machine.
- **Put the prompt before any variadic flag.** `--add-dir` and `--allowedTools`
  swallow a trailing prompt as one of their own values, and the run dies on
  "Input must be provided".
- **Pass `--add-dir <base> [<other paths the sub-issue names>]` for a MEMBER
  repository.** Its delegate's cwd is `<campaign>/repos/<repo>/`, and the claim
  script under `<base>/scripts/` lies outside it, so without the flag its first
  claim stops on a permission prompt -- a fourth silent stop beside the three
  below, observed 2026-09-02. Add every source checkout the sub-issue points at
  the same way; the flag is variadic.
- **A delegate in the base's own clone is launched without it.** `<base>/scripts/`
  is already in its own tree, so the flag adds a working directory that buys
  nothing.

  **It does not buy back the duplicated rules #202 measured, and the probe says
  why.** Probed 2026-09-06 in `<campaign>/repos/campaign-base/` with the flag
  absent: the delegate listed its loaded instruction files as
  `~/.claude/CLAUDE.md`, `~/.claude/RTK.md`, then `<base>/CLAUDE.md` and
  `<base>/AGENTS.md`, then the campaign directory's pair, then the clone's own
  pair. The base's rules arrive twice with the flag gone, because the campaign
  directory lives *under* the base root and the outer copy loads as an ancestor
  import. The duplication is the clone's location, not the flag, and removing
  the flag recovers none of the 28,466 duplicated bytes #202 measured on
  2026-09-05 — a figure pinned to that day's `AGENTS.md`, which every edit to it
  moves. The probe's raw output is kept as a comment on #210; it is the
  delegate's own report of what it loaded, not an observation of the loader.
- Choose the session UUID in advance (`--session-id`) so the transcript path is
  known before the agent starts, and `--name` it `campaign-<N>-worker-<n>` per
  § The session name -- a delegate is always the worker role. `--name`
  sets the harness name only; set the herdr pane name too, because the two do not
  propagate. `scripts/campaign-name-session.py` does both.
- Set `CLAUDE_COWORK_MEMORY_PATH_OVERRIDE` to the base's pool. A memory pool
  inside a git-ignored campaign directory dies with the directory.

## Delivering the prompt

**`herdr agent prompt <pane> "<text>"`.** This is the launch's own step and
the delegate's first brief; every LATER assignment to the same session goes
through `scripts/campaign-assign.py`, which adds the idle and compacted
readings a running session needs and a fresh one cannot have. Both are prompts
into the pane, which is the criterion in `AGENTS.md` § The four messages.

A prompt put on the launch line is
word-split: a launch ending with a whole sentence delivered its first word alone,
and the delegate reported it had been given no brief while the launch looked
successful.

This form submits and returns; it does not wait. Every waiting behaviour belongs
to `--wait`, which it does not pass. **If you add `--wait`, add a `--timeout`
above 5000 ms**: without one the settled-state wait is indefinite, and below the
5000 ms stall threshold the more informative `agent_prompt_stalled` comes back as
the less informative `timeout`. **`--wait` does not track turns** — if the agent
is already working, that turn's completion may satisfy the wait, so a driver can
read a previous turn's settling as its own prompt finishing.

| outcome | what it means |
| --- | --- |
| `agent_blocked` | the agent was already at an approval or question dialog. **No input was sent** — the prompt is still yours to deliver once the dialog clears, and clearing it is the person's call. |
| `agent_prompt_stalled` | an accepted submission that started from a non-working state saw nothing move within 5000 ms. The agent has it; something is holding the turn. |
| `timeout` | your `--timeout` elapsed. A long turn reads exactly like this, so read the pane before concluding anything. |

`agent_blocked` is the only one safe to act on immediately, because it is the only
one that says the input never landed.

`agent start` returns once herdr has detected the agent and judged it ready, with
a startup timeout defaulting to 30000 ms (max 300000); an agent blocked during
startup comes back as `agent_not_ready`. It requires an existing pane at an
interactive shell prompt and creates no layout.

## The campaign's principles

**`acquire-repo.sh` writes them**, into `<campaign>/repos/<repo>/CLAUDE.local.md`
and the clone's `.git/info/exclude`, on every checkout it leaves. A file on disk
in the delegate's own cwd, loaded because it is there — so there is nothing to
prove arrived, and no canary.

Written by the script and not by hand since #187: this section said "write them"
and **no command anywhere did**, so a delegate launched by this procedure got no
principles and nothing recorded that — the unobservability the flag below was
abandoned for, back in a new shape. A campaign with no `AGENTS.md` of its own is
a real answer and the script says so rather than skipping silently.

This replaced `--append-system-prompt-file`, whose whole problem was
unobservability: the flag is absent from `claude --help`, the appended text never
reaches the transcript, and a delegate that received nothing looked exactly like
one that received everything and ignored it. The old repair was a token appended
to the injected file, the file deleted, and the delegate asked to recite it.

Probed 2026-09-04 on this machine: a fresh `claude -p` in a temporary git
repository holding a `CLAUDE.local.md` with a token in it answered with that
token. `.gitignore` would not do for the second half: it is tracked, so
excluding a per-launch file there is a commit on the member repository for the
campaign's convenience.

**The second half of that probe was wrong about its own mechanism**, and #187
found it while writing the command. It read `git status --porcelain` as empty
and concluded the `info/exclude` line was doing the work; this machine's global
gitignore holds `*.local.md`, so the file was ignored either way and the probe
could not have told the two apart. Re-measured with the global and system config
emptied (`GIT_CONFIG_GLOBAL=/dev/null`), the exclude does do it — and
`scripts/acquire-repo-test.py` is that measurement, run on every push: delete
the exclude line and its named case reports `?? CLAUDE.local.md`.

The old external-import dialog goes with the flag: `CLAUDE.local.md` in the cwd
is not an ancestor import and raises no question. The row for it stays in the
table below, because a campaign directory *above* a clone still has an
`AGENTS.md` a session may be asked about.

## What silently stops a delegate before it starts

Three things halt a fresh delegate, and from outside all three look exactly like
an agent thinking.

| what | how it shows |
| --- | --- |
| the folder-trust question | the delegate sits on a dialog, having read nothing — and herdr reports it `idle` with `interactive_ready: true`, never `blocked` |
| the external-import question for an ancestor `CLAUDE.md` | declining it silently drops the campaign's principles. **Whether herdr classifies this one as `blocked` at all is unmeasured** -- do not inherit the row above's reading | 
| the first shell-command permission prompt | `--permission-mode acceptEdits` covers edits but not shell, so it stalls on its first `ls`; it appears *after* the opening prompt is accepted, so `agent prompt` has nothing to refuse |

**Read the pane once after every launch.** That is the only check that catches a
delegate which stopped before it began. A usage-limit menu blocks a pane just as
hard and also reports `idle`, so pair the `blocked` watch with a quiet timer and
treat a long quiet as a question to go and look at rather than as progress.

herdr's own Claude integration hook reports session identity, not state
(`pane.report_agent_session` carries no status method), so nothing infers
`working` from anything but the screen.

## The guard

Every `herdr` command that drives a pane, or resolves its target implicitly, is
guarded by `test "${HERDR_ENV:-}" = 1`, and names its target explicitly. Stripped
of `HERDR_*`, `herdr pane current --current` returned the **UI-focused** pane — a
peer session's — where from inside the pane it returned the caller's own.
`herdr agent list` takes no target and needs no guard: listing answers the same
from outside a pane as from inside.

That the guard passes on this base's daily path is a measurement, not a
property: probed over a campaign session, a peer worker session and a freshly
started delegate, each carrying `HERDR_ENV=1` and its own `HERDR_PANE_ID`, while
a process started outside any pane carried neither. The first plain-terminal or
`-p` session here falsifies it, which is what the guard is for.

## The base as a member of its own campaign

The base gets cloned into `<campaign>/repos/campaign-base/`, so one
repository has two checkouts. Read both hazards with one command — **before
launching a delegate, right after merging its pull request, and before the outer
session next edits anything**:

```sh
BASE=$(cd "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")" && pwd -P)
git -C "$BASE" fetch origin -q
git -C "$BASE" rev-list --left-right --count origin/main...HEAD   # want "0	0"
```

Behind means a merged pull request this checkout has not caught up to, and
editing from here can silently revert work that landed: pull, then read zero
again before editing.

**The clone must not be behind *at launch*, which is a different check.** "Do not
clone while the base is ahead" is not sufficient: the remote can move
between the clone and the launch, on a campaign of any length, leaving the
delegate behind with nothing reporting it.

```sh
git -C <campaign>/repos/<repo> fetch origin -q
git -C <campaign>/repos/<repo> rev-list --left-right --count origin/main...HEAD
```

A delegate launched behind obeys an `AGENTS.md` the launching session has already
superseded, and nothing reports it. Pull the clone, then launch. Pushing the
base before cloning is worth doing and is not sufficient.
