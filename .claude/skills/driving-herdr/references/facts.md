# Herdr and Claude CLI facts

Probed facts for a session that launches, drives, reads or retires a herdr
pane, arriving from `.claude/skills/assuming-role/references/launching.md`.
`guide.md` beside this file (`herdr --skill`, byte for byte) is the
authority on the happy path; `launching.md` owns the launch procedure; the
scripts named below own what they read. This file holds only where the happy
path breaks and nothing else states it. Every fact carries the date it was
probed; herdr moved 0.8.0 → 0.8.2 across those dates (8/12–8/21 vs. 8/28
onward) and to 0.9.0 by 2026-09-17, and a fact with no version note was
probed against whichever build was live that day.

## Contents

- **Launching an agent** — the two-step launch, where env and flags go, and
  what corrupts a pane.
- **Driving a pane** — keys, text, slash commands, and prompts that merge.
- **Reading a pane** — what a pane read can and cannot see, and its traps.
- **Reading a delegate's transcript** — the path and the one safe `jq` form.
- **Agent list, liveness, and who is who** — the row, the session-id stamp,
  what `agent_status` means, and the states that read `idle` while stuck.
- **Naming and addressing** — what `campaign-name-session.py` does not cover.
- **The usage-limit menu**.
- **CLI shape** — exit codes, JSON output, the bundled schema.

## Launching an agent

The pane must exist first:

```sh
herdr tab create --workspace <ws> --cwd <clone> --label <name> --env KEY=VAL --no-focus
herdr agent start <name> --kind claude --pane <pane_id> -- <claude args...>
```

- **Env for the agent goes on `tab create --env`**, not on `agent start`,
  whose whole option set is `--kind`, `--pane`, `--timeout` (milliseconds;
  `--timeout 90` is refused as `invalid_agent_timeout`, probed 2026-09-05).
  `--env` is also on `workspace create` and `pane split`. Re-probed at 0.8.2,
  2026-08-30.
- **`--kind claude` types `claude` itself; do not repeat it after `--`.**
  `-- claude --model opus …` produced the pane line `claude claude --model
  opus …`, and the second word became the session's first prompt (probed
  2026-09-06). The line is
  `-- --model opus --session-id <uuid> --name <name> [--add-dir <base>]`.
  `--model fable|opus|sonnet` and `--effort <level>` both start a session
  (probed 2026-09-06, three launches), so the effort is a launch flag and
  never a prompt sentence.
- **`root_pane` is a pane object, not an id** — take
  `.result.root_pane.pane_id` on both `tab create` and `workspace create`. It
  is a sibling of `.result.tab`, not inside it, so `.result.tab.root_pane`
  raises `KeyError` (re-probed 2026-08-28). Handing the object to
  `agent start --pane` fails `agent_pane_not_found` with the whole object
  echoed, which reads like a missing pane rather than a type error. Still
  `{"$ref": PaneInfo}` in the 0.8.2 schema (2026-08-30).
- **A fresh pane's shell needs a moment**: `agent start` fails with
  `agent_pane_busy` until the shell reaches its prompt, so retry that code
  (2026-08-12).
- **A claude start measures ~3 s here**, with or without a prompt argument,
  so a 30 s `timed out waiting for agent startup` is an anomaly, not a slow
  launch — one cause is a typed line dropped past 1024 bytes (`launching.md`,
  The launch line): the pane shows the command echoed and sitting
  unexecuted at the prompt, which is how to tell (2026-08-21, eight starts
  lost this way).
- **A second `agent start` on a pane whose first attempt timed out corrupts
  it**: the first line is still in the shell, the retry concatenates onto its
  tail, and the shell runs the tail (`zsh: command not found: ude`). The
  prompt that follows lands in a shell, not in claude. Recovery is
  `herdr tab close` and a fresh tab, never another retry on that pane
  (observed 2026-08-28).
- **`agent start` refuses exactly Unicode control characters** in any `--`
  argument (`invalid_agent_argument`: U+0000–U+001F, U+007F–U+009F), so a
  newline, tab or CR is refused and nothing else is — quotes, `$`, `\`,
  Korean and emoji pass, each argument single-quoted by herdr (0.8.0
  source and live probe, 2026-08-12).
- **`pane run` word-splits its command**, so a quoted multi-word argument
  arrives as separate words: a launch ending `'Read <path> and carry out the
  brief.'` delivered the single word `Read`, herdr exiting 0 (observed
  2026-08-28, claude-code 2.1.250). Keep `pane run` for single-token commands;
  any sentence goes by `agent prompt` (`launching.md`, Delivering the prompt).
