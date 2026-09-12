# Herdr and Claude CLI facts

Probed facts about herdr and the Claude CLI on this machine, merged from the
machine-wide and campaign-base memory pools. `.claude/skills/herdr/SKILL.md`
(taken from `herdr --skill`) is the authority on the happy path; this file is
only where that path breaks, or what it does not state at all. `AGENTS.md`
§ Delegate launch and `.claude/skills/opening-campaign/references/launching.md`
own the launch *procedure*; this file holds what they do not. Every fact
carries the version and date it was probed against; where two probes of the
same fact disagree, both are kept side by side rather than one being chosen.
Herdr moved 0.8.0 → 0.8.2 across the probe dates below (8/12–8/21 vs.
8/28 onward); a fact with no version note was probed against whichever build
was live that day.

## Contents

- **Installing and upgrading** — Homebrew vs. `herdr update`, the Collie
  plugin's two upgrade paths, when a server restart is owed, and what a
  protocol-version bump costs.
- **CLI shape and parsing traps** — exit codes, `--help`, `--json`, the
  `api schema` reader.
- **Launching an agent** — the two-step launch, argument and line-length
  ceilings, env placement, and what corrupts a pane.
- **Naming a session** — the two independent names, how each is set and read,
  and where a rename can go stale.
- **Driving a pane** — sending keys and text, slash commands, dialogs, and
  prompt queuing/concatenation.
- **Reading a pane and its transcript** — what `pane read`/`agent read` can
  and cannot see, their line caps, and reading the JSONL transcript instead.
- **Agent list, liveness, and who is who** — `agent_status` derivation, the
  session-id stamp on a pane, scoping liveness by directory, and focus.
- **The usage-limit menu and other stuck-but-idle states**.
- **The official herdr skill and the Claude integration hook**.
- **What a harness hook can read and inject, and which files load** — hook
  payloads, a hook's process chain, and which instruction files a session loads.

## Installing and upgrading

- Installed via Homebrew — `herdr update` fails with "self-update is disabled
  for Homebrew installs". Upgrade with `brew update && brew upgrade herdr`;
  verify with `herdr --version` (0.8.2 as of 2026-08-30). The brew path is
  re-confirmed at that version; the `herdr update` refusal is not, because
  running it installs.
  **Collie is herdr's only installed plugin here** (id `herdr.collie`, web
  bridge, AltanS/collie) — a request naming "collie" is a herdr-plugin
  request; its own deployment facts are in the `topic-remote-access` memory.
  Two upgrade paths, and they differ in what they leave behind:
  - `herdr plugin action invoke update --plugin herdr.collie` fetches,
    rebuilds and restarts, but leaves the registry on the *install-time* pin,
    so `herdr plugin list` then prints a version that is not running. Watch
    `herdr plugin log --plugin herdr.collie` for the result.
  - `herdr plugin install AltanS/collie --ref v<tag> --yes` replaces the same
    plugin root, keeps the config dir, and *does* re-pin the registry, so
    `plugin list` is truthful again. Restart the bridge afterwards.
  Either way, the version you can always trust is the ctl one:
  the plugin's own `collie-ctl.sh version`, from its `scripts/` directory in
  `~/.config/herdr/plugins/github/herdr.collie-*/` (0.32.0+c345ccd running as
  of 2026-08-21, unchanged when re-read 2026-08-30, installed by the reinstall
  path — `plugin list` agrees with it while nothing has been upgraded since).
  Since Collie 0.32.0 the `update` action follows release tags only inside the
  installed major; crossing a major needs the `update-major` action.

- **Restart the server only when it asks for one.** `herdr status` prints the
  client and server versions side by side plus an `update: restart_needed`
  line: a Homebrew upgrade leaves the running server on the old build and
  flips that to `yes`, and nothing else does. A plugin update never needs one
  — Collie's `update` action rebuilds and restarts its own launchd service
  (`herdr.collie`), and `herdr plugin action list --plugin herdr.collie` shows
  the rest of its controls: `restart` (adopt an already-built change),
  `start`, `stop`, `status`, `version`, `url`, `update`, `push-keys`,
  `push-test`, `uninstall`. A config edit takes `server reload-config` alone.
  When one is genuinely owed, note there is **no `restart` command** —
  `herdr server` carries only `stop`, `reload-config`, `agent-manifests`,
  `update-agent-manifests` and `reload-agent-manifests` (the same five at
  0.8.2, 2026-08-30) — so a restart is `herdr server stop` plus a re-attach
  with `herdr`. Read `agent list` and `$HERDR_ENV` before any stop: the server
  holds every pane, so a stop reaches sessions this one did not start, and a
  session running inside a herdr pane kills itself and cannot report what
  happened next. What survives a stop is unverified — no probe has been run,
  because the machine always had live agents (2026-08-18).

- **Nothing supervises the server, and its `ppid 1` is not launchd.** It
  self-daemonises — `herdr status --json` reports
  `capabilities.detached_server_daemon: true` — and is orphaned to init;
  `launchctl list` holds only `herdr.collie`, the plugin's job, and
  `brew services list` says `none`. So neither `launchctl` nor
  `brew services restart` is the restart: `herdr server stop` plus a
  re-attach is, and nothing brings the server back on its own. (Probed
  2026-09-06, correcting an earlier note here claiming "runs under launchd":
  `ppid 1` is consistent with both a launchd job and an orphaned daemon,
  which is why the wrong reading looked verified — the deciding probe is
  `launchctl list`.) `herdr update --handoff` exists on both versions and
  passes file descriptors to the incoming server with per-pane replay, which
  would preserve panes — untested here, and it installs outside Homebrew, so
  brew keeps believing the old version is installed.

### Upgrading across a protocol bump kills every pane, and there is no way round it (2026-08-30)

`src/protocol/wire.rs` declares `PROTOCOL_VERSION`: 19 at v0.8.0, 20 at v0.8.2.
The number is in no release note and it decides whether an upgrade costs a
restart, so it has to be read per tag before upgrading. That read is now a
script: `just herdr-preflight <tag>` in `~/homeops`, which prints the
running server's protocol, the tag's, and the verdict. Match on the
declaration's `= <n>`, never on the name alone — the `u32` in
`pub const PROTOCOL_VERSION: u32 = 20;` is a number too, so a name-only grep
answers 32 at every tag.

When the numbers differ, upgrading the binary alone is not a safe half-step.
The new client refuses against the old server: `herdr agent list` and
`pane list` both fail, and `src/cli/protocol_guard.rs` says why — "client
protocol N is newer than server protocol M; restart the Herdr server before
using this command". The guard sits in `send_request`, the path nearly every
command takes, so assume `server stop` is refused too. `herdr status` is the
exception and keeps answering, which is what makes the state readable: it
prints `compatible: no` and `restart_needed: yes`.

So a same-protocol upgrade is free and a protocol bump is all-or-nothing.
Decide before running brew, not after — after the upgrade the only exit is
the restart.

**A session inside a pane must not perform the restart itself**: stopping the
server kills the server and its pane processes, so the session dies
mid-command and nobody is left to report the outcome. Do the `brew upgrade`
from inside, hand the restart to a person outside herdr, and give them the
one-line check — `herdr status` reading client and server at the same version
and `compatible: yes`.