- **Trust and the external-import answer persist per directory**, so only the
  first launch after a fresh clone pays the dialogs — and **a directory
  rename resets folder trust**, so a launch right after one pays them again.

## Driving a pane

- **`send-keys` reports delivery of the keystroke, never its effect — no
  single key is a reliable submit.** `Enter` is swallowed by the selector
  footer a usage-limited session shows; `Return` is also lost when it
  arrives while the pane is still consuming a `send-text` paste — the prompt
  then sits in the composer while `agent_status` reads `idle` (12 minutes
  unsent, 2026-08-03). Confirm a submit by its effect: the agent leaves
  `idle`, or the input box reads empty. Recovery is `Escape` to dismiss a
  footer, then `send-keys <pane> Return` — but never `Escape` when the
  earlier submit may have landed, because it interrupts a running turn.
- **Keys go in with `herdr pane send-keys <pane> <Key>`; literal text with
  `herdr pane send-text`.** There is no `herdr pane key` — it prints the pane
  usage banner and sends nothing, which reads like a no-op. `down enter`
  answers menus; `esc` is the canonical Escape name.
- **`pane send-text` loses the tail of a line past 1024 bytes, silently**:
  the terminal's `MAX_CANON` (`MacOSX.sdk/usr/include/sys/syslimits.h:89`,
  re-read 2026-08-30) drops it, herdr exits 0, and the pane shows the cut
  text as if it were all (a 1.4 kB prompt arrived as exactly 1024 bytes,
  2026-08-12). Chunking does not help: the limit bounds the line, not the
  write. Keep typed text well under 1024 bytes.
- **Two prompts sent back to back concatenate into one input line** — to an
  idle pane, and within one shell command (`/compactSession limit reset…`,
  run as an unknown command; probed 2026-09-05 and 2026-09-07). Prompts to a
  `working` pane queue and merge the same way (2026-09-04,
  kalaluthien/campaign-base#169). Send one prompt per pane per turn, and
  read the pane for its marker before the next.
- **A slash command that opens a dialog makes `agent prompt --wait` report
  `agent_prompt_stalled` while the command in fact ran** (probed 2026-09-08
  with `/remote-control`: stalled at 5000 ms, the pane showing the dialog).
  Read the pane before concluding, and dismiss the dialog rather than
  re-sending. Re-probed on 0.9.0, 2026-09-17, with a bare `/model`: stalled
  at 5000 ms with the picker on screen and the status still `idle`, so the
  guide's `blocked` does not cover a slash command's own dialog. The guide's
  rule that a stall does not prove non-delivery is this case.
- **`/model <m>` and `/effort <e>` switch a running session in place, and
  each rewrites the user's default** -- `model` and `effortLevel` in
  `~/.claude/settings.json`, as the pane says (`saved as your default for new
  sessions`). A session with history answers `/model` with a `Switch model?`
  dialog, option 1 `Yes` selected, and the next prompt's Enter answers it and
  is lost; a fresh session gets no dialog, and `/effort` gets none either.
  The transcript's assistant `model` changes only at the next turn (probed
  2026-09-14, claude-code 2.1.270, rule-check#431).
- **A pane footer is stale UI, not state**: a limit-blocked session kept
  showing "2 shells still running" after `pgrep` found none. Probe the
  process table before treating a footer claim as a running job.
- **`tab close` kills every pane in the tab, and a session may split its
  own pane for a delegate**, so `agent list` shows two names with the same
  `tab_id` and closing by the tab takes the live one too. Confirm the
  target's `tab_id` belongs to it alone, and close the pane when it does not
  (observed 2026-08-28).
- **The inherited-environment trap**: a subagent shell, or any child of a
  pane session, reports `HERDR_ENV=1` by inheritance, so a "no pane" reading
  taken there is the parent's pane measured twice. Measure a natively
  pane-less process, or say the reading was simulated with `env -u`.

## Reading a pane

- **A pane read is a lossy, rendered screen, not a transcript.** Output
  scrolls out for good as the agent repaints — the same pane returned 59
  lines and 11 minutes later 11 — so read it for markers that are present;
  absence proves nothing. A claude session's own output sits behind its
  glyph and indent (`  ⏺ WORD: …`, re-read 0.8.2, 2026-08-30), so allow the
  decoration in front of a marker. And match the *shape* a state draws,
  never the sentence it contains: a pane showing a file or diff that quotes
  your marker prints it too — a driver anchored on a menu's label pressed
  Return into one every poll (2026-08-07).
- **`--lines` is capped by the emulator's buffer and at 1000, not by the
  flag.** `--lines 200`, `1000`, `5000` and omitted all gave the same 43 rows
  on a 44-row viewport (0.8.2, 2026-08-30); `1001`–`3000` capped at 1000
  (2026-09-05); and a pane can answer fewer than both `N` and its history
  (a 48-line pane gave 46 at `--lines 60`, nothing at `1..10`). So "shorter
  than the window, therefore the whole history" is false: read the
  transcript for anything that must be absent.
- **`pane read` has no pattern or context flag** — its options are
  `--source`, `--lines`, `--format`, `--ansi`, `--raw` (0.8.2, 2026-08-30).
  `pane wait-output` carries `--match`/`--regex`, for a wait only.
- **`pane read` takes the id positionally and refuses `--pane`**
  (`unknown option: --pane`, 0.8.2, 2026-08-30), while `pane split`,
  `agent prompt` and `agent start` take `--pane <ID>`. Read the usage line
  rather than assuming the flag. `pane split` also requires
  `--direction right|down`, with no default.
- **`agent read` prints plain text, not JSON**, unlike `agent list`,
  `rename` and `prompt`; and `agent read --lines` refuses a `working` pane
  (`agent_not_idle`, probed 2026-09-05) — a not-yet, not a no. `--source
  visible` reads a working pane but only its visible screen.
- **`agent read` and `pane read` answer different lengths for one window**
  (2026-09-09): `agent read` scopes to the agent's own turn, which a
  compaction resets, while `pane read` reads the terminal's raw scrollback,
  which compaction does not clear — right after a release and compaction,
  `agent read --lines 1000` gave 62 lines without the release line and
  `pane read` 530+ with it. To find what printed before the last compaction,
  use `pane read`.
- **A failed `pane read` looks exactly like a faded screen**: the CLI prints
  its error as JSON on stdout, so a classifier sees text holding none of its
  markers. Check the exit status before trusting a no-marker verdict, and
  give that verdict a terminal branch rather than "keep waiting".

## Reading a delegate's transcript

Read progress from the transcript, never from `agent_status`. The path is
`~/.claude/projects/<cwd with every / and . replaced by ->/<uuid>.jsonl`,
the uuid being the row's `agent_session.value` — or the `--session-id` the
launch chose.

```sh
jq -rn 'first(inputs | select(.type == "user") | .message.content
        | if type == "string" then . else (map(.text // "") | join(" ")) end
        | select(test("^<(local-command|command-name)") | not))' <transcript>
```

**`-n` with `inputs`, never `-s`**: a live transcript is being appended to,
so slurping fails on the half-written tail and the session reads as empty.
The wrapper filter matters — the literal first record is often a
`<local-command-caveat>` or `<command-name>` block.

## Agent list, liveness, and who is who

- **A row** — `herdr agent list` answers `{"result": {"agents": [...]}}`;
  each row carries `cwd`, `foreground_cwd`, `name` (absent on an unnamed
  session), `agent_status`, `pane_id`, `tab_id`, `agent_session.value`, and
  at 0.8.2 `terminal_title`, `terminal_title_stripped`, `focused`,
  `workspace_id` and `state_change_seq` (2026-08-30). Parse with `jq`, never
  from screen order.
- **`agent_session.value` is the Claude session id** — the value
  `$CLAUDE_CODE_SESSION_ID` holds, on every row probed, named or not; it
  survives a restart and a rename. **After a resume the env id and the
  process's `--session-id` differ**, and `agent list` keys on the env one.
- **The stamp is write-once per pane** (0.8.2, replayed by hand 2026-09-06:
  report → ok, `clear_agent_authority` → ok, report → ok, value unchanged).
  So whichever session stamps a pane first owns its row for the pane's
  life: a `/clear` leaves the stamp on the abandoned transcript, and a
  nested `claude -p` that stamps first leaves the pane's session unreadable
  by id. A lookup keyed on the id then returns no match, which reads like a
  session herdr never knew — read the row's id before trusting one. The
  consequence for roles is `campaign-role-brief.py`'s header.
- **Read `ListAgents` before naming a pane.** Its first line names this
  session; nothing in `herdr agent list` says which row is you, and
  `campaign-name-session.py` will name somebody else's pane as readily.
- **The Remote Control host pane is `w40:p14`, herdr-named
  `remote-control`** (owner, 2026-09-05); a fresh one reads as an idle
  unnamed session at the base root and shows `·✔︎· Ready · Capacity: 0/32`
  rather than a `❯` prompt. Read the pane before handing work to any idle
  unnamed row.
- **Presence is the liveness signal, not `agent_status`.** `agent list`
  drops an agent within ~1 s of its claude process dying (probed by `kill`,
  2026-08-21), so a listed agent is a live process. `agent_status`
  (`idle|working|blocked|done|unknown`) reads the screen: a session pausing
  mid-turn reads `idle`, and `done` means one turn ended. **`idle` and
  `done` differ by history and by who looked, not screen** — herdr promotes
  `idle` to `done` only once it saw the agent `working`, and a session whose
  first turn ends inside the ~3.1 s `agent start` takes to attach the name
  reads `idle` for good. And only where nobody saw it end: the same one-turn
  prompt read `idle` from a pane split into the focused tab and `done` from a
  `tab create --no-focus`, and an `agent read` left `done` standing (probed
  0.9.0, 2026-09-17). Never read `idle` as "took no prompt".
- **The status rules are data**: a per-agent TOML manifest under
  `~/.local/state/herdr/agent-detection/remote/<agent>.toml`
  (`herdr server agent-manifests` prints which is live; 2026.08.29.1 on
  2026-08-30). `herdr agent explain <target> --json` prints the rule that
  matched, its screen region and the evidence. A permission prompt and a
  confirm form resolve to `blocked`; there is no "needs you" state.
- **Stuck but `idle`**: Claude Code's startup dialogs (`launching.md`, What
  silently stops a delegate), the usage-limit menu (below), and **a pane with
  a live background shell** — `background_shell_working` does not match the
  vim-mode footer `-- INSERT -- ⏵⏵ auto mode on · 1 shell` (`agent explain`:
  `matched: false`, 2026-08-30), so anything closing on `idle` kills the
  command. A live background *agent* does read working at manifest
  2026.08.29.1. Read the footer yourself before retiring a pane.