**What a restart costs depends on whether the session is in a pane, measured
on the 19 → 20 upgrade.** A session inside a pane comes back with its session
id intact and a new pid, and with a new harness name — all three in-pane
sessions did, verified against subagent artifacts predating the restart. A
session running outside any pane is simply gone. So the session id is the
only identifier that survives, and a record keyed to pid or name cannot be
repaired afterwards. So the flat prediction that a restart loses every
running session was wrong and would overprice every future upgrade, and the
flat opposite is wrong too. What a restart does cost is every pid recorded
anywhere: **a session that records its own pid must rewrite that record after
a restart**, because it survives under a new one while the file still names
the old. Here `runtime/holder` named a pid that no longer existed while its
session was alive and holding the campaign, which reads as an abandoned
campaign to the next session that looks.

## CLI shape and parsing traps

- **Unknown subcommands print help and exit 2** (0.8.2, probed 2026-08-30).
  Through 0.8.0 they exited 0, so a script calling a command from a different
  version looked like it ran; 0.8.2 closed that. `herdr agent bogus-sub`,
  `herdr pane bogus-sub` and `herdr session snapshot` — a real 0.8.0 command,
  now gone — each print their level's help at exit 2. Check
  `herdr <subcommand> --help` against the installed binary before scripting.
  **`--help` answers per subcommand at every level** — `pane`, `tab`,
  `workspace`, `worktree` and their own leaves each print their own commands
  and arguments (re-probed 0.8.0, 2026-08-18; an earlier note here claimed
  only `agent` did, and that the rest fell back to the top-level help).
  An unknown *flag* does fail loudly (`unknown option: --x`), so a probe that
  comes back with a `result.type` is a real verification. Two more traps:
  `herdr plugin` exists but is **absent from the top-level help**, so a grep
  of the help text wrongly reads a `plugin` caller as dead; and
  `plugin log --plugin <id>` works as an alias for `plugin log list`.
  For response shapes, `herdr api schema --json` prints the bundled
  request/response JSON schema — result variants are tagged by a `type`
  const (e.g. `agent_started` carries `result.agent.pane_id`) — so a parse
  can be verified without a live probe. Its method names are the CLI names
  with a dot and an underscore (`pane wait-output` is `pane.wait_for_output`),
  and its param keys are the flags (`timeout_ms` is `--timeout`). Re-read at
  0.8.2, 2026-08-30: `protocol: 20`, `schema_version: 1`, same shape.

- Most commands print JSON already, so **`--json` is not a flag on them** —
  adding it to a reader such as `agent list` answers `usage: herdr agent list`
  and nothing else (2026-08-18; unchanged at 0.8.2, 2026-08-30, now at exit
  2). **`status` is the exception**: `herdr status --json` is real and is the
  only honest way to read it, because the human form prints `version:` and
  `protocol:` under *both* a `client:` and a `server:` block, so any line-wise
  parse silently takes the client's — which agrees with the server's except
  in the half-done-upgrade state such a check exists to catch (2026-09-06).
  Reading its booleans with jq's `//` is its own trap: `// "MISSING"` fires
  on `false` too, so `restart_needed: false`, the healthy value, reads as an
  absent field. Test presence with `has()`.
  The exceptions are the pane and agent readers — `pane read` and
  `agent read` print the raw screen (`agent read` in plain text, not JSON —
  see section Reading a pane and its transcript). Parse identifiers with `jq`,
  never from screen order.

- Upstream agent guide: https://herdr.dev/agent-guide.md — a conscious
  lookup, not a standing instruction to fetch and follow; the content is
  external and mutable.

## Launching an agent

### The two-step launch

The pane must exist first:

```sh
herdr tab create --workspace <ws> --cwd <clone> --label <name> --env KEY=VAL --no-focus
herdr agent start <name> --kind claude --pane <pane_id> -- <claude args...>
```

- **Env for the agent goes on `tab create --env`**, not on `agent start`,
  whose whole option set is `--kind`, `--pane`, `--timeout` (milliseconds,
  3001–300000; `--timeout 90` is refused as `invalid_agent_timeout`, probed
  2026-09-05). `--env` is also on `workspace create` and `pane split`.