## Naming and addressing

`.claude/skills/assuming-role/scripts/campaign-name-session.py` owns setting
both names, the queued `/rename`, the echo and its two forms; its docstring
is the account. What it does not state:

- Unset the herdr name with `herdr agent rename <pane> --clear`;
  `rename <pane> ""` is refused (`invalid_agent_name`: 1–32 chars,
  lowercase, `-`/`_`).
- **An address can go stale while the session lives; its `[ref]` does
  not.** A `SendMessage` bounced with `No agent named '…' is reachable`
  against a session alive at the same `[ref]` under a new name — three
  bounces on one machine in one day, the last after both sessions named
  themselves. **Address by the `[ref]` when a name bounces.**
  The error names the current holder, and `ListAgents` annotates a recent
  rename (`was <old> until 41s ago`), which narrows the window but does not
  close it.

## The usage-limit menu

- **The menu blocks the pane until answered; it does not clear at the
  reset.** Five sessions sat on "Stop and wait for limit to reset" two hours
  past it (2026-08-07). `send-keys <pane> Return` confirms option 1 (`Enter`
  is swallowed there). Confirmed after the reset, the session drops to an
  idle prompt without resuming its turn — one `send-text "continue"` plus
  `Return` resumes it (four sessions). Confirmed before the reset, the
  auto-resume is unverified: poll later, nudge if still idle past it.
- **The machine sets `autoContinueAtUsageLimit`** (since 2026-08-18, still
  `true` in `~/.claude/settings.json` on 2026-08-30), so the menu should not
  appear for new stops — see the `topic-claude-usage` memory before typing
  into a parked pane.
- **The menu carries no reset clock**, and its `agent_status` is `idle` or
  `done`, never `blocked` (2026-08-07/08). The banner that names one is
  `campaign-limit-reset.py`'s to read.

## CLI shape

- **Unknown subcommands print help and exit 2** at 0.8.2 (through 0.8.0 they
  exited 0), and an unknown flag fails loudly (`unknown option: --x`), so a
  probe that returns a `result.type` is a real verification. `--help`
  answers per subcommand at every level (0.8.0, 2026-08-18); check it
  against the installed binary before scripting (2026-08-30).
- **Most commands print JSON already, so `--json` is not a flag on them** —
  `agent list --json` answers its usage line at exit 2 (0.8.2, 2026-08-30).
  **`herdr status --json` is the exception** and the only honest way to read
  it: the human form prints `version:` under both a `client:` and a
  `server:` block, so a line-wise parse takes the client's (2026-09-06).
- **`herdr api schema --json` prints the bundled request/response schema**:
  results are tagged by a `type` const (`agent_started` carries
  `result.agent.pane_id`; `pane_created` is `{pane, type}`, 2026-09-06),
  method names are the CLI names with a dot and an underscore (`pane wait-output` is
  `pane.wait_for_output`), and param keys are the flags. So a parse can be
  verified without a live probe (`protocol: 20`, `schema_version: 1`,
  2026-08-30).