- **`--kind claude` types `claude` itself; do not repeat it after `--`.**
  `-- claude --model opus …` produced the pane line `claude claude --model
  opus …`, and the second word became the session's first prompt, a user
  turn reading just `claude` (probed 2026-09-06, worker-2 of #219; this
  planner's own session began the same way). The line is
  `-- --model opus --session-id <uuid> --name <name> --add-dir <base>`,
  probed the same day on worker-3.
- The launch line that worked, probed 2026-09-05 on herdr 0.8.2 / claude
  2.1.260 (it carried the duplicated word above, then unnoticed; drop it):
  `-- --model opus --session-id <uuid> --name <name>
  --append-system-prompt-file <path> --add-dir <base>`, with the memory
  override on `tab create --env`. `--model fable|opus|sonnet` and
  `--effort <level>` both start a session (probed 2026-09-06, three
  launches), so the effort is a launch flag and never a prompt sentence.
  **`--append-system-prompt-file` still works and is still absent from
  `claude --help`** — this repository retired it for `CLAUDE.local.md`
  because nothing on disk records that it arrived, not because it stopped
  working.
- **`claude` does have `-n, --name`** ("Set a display name for this
  session"), which is what makes a delegate addressable under a chosen name.
- Trust and the external-import answer persist **per directory**, so only
  the first launch after a fresh clone pays the dialogs — and **a directory
  rename resets folder trust**, so a launch right after one pays all three
  again.

### Argument validation, line-length ceilings, and what corrupts a pane

- **`agent start` validates the `--` args** and refuses some text with
  `invalid_agent_argument` ("agent arguments cannot be encoded safely for
  the target shell"). **The refused class is exactly Unicode control
  characters** (`char::is_control`, i.e. U+0000–U+001F, U+007F–U+009F) in
  any `--` argument — so a newline, a tab or a CR is refused and nothing
  else is. Quotes (straight and curly), backticks, `$`, `\`, every shell
  metacharacter, NBSP, U+2028/U+2029, Korean and emoji all pass; herdr wraps
  each argument in single quotes (`'` → `'\''`), which is why no
  metacharacter can break out. Length is not herdr's own limit — 900 kB
  passed; the ceiling is the OS `ARG_MAX` (1 MiB here), hit as `E2BIG` in the
  caller. **The real ceiling is far lower and is the terminal's**: `agent
  start` launches by *typing* `<kind> <argv>` into the pane's shell, so the
  whole command line is one typed line, and a shell still in its terminal's
  canonical mode drops a line past `MAX_CANON` — 1024 bytes here — silently.
  Nothing runs, and `agent start` then answers `{"code":"timeout","message":
  "timed out waiting for agent startup"}` after its `--timeout`, which reads
  as a slow agent rather than a lost line; the pane shows the command echoed
  and sitting unexecuted at the prompt, which is how to tell. Whether the
  shell is past its startup is a race, so the same long line travels most of
  the time. Keep the whole typed line under 1024 bytes: hand a long prompt
  over as a file the agent reads. (2026-08-21, eight agent Starts lost this
  way.) Verified 2026-08-12 against herdr 0.8.0 (`src/app/agents.rs:155`,
  `src/platform/macos.rs:51`) and by live probe. **The argument check runs
  *before* the pane lookup**, so a bogus pane id characterizes the class for
  free: `invalid_agent_argument` means refused, `agent_pane_not_found` means
  accepted. (This corrects an earlier note here claiming the opposite
  order.) A freshly split pane's shell needs a moment to reach its prompt —
  `agent start` fails with `agent_pane_busy` until then, so retry.
  **`agent start` takes `--timeout <MS>` — default 30000, max 300000 — and
  the default is the only bound a caller that omits it gets.** A claude
  start measures ~3 s here, with or without a prompt argument, so a 30 s
  `timeout / timed out waiting for agent startup` is an anomaly and not a
  slow launch; time it before widening anything. **herdr does not serialize
  its commands**: a blocking `agent wait` does not delay a concurrent
  `agent list`, and two simultaneous `agent start` calls each finish in the
  single-call time (probed 2026-08-21), so a queue observed in a driver is
  the driver's own lock. **A workspace label is not unique**: two
  `workspace create --label X` calls answer with two workspaces both
  labelled X (probed 2026-08-21), so a driver that looks a label up and
  creates one when none answers owes that pair its own lock. **`root_pane`
  is a pane object, not an id** — take `.result.root_pane.pane_id` on both
  `tab create` and `workspace create`. It is a sibling of `.result.tab`, not
  inside it, so `.result.tab.root_pane` raises `KeyError` (re-probed
  2026-08-28). Handing the object to `agent start --pane` fails
  `agent_pane_not_found` with the whole object echoed in the message, which
  reads like a missing pane rather than a type error (probed 2026-08-28,
  0.8.0). (0.8.0 added the tab to `tab_created`; an earlier note here said to
  read it from `tab list` instead. Verified by live probe, 2026-08-12.)
  **Re-probed at 0.8.2, 2026-08-30**: the `agent start` shape, the
  `--timeout` bounds, `tab create --env` and the absence of any `--env` on
  `agent start` are unchanged, and the no-serialization reading reproduced —
  a blocking `agent wait` took 4.068 s while a concurrent `agent list`
  answered in 0.012 s. `root_pane` is `{"$ref": PaneInfo}` in the bundled
  schema, so the object-not-id trap is still there in writing. The refusal
  class, the `MAX_CANON` drop, the `agent_pane_busy` retry and the
  pane-corrupting retry below were not re-run: each needs an agent started.

- **A second `agent start` aimed at a pane whose first attempt timed out
  corrupts that pane**: the first attempt's line is still sitting in the
  shell, so the retry's text concatenates onto its tail and the shell runs
  the tail as a command (observed `zsh: command not found: ude` from a
  second `... --model opus ...`). The pane is then unusable and the prompt
  that follows lands in a shell, not in claude. Recovery is `herdr tab
  close` and a fresh tab, never another retry on the same pane; a startup
  timeout means abandon the pane (observed 2026-08-28).

- **Send a delegate's opening prompt with `herdr agent prompt <pane>
  "<text>"`, not by typing it into the shell.** A prompt passed on the
  launch line is word-split: a launch ending `... 'Read <path> and carry out
  the brief.' --add-dir <dir>` delivered the single word `Read`, and the
  agent reported it had been given no brief while the launch looked
  successful. This is the same family as the 1024-byte line ceiling and the
  variadic-flag swallow, and it is the quietest of the three (observed
  2026-08-28).

- **`pane run` word-splits its command, so a quoted multi-word argument does
  not survive.** `herdr pane run <pane> <COMMAND>...` takes argv, and the
  shell that typed it already split the quotes away: a launch line ending
  `... 'Read <path> and carry out the brief.' --add-dir <dir>` reached
  `claude` as separate words, and the session received the single word
  `Read` as its whole prompt and reported that no brief was given (observed
  2026-08-28, claude-code 2.1.250). herdr exits 0 and the pane renders the
  full line, so the launch looks successful — same silent-loss shape as
  above, by a different route. **`herdr agent prompt <pane> "<text>"`
  delivers a multi-word sentence intact**, so use it for any prompt, and
  keep `pane run` for single-token commands.

- **`pane send-text` can lose the tail of a long line, silently.** The text
  goes to the pane's terminal, and a terminal still in its shell's line
  discipline discards a line past `MAX_CANON` — 1024 bytes on this machine,
  `MacOSX.sdk/usr/include/sys/syslimits.h:89`, re-read 2026-08-30 — with no
  error anywhere: herdr exits 0 and the pane shows the truncated text as if
  it were all of it (observed 2026-08-12, a 1.4 kB prompt arriving as
  exactly 1024 bytes, cut mid-word). Whether the pane is in that state when
  the text arrives is a race with the session's own startup, and
  `agent start` reporting `interactive_ready` does not settle it, so the
  same send succeeds most of the time. Chunking does not help: the limit
  bounds the accumulated *line*, not the write. Keep typed text well under
  1024 bytes, or hand it to the session another way — `claude` takes an
  initial prompt as a positional argument, which the process reads with no
  terminal in between (verified 1506 bytes intact; it must sit ahead of the
  variadic `--allowedTools`, which would otherwise swallow it as a tool
  name).

- **`tab close` kills every pane in the tab, and an agent that splits its
  own pane puts two agents in one.** A session launching a delegate may
  split beside itself rather than opening a tab, so `agent list` shows two
  names with the *same* `tab_id` — closing by the tab a finished agent
  reports takes the live one with it. Before retiring anyone, read
  `agent list` and confirm the target's `tab_id` belongs to it alone; close
  the pane, not the tab, when it does not. `agent list` is the only place
  the pane-to-tab map is visible, since a tab's LLM-generated title says
  nothing about who is in it (observed 2026-08-28, a campaign session and
  its delegate sharing one tab).

## Naming a session

**A session names itself, on both sides, with no person.** There are two
names and they are different strings that do not propagate to each other, so
a session that wants one name sets it twice (measured 2026-08-30 and
2026-09-06):

| name | set by | read from |
|---|---|---|
| herdr agent name (pane name) | `herdr agent rename <pane> <name>` | `herdr agent list` |
| harness name | `herdr agent prompt "$HERDR_PANE_ID" "/rename <name>"` | `ListAgents`; this is the address `SendMessage` uses |

`.claude/skills/assuming-role/scripts/campaign-name-session.py <pane> <name>` sets both. Unset the herdr
name with `herdr agent rename <pane> --clear`; `rename <pane> ""` is refused
(`invalid_agent_name`, 1–32 chars, lowercase, `-`/`_`).

`/rename` is input to a pane and herdr can put input in a pane, which is what
makes the harness half work — so "only a person can rename a running
session" is false.

**Self-injection works; whether a given call is permitted is a per-session
permission decision, not a property of herdr.** `herdr agent prompt
"$HERDR_PANE_ID" "/rename ..."` drives the caller's own pane. Three readings
on one machine within an hour on 2026-08-30 disagree: refused on one
session, the same call accepted on that session later once the owner had
approved the script wrapping it, and accepted throughout on a peer whose
name was first set exactly that way with nobody typing it. **An earlier note
here said a session cannot rename itself and that this was a tool guard —
that was one refusal generalised, and it is wrong.** Build on neither
outcome: run it, report applied and not applied, confirm with `ListAgents`.
The caller's own rename is the one most likely to need a person.

**The two halves land at different moments, and the claim guard reads the
half that lands first.** `campaign-name-session.py` sets the herdr name
immediately and reports the harness `/rename` as *queued* — a prompt into a
working pane applies when the turn ends: the session runs `/rename` on its
next turn, so `agent prompt` returning is not the rename applying, even for
an `idle` pane — a prompt sent straight after the call merges into the same
input line and the name becomes the rename plus that prompt (seen as
`sdlc-alloy-planner-7`, 2026-09-10). Wait for the echo (below), or for
`ListAgents`, before sending that pane anything else. `check-campaign-claim.py`
resolves the role from `herdr agent list`, so a rename made mid-turn takes
effect on the very next write; there is no need to end the turn or restart.
Observed 2026-09-06: a file write refused as belonging to another campaign
succeeded on the retry immediately after the rename, with the harness half
still queued. Report the rename as sent.

**An address can go stale mid-conversation while the session lives, and the
`[ref]` does not.** Three sends bounced on one machine in one day, the last
one *after* both sessions had adopted self-naming — so naming yourself makes
the current name meaningful, it does not make an address durable. A
`SendMessage` bounced with `No agent named '…' is reachable` against a
session alive at the same `[ref]` under a new name — **address by the
`[ref]` when a name bounces.** When a send fails, the error names the
current holder; `ListAgents` also annotates a recent rename (`says it was
<old> until 41s ago` / "was X until N seconds ago"), which narrows the
window but does not close it. Neither hint reaches anything reading a
*file*, which is why a record keyed to a name cannot be repaired.

**The harness name is in no file on disk** — a `grep -rl` for a live
session's name over `~/.claude/` and `/tmp/cc-socks` finds nothing, and
`ListAgents` is a model tool, not a command, so nothing outside a session
can read it. So no shell script can read it directly, and a design that
wants one thing to read should put the name in the herdr row rather than
join two sources.

**A script outside a session can still see the harness rename LAND, two
ways** (probed 2026-09-10). The CLI prints `Session renamed to: <name>` when
`/rename` runs — the literal is in the shipped binary
(`grep -ao "Session renamed to" $(which claude)`, `/opt/homebrew/bin/claude`)
— so a caller that sent the prompt can poll `herdr agent read <pane>` for
it. That window is short, because `agent read` returns the visible screen
and not scrollback (section Reading a pane and its transcript). The durable half:
`herdr agent list`'s `terminal_title_stripped` carried the harness name on
every named pane and differed from it on the one pane with no herdr name at
all (4 panes, 2026-09-10) — consistent with the CLI setting the title, not
proof of it, so probe before a check depends on it.

**The rename echo has TWO forms**, and a reader that rebuilds the line from
the name deletes the half that matters: `Session renamed to: <name>` and
`Session renamed to: <name> ("<other>" is held by another live session on
this machine)` (both literals in the shipped binary, 2026-09-10). Quote the
line read off the pane. Match it anchored on the RIGHT only — `<n>` is an
unbounded digit run, so a plain substring confirms `-worker-1` off
`-worker-12` — and never on the left, since the CLI prints it inside its own
decoration. For the same reason QUOTE it from the match to the end of the
line: a whitespace strip keeps the `⎿` gutter the terminal draws in front.

The `herdr-name.sh` `UserPromptSubmit` hook that used to AI-title the tab
and pane was **deleted 2026-08-30** (owner decision) as redundant with
self-naming; the hook file and its `settings.json` entry are both gone, and
nothing auto-names a tab now. The older naming strategy it served —
workspace = where, agent = purpose, tab/pane = current work — is retired
with it.

## Driving a pane

- **`send-keys` reports delivery of the keystroke, never its effect — no
  single key is a reliable submit.** `Enter` is swallowed by the selector
  footer a usage-limited session shows; `Return` is better but is also lost
  when it arrives while the pane is still consuming a `send-text` paste —
  the prompt then sits in the composer while `agent_status` reads `idle` (a
  queued prompt sat unsent 12 minutes this way, 2026-08-03). Confirm a
  submit by its effect: the agent leaves `idle`, or the input box reads
  empty. Manual recovery is `Escape` to dismiss any footer, then
  `send-keys <pane> Return` — but never send `Escape` when the earlier
  submit may have landed, because `Escape` interrupts a running turn. A
  driving program resends `Return` alone and polls `agent_status`.
- **Keys go in with `herdr pane send-keys <pane> <Key>`; literal text with
  `herdr pane send-text`.** There is no `herdr pane key` — that spelling
  prints the pane usage banner and sends nothing, which reads like a no-op
  rather than an error. `herdr pane send-keys <pane> down enter` answers
  menus; `esc` is the canonical Escape name (both spellings accepted).
- A pane footer is stale UI, not state. A limit-blocked session kept
  showing "2 shells still running" after its shells were gone — `pgrep`
  found no matching process. Probe the process table before treating a
  footer claim as a running job.
- **A slash command that opens a DIALOG produces no state change, so
  `agent prompt --wait` reports `agent_prompt_stalled` while the command in
  fact ran.** Probed 2026-09-08 with `/remote-control`: the wait failed at
  5000 ms with "status is idle and state_change_seq remained ...", and the
  pane was showing the Remote Control dialog. The failure word is about the
  model turn, not the command — **read the pane before concluding
  anything**, and dismiss the dialog rather than re-sending.
- **`/remote-control` re-connects a session the Claude mobile app shows as
  disconnected**: send it, then `send-keys ... Enter` on the default
  "Continue" row. The dialog's other rows are "Disconnect this session" and
  "Show QR code", so a blind second Enter is not safe — read the pane
  between the two steps. Sleep is what drops the connection; see the
  `topic-macos-power` memory.
- **A slash command sent by `herdr agent prompt <pane> "/compact"` runs as
  the command, not as text** (probed 2026-09-05 on executor-5's own pane,
  sent by that session as the last call of its turn): the pane showed
  `❯ /compact` under "Press up to edit queued messages" while the turn
  finished, then `Compacting conversation… (41s)` with a progress bar. That
  is the mechanism kalaluthien/campaign-base#198 builds on.
- **`herdr agent read --lines` refuses a `working` pane** — `agent_not_idle`,
  "its alternate-screen history can only be captured by scrolling while
  idle" (probed 2026-09-05) — and a session is working for as long as it is
  running, so a self-read through `agent read` is refused by construction.
  `--source visible` reads a working pane but returns only the visible
  screen, not scrollback. **`herdr pane read <own pane> --source
  recent-unwrapped --lines N --format text` is NOT refused** (probed
  2026-09-10 from the working pane itself, #279): it returned the recent
  scrollback of the caller's own pane, its last limit banner included,
  which is what `campaign-limit-reset.py` reads. A peer's read after the
  subject's turn ends is still the one way to read a pane through
  `agent read`. So any reading of a pane's history has an idle check in
  front of it by necessity, not by manners.
- **Prompts sent to a `working` pane queue, and the harness merges every
  queued prompt into one input line** (probed 2026-09-04). Three `/rename`
  prompts to a mid-turn pane landed as one name,
  `campaign-1-executor-3/rename campaign-1-planner-1/rename
  campaign-1-executor-3`. Send one prompt per turn to a working pane, and
  read `ListAgents` before trusting a rename. Filed as
  kalaluthien/campaign-base#169.
- **Two prompts sent back to back concatenate** (probed 2026-09-05 and
  2026-09-07). Two `herdr agent prompt <pane>` calls in one breath — to an
  idle pane, and within one shell command — are pasted into ONE input line
  (`/compactSession limit reset…`, run as an unknown command). Send one
  prompt per pane, and read the pane for its marker before sending the
  next: after a `/compact`, that marker is `Compacted`.
- **The inherited-environment trap**: a subagent shell, or any child of a
  pane session, reports `HERDR_ENV=1` by inheritance, so a "no pane"
  reading taken there is the parent's pane measured twice. Measure a
  natively pane-less process, or say the reading was simulated with `env -u`.

## Reading a pane and its transcript

- A pane read is a lossy record, not a transcript. Both `visible` and
  `recent` return what the emulator still holds, and a pane repaints as its
  agent runs, so output scrolls out for good — the same pane returned 59
  lines and then 11 minutes later. Read a screen for markers that are
  present; absence proves nothing about what the session did. It is also a
  *rendered* screen: a claude session's own output arrives behind its
  bullet glyph and indent (`⏺ WORD: …`), so a matcher anchored on the start
  of the line never fires — re-read at 0.8.2, 2026-08-30, a live pane
  returning `  ⏺ main` and `  ◯ general-purpose …`, both behind their
  glyph. Allow the decoration in front of any marker you match.
  The opposite error is worse: match the *shape* a state draws, never the
  sentence it contains. A session reading a file, a diff or a document that
  quotes your marker prints it on the same screen, so a phrase match fires
  on a pane that is working fine — a driver anchored on a menu's label
  pressed Return into one every poll (2026-08-07). Anchor on what only the
  state draws: the option line's own form, a modal that has replaced the
  composer, the glyph a session's own output carries.

- **`pane read --lines` is capped by the emulator's buffer, not by the
  flag.** `herdr pane read <pane> --source recent-unwrapped --lines N`
  returns at most what the terminal still holds, and that is small: probed
  2026-08-19 on a live claude pane, `--lines 20` gave 19 rows, and `200`,
  `1000` and `5000` all gave the same 61. Omitting `--lines` gives the same
  61. Re-probed at 0.8.2, 2026-08-30: 19 rows at `--lines 20`, and 43 at
  `200`, `1000`, `5000` and omitted, against a 44-row viewport — the
  ceiling is the terminal's, so the number moves with the pane and the rule
  does not. So a reader that misses something the session printed is not
  fixed by asking for more rows — the rows are gone. Read the session's own
  transcript instead (below), which keeps everything.
  `herdr pane read` has **no pattern or context flag** — its whole option
  set is `--source`, `--lines`, `--format`, `--ansi`, `--raw`. Any searching
  happens in the caller. Unchanged at 0.8.2 (2026-08-30), where `--source`
  also takes `detection` and `pane wait-output` carries `--match`/`--regex`
  for a *wait*.

- **`agent read <pane-id>` and `pane read <pane-id>` can answer very
  different lengths for the same window** (2026-09-09). Both take a pane id
  and `--lines N` and both share the same 1000-line cap (measured:
  `--lines 1500`/`3000` both capped at 1000 for both commands, same pane).
  But `agent read` scopes to the *agent's own turn*, which a
  release-then-compact resets, while `pane read` reads the terminal's raw
  scrollback, which compaction does not clear. Live occurrence (NOTE on
  campaign-base#1): `agent read <pane> --lines 1000` right after that
  pane's own `campaign-claim release` had printed a release line and
  compacted answered 62 lines with no release line in them; `pane read` on
  the identical pane and window answered 530+ lines holding both the
  release and the compaction marker. A script reading a pane by id to find
  something printed before its last compaction wants `pane read`, not
  `agent read` (`campaign-base/scripts/campaign-assign.py`, fixed at
  PR #270).
  `agent read` also **prints PLAIN TEXT on stdout, not JSON**, unlike
  `agent list`, `rename` and `prompt`, so a caller that parses herdr's
  output has to keep this one out of the JSON path; it refuses a `working`
  pane, which is what a pane is while it applies a prompt, so a refusal
  there is a not-yet rather than a no (see section Driving a pane).

- **`--lines N` tells you nothing about whether you read the whole
  history**, and an earlier version of this note implied otherwise.
  Measured 2026-09-05, all on this machine:
  - it **caps at 1000 lines** however large `N` is: 900→900, 1000→1000,
    1001→1000, 1200→1000, 1500→1000, 3000→1000, with the large reads
    sharing a tail and differing at the head. Asking past the cap reads no
    further, so a bigger `N` buys nothing and hides that it bought nothing.
  - it returns **fewer lines than both `N` and the history**: one 48-line
    pane answered `--lines 60` with 46, `--lines 48` with 34, and
    `--lines 1..10` with nothing at all. Another pane did return exactly
    `N`. So the behaviour differs per pane and **"the read was shorter than
    the window, therefore that is the whole history" is false.**
  A reader that needs "X is absent from this pane's history" cannot get it
  from here. Treat the absence as unknown and refuse, per the
  `pitfall-campaign-mechanics` memory.

- **A shell command's stdout reaches the pane's text with its middle lines
  intact** at 16 and 40 lines (probed 2026-09-05 with a token on line 8).
  The transcript's `... +N lines` collapse applies further out; where
  exactly is unmeasured, and a session cannot read its own pane to find out.

- **A compacted pane's scrollback holds `Compacted (ctrl+o to see full
  summary)`** under the `❯ /compact` line (probed 2026-09-05). That string
  is the only marker; the `Compacting conversation…` progress line does not
  survive the turn. `scripts/campaign-assign.py` holds it as `MARKER`, and
  reads it by ORDER against the release line rather than by presence — an
  older marker from a previous sub-issue says nothing about now.

- **An idle pane's context size is on screen**: the harness prints
  `new task? /clear to save <K>k tokens` above the prompt once a turn ends
  (read 2026-09-05, e.g. `790.8k` on executor-4). A working pane shows only
  the turn's `↓ Nk tokens`, never the total. `<campaign>/scripts/compact-watch.py`
  reads that line to decide a mid-task `/compact`.

- **`pane read` refuses `--pane` and takes the id positionally** (2026-08-30,
  0.8.2). The pane-addressing flag is not uniform across the CLI, and the
  one command that breaks the pattern is a *reader* — the thing you reach
  for right after a launch, when you are checking whether the agent stalled.

  ```sh
  herdr pane read --pane w40:p15 --lines 30   # unknown option: --pane
  herdr pane read w40:p15 --lines 30          # works
  ```

  `pane split`, `agent prompt` and `agent start` all take `--pane <ID>`. So
  a habit built on those fails exactly once, on the command whose failure
  looks like "the pane is gone" rather than "the flag is wrong" — the error
  names the option, but it arrives while you are already suspecting the
  launch.

  **This contradicts a rule in `AGENTS.md` § Delegate launch**, which says
  to name the target on every pane-addressing command as
  `--pane "$HERDR_PANE_ID"`. True for the driving commands, false for this
  reader. The rule's *intent* holds — never let herdr resolve the target
  implicitly, because outside a pane `--current` returns the UI-focused pane
  rather than the caller's — but the spelling differs per command. Read the
  usage line rather than assuming the flag.

  `pane split` also requires `--direction right|down`; there is no default,
  and omitting it prints the usage line rather than a named error.

  **Settled 2026-09-06**: the bundled 0.8.2 schema declares `pane_created`
  as `{pane, type}`, so the skill's `.result.pane` is right and an earlier
  note here flagging `.result.pane_id` was reading a truncated print. Read
  the whole `result` object once rather than reaching for a path.

- **A `pane read` failure looks exactly like a faded screen.** The CLI
  prints its error as JSON on stdout, so a failed read reaches any
  classifier as text holding none of the markers it looks for, and scores
  the same "no evidence" verdict a finished session's collapsed pane gets.
  Check the read's exit status before trusting any no-marker verdict, and
  give such a verdict a terminal branch rather than mapping it to "keep
  waiting".

### Reading a delegate's transcript

Read progress from the transcript, never from `agent_status` (section Agent list,
liveness, and who is who). The path is
`~/.claude/projects/<cwd with every / and . replaced by ->/<uuid>.jsonl`,
the uuid being the row's `agent_session.value`.

```sh
jq -rn 'first(inputs | select(.type == "user") | .message.content
        | if type == "string" then . else (map(.text // "") | join(" ")) end
        | select(test("^<(local-command|command-name)") | not))' <transcript>
```

**`-n` with `inputs`, never `-s`**: a live session's transcript is being
appended to right now, so slurping fails on the half-written tail and the
live session reads as empty. The wrapper filter is part of the recipe — the
literal first record is often a `<local-command-caveat>` or `<command-name>`
block.

## Agent list, liveness, and who is who

- **A pane can carry the session id running in it, and that is the way off
  the screen.** `pane.report_agent_session` over the unix socket
  (`$HERDR_SOCKET_PATH`, one JSON line per request) stores it, and it reads
  back as `pane.agent_session` → `{source, agent, kind: "id", value}` on
  `pane.get` and in the live snapshot — which at 0.8.2 is
  `herdr api snapshot`, the old `herdr session snapshot` having been
  removed; the read-back shape is unchanged (2026-08-30). The CLI form
  needs the pane id *before* the flags (`herdr pane report-agent-session
  <PANE> --source S --agent claude --agent-session-id <UUID>`); flags first
  answers `unknown option: <value>`. **The ref is write-once per pane**: a
  later report returns `{type: ok}` and changes nothing, from any source,
  and `pane.clear_agent_authority` does not release it — so a `/clear`,
  which forks a new session id inside the same process, leaves the stamp on
  the abandoned transcript. Anything reading it must tolerate that.
  The snapshot publishes panes and agents as **two arrays joined on
  `pane_id`**: the agent row carries `name` (the delegation name), the pane
  row carries `label` (a display title) — they are not the same field, and
  reuse decisions key on `name`.
  A closed pane answers `pane.get` with `pane_not_found`, so the read that
  confirms a close raises on success unless it is caught (0.8.2 answers the
  same code for an unknown id, 2026-08-30).
  Two 0.8.2 surface changes: `pane.clear_agent_authority` now has a CLI
  form, `herdr pane release-agent`, and `pane report-agent-session` gained
  `--session-start-source`. **Still write-once at 0.8.2** (worker-10 of
  campaign-base#227, 2026-09-06, replayed the hook's exact socket path by
  hand on its own pane: report → ok, clear_agent_authority → ok, report →
  ok, value unchanged over three reads). Consequence: whichever session
  stamps a pane first owns its row for the pane's life, and
  `.claude/skills/herdr/scripts/herdr-session-link.py` can only fill an
  empty pane, never repair one — its clear-and-restate tail is two silent
  acks. A nested `claude -p` from a pane's Bash tool passes that hook's
  ancestor walk, so when the pane's own stamp is late the probe run becomes
  the first writer and the pane's session is unreadable by id from then on.
  A lookup keyed on the id then returns NO MATCH, which reads exactly like
  a session herdr never knew rather than like a wrong row — so read the
  row's id before trusting such a lookup, and treat a no-match as a reading
  about herdr rather than about the session (the `pitfall-diagnosis`
  memory).

- **Each `agent list` row's `agent_session.value` is the Claude session
  id** — the same value `$CLAUDE_CODE_SESSION_ID` holds. Probed on four
  live sessions; every row carried it, including one with no `name`. It
  survives both a restart and a rename — and a wrong first writer, for the
  pane's life: the ref is write-once (above), so a row can name a nested
  probe run's id instead of the pane's session, and `role_of` then reads no
  role for that session until the pane is closed. Seen on `w40:p1V`
  (worker-10 of #227, 2026-09-06).
- **`$CLAUDE_CODE_SESSION_ID` and the `--session-id` on the process command
  line differ after a resume, and both are real.** Measured in one
  session: the env held `7496e7c9-…` while `ps -p $PPID -o command` showed
  `--session-id 1387f9c4-…`. `agent list` keys its row on the env one.
- **Read `ListAgents` before naming a pane.** Its first line names *this*
  session; nothing in `herdr agent list` says which row is you, and
  `campaign-name-session.py <pane> <name>` will happily name somebody
  else's. Done once here, and there is no undo that is not a second write
  to another session.
- **The Remote Control host pane is `w40:p14`, herdr-named
  `remote-control`** (owner, 2026-09-05); a fresh one reads as an idle
  unnamed session at the base root. Its pane shows
  `·✔︎· Ready · Capacity: 0/32` rather than a `❯` prompt. A prompt or
  `/rename` sent to it lands nowhere useful. Read the pane before handing
  work to any "idle" unnamed row.

- **`agent list` rows are keyed by directory, which is how you scope
  liveness to a tree.** `herdr agent list` answers
  `{"result": {"agents": [...], "type": "agent_list"}}`. Each row carries
  `cwd` and `foreground_cwd` (the pane's directory), `name` (the
  `claude --name` slug, absent on an unnamed session), `agent_status`,
  `pane_id`, `tab_id`, and `agent_session.value` (the session UUID) — and
  at 0.8.2 also `terminal_title`, `terminal_title_stripped`, `terminal_id`,
  `revision`, `state_change_seq`, `focused`, `workspace_id` and `agent`,
  none of them a subtask, so the argument below is untouched (2026-08-30).
  So the only honest "is anything alive under this directory?" query is a
  prefix match on `cwd`, not a name or title match — an unnamed session has
  no name to match and the terminal title is LLM-generated prose:

  ```sh
  herdr agent list | jq -r --arg tree "$DIR" \
    '.result.agents[] | select(.cwd | startswith($tree))
     | "\(.name // "unnamed")\t\(.agent_status)\t\(.cwd)"'
  ```

  Presence of a row is the liveness signal; `agent_status` is not, since it
  reads the screen and reports a mid-turn pause as `idle`. A row survives
  the agent going quiet, so a tree with rows is held whatever the status
  word says.

- `agent_status` is one of `idle|working|blocked|done|unknown`, derived from
  screen rules — `agent explain <target> --json` shows which rule matched
  and why. It reports the pane, not the task: a session pausing mid-turn
  reads as `idle`, and `done` means one turn ended, not that the delegation
  finished. **`idle` and `done` differ by history, not by screen**: the
  manifest declares no `done` rule at all — still none at manifest
  2026.08.29.1, re-grepped 2026-08-30 — and `agent explain` answers `idle`
  (`live_prompt_box`) for a pane whose `agent list` row says `done` — herdr
  promotes rule-`idle` to `done` only once it has observed that agent
  `working`. The agent name is attached to the pane when `agent start`
  *returns* (~3.1 s), so a session whose whole first turn ends inside that
  window is never observed working and reads `idle` for good. Never read
  `idle` as "took no prompt". **Presence is the reliable signal**:
  `agent list` drops an agent within ~1 s of its claude process dying
  (probed by `kill`, 2026-08-21), so an agent in the list is a live process
  running the argv it was started with.
  The rules are data, not code: a per-agent TOML manifest under
  `~/.local/state/herdr/agent-detection/remote/<agent>.toml`, refreshed
  from upstream and version-stamped (2026.08.29.1 active on 2026-08-30, up
  from 2026.08.19.1; `herdr server agent-manifests` prints which is live),
  holding prioritised rules that each match a named screen region
  (`osc_title`, `osc_progress`, `prompt_box_body`,
  `bottom_non_empty_lines(N)`, `after_last_horizontal_rule`,
  `last_non_empty_above_prompt_box`, `whole_recent`) and declare a state.
  Highest priority wins; `explain` prints the rule id, its region and the
  evidence text. There is no "needs you" state — a permission prompt, a
  confirm form and the dynamic-workflow prompt all resolve to `blocked` —
  at manifest 2026.08.29.1 `live_blocked_form` matches
  `enter to confirm` beside `esc to cancel`, which is 0.8.2's
  confirm-prompt fix as manifest data (2026-08-30).
  **Claude Code's own startup dialogs do not** [resolve to `blocked`], and
  that is a third stopped-but-idle state alongside the usage-limit menu
  (section The usage-limit menu) and the background-shell rules below.
  `agent start --kind claude` returned success with `agent_status: "idle"`
  and `interactive_ready: true` on a pane holding the folder-trust dialog
  (*"Yes, I trust this folder"*), and again on the external-import dialog
  behind it — the session had read nothing either time (2026-08-28, claude
  2.1.250). `agent start`'s contract is that the expected agent was
  detected and is ready for input; it detects the process, not whether the
  process can accept work. So a driver gating on `blocked` never fires, and
  one trusting the return value walks away from a delegate that never
  starts. **Read the pane once after every launch** —
  `agent read <name> --source recent-unwrapped --lines 40` shows the
  dialog plainly. Clearing it is `send-keys <name> down` then
  `send-keys <name> enter`, which worked for both; pre-setting the
  `~/.claude.json` keys avoids it entirely (the `topic-claude-sessions`
  memory, "the trust dialog").
  The terminal title is the strongest signal (priority 1100): Claude Code
  spins a glyph into it while working, so it survives any repaint. At 0.8.2
  every `agent list` and snapshot row carries both `terminal_title`
  (`◐ Claude Code`) and `terminal_title_stripped` (`Claude Code`), so a
  reader no longer strips the spinner itself (2026-08-30).
  **A pane with a live background *shell* still reads `idle`; one with a
  live background *agent* no longer does** (claude.toml 2026.08.29.1,
  re-probed 2026-08-30). `background_shell_working` anchors its line on
  the auto-mode glyph, which vim mode pushes behind `-- INSERT --`, and it
  requires whitespace after the shell count, which sits at end of line —
  the live footer `  -- INSERT -- ⏵⏵ auto mode on · 1 shell` matches
  neither half, and the no-vim form fails the second half alone;
  `agent explain` still reports it `matched: false` against exactly that
  footer. Its sibling `background_agents_working` **does** now fire —
  `matched: true` on `✻ Waiting for 1 background agent to finish` — so the
  earlier reading that *two* rules were dead is retired by the manifest
  refresh, not by anything in 0.8.2 itself. A session that ended its turn
  with a shell still running reads `idle`, and anything that closes on
  `idle` kills the command. Read the footer yourself before retiring a
  pane; the workspace `clean` skill's classifier does (workspace `9267a43`).

- **`scripts/herdr-survey --json` prints one JSON object per line, not an
  array, and its `worktrees` counts `git worktree list` unfiltered — the
  repository's own checkout is included, so a repository with nothing left
  behind reports 1 and never 0.** The field name says worktrees and the
  value means checkouts, so summing it raw reports one phantom leftover per
  repository; subtract one per repository to count linked worktrees. Its
  other counts are what they name: `dirty` is porcelain lines, `unpushed`
  is `@{upstream}..HEAD`. Re-run 2026-08-30: seven objects, one per line,
  every repository with no linked worktree still reporting 1. A repository
  the script does not enumerate yields no row, so a consumer joining on
  repository name gets a missing value rather than a zero — the workspace
  root is that case.

- **Focus is a verb on three nouns, and it moves only the local client's
  view.** `agent focus <name>`, `tab focus <tab id>` and
  `workspace focus <workspace id>` each exist and answer with the object's
  JSON (probed 0.8.0, 2026-08-12). `pane focus` is a different thing — it
  moves to a *neighbouring* pane within a split, not to a pane by id, and
  at 0.8.2 `--direction` is required, so `pane focus <id>` cannot even be
  typed (2026-08-30). Focusing changes what the herdr window on this
  machine shows and nothing else, so it is invisible to anything reading
  over the network. To probe one politely, read `agent list` for the row
  with `focused: true` first, then restore by
  `workspace focus <its workspace>` followed by `tab focus <its tab>` — an
  unnamed pane cannot be restored with `agent focus`.

## The usage-limit menu and other stuck-but-idle states

**A claude session's usage-limit menu blocks the pane forever until
answered — it does not clear itself when the limit resets.** Five sessions
sat on "Stop and wait for limit to reset" for two hours past the reset
(2026-08-07). `send-keys <pane> Return` confirms option 1 (the `Enter` key
name is swallowed there — section Driving a pane). Confirmed *after* the reset
time, the session drops to an idle prompt and does not resume its
interrupted turn — one `send-text "continue"` plus `Return` resumes it
(verified on four sessions). Confirmed *before* the reset, Claude Code is
expected to wait and auto-resume; that half is unverified — design drivers
so it does not matter (poll later, nudge if still idle past reset).
**Superseded for new stops since 2026-08-18**: the machine now sets
`autoContinueAtUsageLimit` (still `true` in `~/.claude/settings.json` on
2026-08-30), so the menu should not appear at all — see the
`topic-claude-usage` memory before typing into any parked pane.
Two more facts a driver needs (verified 2026-08-07/08). The menu is an
overlay carrying **no reset clock at all**, so a screen showing it cannot be
used to time the wait; the message that does name one — `You've hit your
session limit · resets 10:10pm (Asia/Seoul)` — reaches the pane only when
the limit interrupts something that prints it, and it carries a wall time
with no date, so a screen read cold cannot be told from one read a day
late. And `agent_status` for a pane blocked on the menu is `idle` or
`done`, never `blocked` — a driver gating on `blocked` sees nothing.

Both the folder-trust/external-import startup dialogs and the
background-shell footer are the same shape of trap; see section Agent list,
liveness, and who is who for both.

## The official herdr skill and the Claude integration hook (2026-08-28)

**The skill is installed here**, at `.claude/skills/herdr/SKILL.md` (the
vendored skill in this repository, taken from `herdr --skill` and
byte-identical to `herdrdev/herdr@v0.8.2`). It is the authority on the
happy path — pane IDs, `pane split --no-focus`, `agent start`,
`agent prompt --wait`, `--lines` and the read sources, the lifecycle words,
the `agent_not_ready`/`agent_blocked`/`agent_prompt_stalled` returns, and
the `HERDR_ENV=1` guard. **This file is only where that path breaks**, so
nothing here restates it; read the skill first and this file when the
skill's account does not match what the pane does. It is **not** in the
Claude plugin marketplace (`claude-plugins-official` has no herdr entry),
and `herdr.dev/plugins` indexes herdr plugins (`herdr-plugin.toml`), not
skills.

`herdr integration status` shows the Claude hook
(`~/.claude/hooks/herdr-agent-state.sh`). **Installed 2026-08-30, and the
name lies: it reports identity, not state.** `herdr integration install
claude` writes the script and appends one `SessionStart` entry to
`~/.claude/settings.json` (purely additive — existing hooks survived).
Read the script and the hypothesis dies: `case "$action"` accepts only
`session` and exits 0 on anything else, and its one RPC is
`pane.report_agent_session` carrying the session id and transcript path.
There is no status method at all, so herdr still infers working/idle/
blocked from the screen and **every screen-reading workaround stays** —
the `agent_status` misreads above are not removed by installing this. It
also guards on `HERDR_ENV=1`, so it is inert outside a pane.

It duplicates a hand-written `.claude/skills/herdr/scripts/herdr-session-link.py`,
and neither dominates: herdr's fires on `SessionStart` only and sends the
transcript path as well; the local one fires on `SessionStart` **and**
`UserPromptSubmit`, so it re-asserts the link a restart cleared, but sends
no path. Both call the same method, so the later write wins — a partial
write may drop the path the fuller one set. Not yet measured, because the
pane record as `herdr api snapshot` exposes it shows no path field either
way.

## What a harness hook can read and inject, and which files load

Probed 2026-09-06, claude 2.1.261, a temp project whose `.claude/settings.json`
dumped each hook's stdin and echoed a canary (#227 re-plan, worker-9).

- `UserPromptSubmit` stdin: `session_id`, `cwd`, `prompt`, `prompt_id`,
  `permission_mode`, `transcript_path`. Its stdout is injected into the
  model's context (the canary came back verbatim). It fires on a slash
  command too: this pane's `/rename` showed "UserPromptSubmit hook
  success".
- `SessionStart` stdin: `session_id`, `cwd`, `source`. Probed by worker-10
  of #227 (claude 2.1.263, raw lines on #227): `startup`, `resume` (adds
  `context_tokens`, `prompt_cache_likely_expired`), and `compact` after a
  manual `/compact`, preceded by `PreCompact` with `trigger: manual`; the
  session id is unchanged across all of them. A `/compact` on a short
  session answers "Not enough messages to compact." and fires NO
  SessionStart, so a compaction probe needs a long transcript. Auto-compaction
  unprobed; `claude --autocompact <tokens>` (min 100k) makes it a
  haiku-sized probe.
- After compaction the model still sees the `compact` SessionStart's stdout
  and no longer the `startup` one, so SessionStart is the post-compaction
  delivery.
- An Agent-tool subagent fires no `UserPromptSubmit` and no `SessionStart`;
  its `PreToolUse` stdin carries `agent_id` and `agent_type` (the parent's
  calls do not) with the PARENT's `session_id`. Hook order in `-p`:
  SessionStart, UserPromptSubmit, then the first PreToolUse.
- A hook's process chain (probed 2026-09-12, macOS): a `python3 "<path>"`
  hook's parent is the `claude` that runs it, with no shell between, even
  when the command holds a `$VAR` for the harness to expand; a
  `/bin/sh` script hook is the same depth. A one-shot `claude -p` run from a
  pane's Bash tool sits two frames deeper: `hook <- claude -p <- /bin/zsh
  <- claude <- pane shell`. `herdr-session-link.py`'s `FRAMES` rests on
  this. Probed without touching the pane's stamp by unsetting herdr's
  environment for the one-shot: `env -u HERDR_PANE_ID -u HERDR_SOCKET_PATH
  claude -p ok --model haiku --settings '<a SessionStart hook that writes
  its ps chain>' < /dev/null`. `ps -o comm=` on macOS prints the path the
  process was started by, so a symlink named `claude` reads as `.../claude`.
- `campaign-name-session.py` sets the herdr pane name synchronously and
  only then queues `/rename`, so a hook on that `/rename` prompt already
  sees the new role in `herdr agent list` by session id, the way `role_of`
  reads it.

### Which instruction files a Claude session loads, by launch shape

Probed 2026-09-06, claude 2.1.261, `<campaign>/scripts/probe-load-227{b,c,d}.sh`
(#227 NOTEs hold the numbers). Method: `claude -p --model haiku --max-turns 1
--output-format json`, ask it to quote marker strings; first-turn tokens =
input + cache creation + cache read.

- An ancestor `CLAUDE.md`'s direct text loads from any subdir; its
  `@AGENTS.md` import does not, and a subdir `CLAUDE.md` saying
  `@../AGENTS.md` does not pull the parent either. So a session in
  `<campaign>/` never sees the base rules.
- A project `.claude/agents/<name>.md` reaches a main session via
  `--agent <name>`, adding its prompt and keeping every `CLAUDE.md`; an
  Agent-tool subagent of that type gets the definition plus everything its
  parent loaded.
- A project `.claude/rules/<x>.md` with `paths:` frontmatter loads only
  when a matching file is Read; a skill loads only on invoke.
- A worktree root loads its own `AGENTS.md` once; `--add-dir` inside the
  same project adds nothing; an interactive session starts ~14K tokens
  above `-p`.
