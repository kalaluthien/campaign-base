# campaign-base

A base for running **campaigns**: units of work across the repositories they
need, on repositories that live elsewhere. `README.md` says what the base is
and `spec/campaign/*/*.als` why these rules are what they are; this is how to work
here.

**Much of what used to be written here is now enforced.** `scripts/campaign-primitives.py`
lists this repository's scripts and hooks; run it in full for what each decides. It
cannot see what lives off this tree — `main`'s branch protection, the machine-wide
git hooks — so its silence is not evidence that no mechanism exists. Use `gh` for
every GitHub operation; it is authenticated here.

**Ask the person only what no check can settle** — preference, scope, a
destructive stake. Everything else, decide and do, and report the decision.
**Report outcomes, not operations**: what changed and the artifact that proves
it — a path, a commit, a URL — with the journey only when the person asks how.

# The campaign

One assignment a person is responsible for, worked across the repositories it
needs, which may be none. Bigger than a ticket, no size ceiling. It splits into
sub-issues, and follow-ups keep arriving until someone decides it is over.

## Routing an arriving request

Settle this before anything else. Most of what arrives here loads no skill.
**The session a request arrives at reads it here**; which shape the work then
takes, and whether that session is its planner, is § The binding.

**A person saying a campaign is over is routed before anything is read.** Load
`closing-campaign` and stop, or the readings below take the close for a sub-issue.

Otherwise, two readings, in this order.

**One: does any open campaign's Scope cover the request?** `scripts/campaign-tracker.py campaign-issues`
lists the open campaign issues — **never survey the tracker unfiltered**, since it holds
three kinds of issue and only structure classifies them; where structure cannot
answer, both templates are in `.claude/skills/opening-campaign/assets/`, and **an
issue matching neither is the third kind, which every reader leaves alone**. Read
the body of each campaign issue that could plausibly cover the request — the title does
not carry the Scope. Match on Scope, never on `## Repos`, and treat testing or
fixing a campaign's own deliverable as covered by it.

**Two, only if nothing covers it: is the request finished when this session
ends?** A campaign outlives the sitting.

| what the two readings say | what this is |
| --- | --- |
| An open campaign's Scope covers it | **A sub-issue of that campaign.** Read the binding first (§ The binding), then § Sub-issues. Load `opening-campaign` only to *join* — this machine has no directory for the campaign yet. |
| Two or more could cover it, or the fit is arguable | **A question for the person.** Name the candidates; do not guess. |
| Nothing covers it, and it ends with this session | **Not campaign work.** Answer it, or make the change and land it. |
| Nothing covers it, and it will outlive this session | **A new campaign.** Load `opening-campaign`. |

**Size is not one of the readings**, and asking it first is the mistake this
ordering prevents. A one-line edit inside a Scope is that campaign's sub-issue.

## The three planes

Every artifact belongs to exactly one, and the plane decides where it is stored
and whether it survives the machine. Identify the plane before any git command.

| plane | holds | stored in |
| --- | --- | --- |
| **base** | `AGENTS.md`, `CLAUDE.md`, `README.md`, `.gitignore`, `.claude/`, `spec/`, `scripts/`, `.github/` | this repository |
| **member repository** | the code and its history | each repository's own remote |
| **campaign** | which repositories, what for, how far along | GitHub issues |

`spec/` is normative and is Alloy whose comments are the spec, and an HTML
diagram may sit beside a model; it holds no markdown, and that is the part a
guard refuses. Two `pre-commit` guards refuse a commit that breaks the
shape — `check-tree-shape` and
`check-rule-readers`, whose header gives the syntax exempting a block that must
hold a guarded form. **Do not write a second reader of a rule a script owns**:
two of them drift.

The campaign directory holds no plane of its own: git-ignored scratch, and
**nothing durable may live only there** — a repo-less campaign lands its results
in the campaign issue and its sub-issues, the memory pool, or a repository by hand.
**No RECORD OF THE WORK lives only in `runtime/`** — a sub-issue's plan, a
session's state at a stop, the campaign's progress. Each of those belongs on the
issue it is about, a comment on the sub-issue or on the campaign issue for a
planner's own state, where every session and every machine can read it; a design
a file was the only copy of dies with the directory. What may stay there is what
no issue can hold — a pid, a log, a lock — and what is DERIVED from an issue and
re-derivable at any time: `runtime/repos` and
`runtime/campaign-issue-body-derived.md`. `opening-campaign` writes both and
reads the first back; `closing-campaign` and `campaign-claim` read the second,
and `closing-campaign`'s sync rewrites it.

**Resolve the base root one way, everywhere:**

```sh
BASE=$(cd "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")" && pwd -P)
```

The base root is the main checkout by definition, and this form returns it
from a linked worktree too, where `--show-toplevel` returns the worktree instead.
Never run one git command across member repositories. **Operate on a worktree
from the main checkout with `git -C <path>`**, edit through the worktree's own
absolute paths, and never `cd` into one a later step merges or removes.

### Installed repositories

**A repository installed on this machine — checked out where it is used — has
two checkouts once a campaign clones it**, and one rule covers every such
repository: work in the clone, and **a merge is not finished until the install
shows it**. The base is one row of that rule, not a case beside it.

| repository | installed at | how a merge reaches it |
| --- | --- | --- |
| the base | the base root | `scripts/campaign-installed.py reach`, whose `apply` is `scripts/install-hooks.sh` |
| a `## Repos` entry carrying `(installed: <path>, apply: <command>)` | `<path>` | the same command, running `<command>` |

The marker is `scripts/campaign-repos.py`'s to read, and the base's row is a
constant in `scripts/campaign-installed.py`, since `## Repos` refuses the base.
**Whoever merges runs `reach` for the repository the merge landed in, and the
`REPORT` quotes its line**, which names the install's sha; `closing-campaign`
step 2 runs `check` and refuses while an install is behind. The model is
`Machine.installed` and `reachDiscipline` in `spec/campaign/directory/system.als`.
Two hazards stay with the clone: **behind is a merged pull request the
checkout has not caught up to**, so the clone must not be behind at launch and
the install must not be edited while behind; and **a skill edited inside the
clone does not change the running campaign**. Commands:
`.claude/skills/opening-campaign/references/launching.md`.

# Session identity

**The role a session holds, what it licenses, and the moments of its lifecycle
are the `assuming-role` skill's**, and its brief hook pushes them into every
session start. What stays here is what no skill answers: which campaign a
session is in, what it calls itself, and where its work lives.

## The binding

**A campaign runs on one machine at a time, and every session on that machine is
an equal session of it.** No session holds it; each campaign-wide write names its
own guard.

One reading decides whether a session is in the campaign, and `campaign-tracker bound <N>`
is its one reader: `here`, `elsewhere <machine>`, or `unbound`. **Read the word,
never the exit status**, as for `campaign-local-work` and `campaign-claim live`.
Two `bound:` labels is the one thing it refuses to answer rather than answering
wrongly, and only `campaign-tracker bind <N>` repairs that.

| the word | this session is |
| --- | --- |
| `here` | **a session of this campaign.** Name this session first (§ The session name), then work the directory if there is one, scaffold it if there is none (`opening-campaign` steps 2 and 4), and take the shape the request calls for — a worker takes a sub-issue, a planner files them and distributes. |
| `elsewhere` | **not in this campaign.** Stop before any write and any launch, and name the machine. |
| `unbound` | **not bound yet.** Only a person's word binds an existing campaign. |

**The binding gates four things**: the campaign issue body, the `bound:` label,
a claim, and a launch. Read it before each of those. Only one of the four has a
machine behind it: `campaign-claim take` reads the binding before it cuts a ref
and refuses on anything but `here`. The body write, the label, and a launch are
gated by this rule and the model alone
(`spec/campaign/session/scenarios.als`, `boundOnly`), so read the word yourself
before each. **The sub-issue link is outside it**: any session on any machine
may file a sub-issue of any campaign, one it is not a session of included,
because a sub-issue is a record and not a claim — the atomic gate stays
`campaign-claim take`'s create-ref, and the model's `addMember`
(`spec/campaign/github/system.als`) has no actor, machine, or binding
precondition. What the filer still owes: file from the template, and leave
adding a repository the work needs to `## Repos` to a bound session, since that
is a scope change (`opening-campaign`, "A repository the campaign issue's `## Repos` list does not name").

**The binding is one `bound:<machine>` label on the campaign issue**, from
`hostname -s`, written by `campaign-tracker bind <N>` and by nothing else — it
adds this machine's and removes every other in one edit, so the two-label state
it repairs is one it cannot leave behind. A label is read by exact name and has
no history, so there is no latest to pick and nothing to page through.

**A session binds in exactly two cases**: for a campaign it has just filed
itself, and when a person tells it to — migration, and the person's call because
nothing here can observe its premise. Bind, then read it back with `bound`; a
label naming somebody else means the campaign was migrated out from under you.

**A session of a campaign is a planner or a worker, and the request decides
which shape it takes.** A simple request has a worker only: the session files
the sub-issue and works it. A request that needs decomposition has a **planner**
and separate **workers**, each **a session of its own on this machine**: another
session that takes a sub-issue, or a herdr delegate the planner launches
(§ Execution mode chooses between them, by the repository first and then by cost
— a delegate is the ordinary shape for a member repository and the mode of last
resort for the base, and a repo-less campaign has the first form and not the
second; the launch itself is
`.claude/skills/opening-campaign/references/launching.md`). What each role may
write is `.claude/skills/assuming-role/scripts/campaign-roles.py`, and the
moments of each lifecycle are that skill's two references; neither is restated
here. The model is `Planner` in `spec/campaign/orchestration/system.als`, and it
requires a planner only of a delegate launch.

**#185 enforces the code-plane bar over a FILE TOOL's writes and no further**: a
shell command is read only for the `gh` writes in it, never for what it does to
a file, and `check-commit-claim.py` reads no role — so `sed -i` and `git commit`
from a planner are refused by nothing today.

**No role licenses a write, nor does asking**: a session that cannot satisfy a
guard does not make the write. **The planner claims the branch before it
launches onto it**, with `campaign-claim take <N> <issue> <topic>`: the ref is
cut now, and the delegate checks it out when it starts, which is what makes the
branch the delegate's.

## The session name

**`<slug>-<role>-<n>`**, the slug being the campaign's own (§ ID, slug,
directory, branch) and the role being `planner` or
`worker`, for every session on this machine; `<n>` is one counter across both
roles, assigned in the order sessions appear, so two do not both pick `-1` —
this sentence is that counting rule's one home. **The role word is not a
label**: since #185 `check-campaign-claim.py` resolves it from `herdr agent
list` and decides both planes by it, so a name of the wrong shape is refused
every campaign write; what a well-formed one licenses is
`campaign-roles.py`'s. It is also what a person reads in `herdr agent list`,
which is how the two used to be confused. It is per-session, where the `role` on the model's Agent
atom is per launch and records the shape one sub-issue was worked in.

**The name is not a security boundary, and is not meant to be.** A session can
rename itself, and every session here shares one `gh` account — so one that
renames itself a planner already holds the power the name would grant. What the
role buys is that it is explicit and that the mistake is loud; #194 is the
sub-issue for tying the name to something the named session did not choose.

**Set it at
the start of every session of a campaign, whichever path started it** — the
`here` reading above, `opening-campaign` step 3, or a delegate launch — because a
session that arrived from another campaign keeps that campaign's name until
something sets it. The one pattern lives in `.claude/skills/assuming-role/scripts/campaign-name-session.py`, and
`check-campaign-claim.py` imports it rather than restating it.
**Nothing refuses a stale name at the CLAIM**, which the record used to do by
carrying the name into a place later readers trusted; with no record there is no
such place. What reads the name instead is the guard, on every write: a name of
another campaign gets a worker refused that campaign's issues, and a name of
no shape gets both planes refused.

**The sub-issue is deliberately not in the name**, because a session works
several; which one a session is in is asked, not derived. **Never test a name
against a branch**: they are two strings on purpose, and a test treating them as
one finds whatever happens to match and misses the rest.

**A session has two names and neither propagates to the other**, so
`.claude/skills/assuming-role/scripts/campaign-name-session.py <pane> <name>` sets both and refuses a name the rule
does not admit; read what it reports applied, and confirm with `ListAgents`,
which resolves the harness name a message is addressed to. `herdr agent list`
shows the pane.

## ID, slug, directory, branch

**A campaign has two names.** The **ID** is what every `gh` call is given; the
**slug** is what every name a person reads is built from. Neither substitutes
for the other, and a missing slug refuses rather than being guessed at.

- **ID** — the campaign issue's number in `kalaluthien/campaign-base`, typed `#N`.
  The campaign issue carries the `campaign` label; every survey lists by it, so a campaign issue
  filed without it is in nobody's listing.
- **Slug** — one `campaign:<slug>` label on the campaign issue, the same shape
  as `bound:` and read the same way. `campaign-tracker.py`'s `slug <N>`,
  `issue <slug>` and `slugs` are its readers, and `campaign-issues` refuses an
  open campaign that has none. **`campaign-name-session.py` owns what a slug may
  be** — a length ceiling herdr's own limit sets, and words it may not contain —
  and every other script asks it rather than restating it. **The planner mints
  one at open** from `slugs`, which lists every slug ever spent; the owner
  vetoes by renaming the label before any session is named. Two campaigns cannot
  share one, because GitHub keeps label names unique.
- **Directory** — `campaign-<slug>-<date>` at the base root, `<date>` the local
  `YYMMDD` it was scaffolded, git-ignored, optional off the bound machine. The
  bare `<slug>/` is the accepted older form and nothing renames a directory that
  wears it. The date is for the person reading `ls`, since a bare slug beside
  `scripts/` and `spec/` says nothing about what it is. A campaign *is* its
  campaign issue; the directory is one machine's cache and holds nothing that is
  not derivable from GitHub. **What makes a directory a campaign's is the
  `.campaign` file inside it**, naming the campaign — neither form's name is
  read, because no name shape separates an arbitrary slug from `scripts/`.
  It sits beside `runtime/` and not inside it, because `runtime/` is scratch
  sessions sweep. `check-campaign-claim.py` owns that reading,
  `scripts/campaign-directory.py` is the one word other scripts and skills ask
  it for, and **nothing composes the path out of the slug**. **A campaign
  directory with no marker is a campaign nothing on this machine can see** — not
  a claim, not a guard log, not a close — so `opening-campaign` writes it at
  scaffold and a directory that predates it gets one by hand.
- **Branch** — `<slug>/<issue>-<topic>`, **the sub-issue's whole claim** as
  well as its workspace. `campaign-claim take` cuts it from the remote and writes
  nothing else; create-ref refuses an existing ref server-side, so the claim is
  atomic across every machine, where a survey-then-file is not. **Every
  sub-issue cuts one**, work that lands no commit included — a repo-less
  campaign's on the base.
- **The retired form is gone** — before #181 a session name and a branch
  carried the campaign NUMBER. Nothing reads it since #237, and nothing
  refuses it by name either: `campaign` is a barred slug segment, so
  `campaign-1` is not a slug and no name or branch can be read as one.

**Before adopting a word for a renamed value, grep the tree *and* `git log -S`
it**: a word absent from the tree may be pinned by an assertion that it is not
there, and a word the tree holds may already carry another meaning. **Retiring a
name or a rule sweeps every place it is stated** — its path, its role word, the
prose aliases, the spec that calls itself the contract, and any validator whose
pattern encodes it — in every language the tree is written in.

# Campaign work

**Open** — load `opening-campaign` when the request opens a campaign, or joins one
this machine has no directory for. **Close** — load `closing-campaign`; only a
person decides a close.

## Sub-issues

One sub-issue is one GitHub issue, **filed on this base's tracker whatever
repository its code lives in**, and created **as a sub-issue of the campaign issue**:

```sh
gh issue create -R kalaluthien/campaign-base --parent https://github.com/kalaluthien/campaign-base/issues/<N> ...
```

That one flag is the whole index, and `campaign-tracker index <N>` reads it
back. Fill the body from `.claude/skills/opening-campaign/assets/sub-issue.md`.
**A member repository receives only the branch and its pull request**, so its
own issue conventions are never touched, and a repository this account does not
own, or a sub-issue moving two repositories at once, needs no special case. The
pull request body closes the sub-issue with the keyword and the full name,
`Closes kalaluthien/campaign-base#<issue>`: `campaign-tracker settlement`
reads `closedByPullRequestsReferences`, which a keyword populates and a bare
mention does not, and the short `#<issue>` closes the member repository's own
issue of that number instead. Which repository the work lands in is the
template's `## Lands in` section, since the issue's own location no longer says.

**One shape per kind, decided by structure and read by one script.** An issue is
a campaign issue by its `campaign` label, a sub-issue by its parent, both at once
by neither — a defect, reported — and the third kind by neither, which every
reader leaves alone. The third kind is exempt from the SECTIONS, not from the
ceilings: a title is a title. A title is a verb-first mission under the title
ceiling; a body is bullets or tables under the body ceiling; the sections are
`## Intent`, `## Scope`, `## Definition of done`, `## Plan`, `## Repos` and
`## Lands in`, and a kind **omits** one, never renames it. `campaign-tracker check <N>` is the one
reader: `bind` calls it and prints what it said, `campaign-claim take` calls it
with `--plan` and refuses on it. Both templates are in
`.claude/skills/opening-campaign/assets/`.

**A `backlog` sub-issue is not worked until the owner says so**, and only the
owner takes the label off — nothing here can observe that they changed their
mind. `take` refuses a claim on one. A sub-issue **without** the label is worked
as soon as it is filed or reopened.

**Every comment carries its kind on its first line**, `KIND <session
name|owner>: <one line>`, one intent per comment, under the comment ceiling, and
the guard reads it. **The three ceilings are numbers in two scripts and nowhere
else** — `campaign-tracker.py`'s `TITLE_CEILING` and `BODY_CEILING`, the guard's
`COMMENT_CEILING` — and each check prints the number beside what it measured, so
a document repeating one would be the copy that drifts. The five kinds are
`REPORT`, `REVIEW`, `BLOCKED`, `DECISION` and `NOTE`; § The four messages says
which goes where, and states once that the comment is the durable record while
the message of the same name is its notification, carrying no fact the comment
does not.

**A discovery is recorded the moment it is found**, by whoever can file it: one
held in a session's memory dies with its pane. **Look for the sub-issue it
belongs to before filing a new one**: read the campaign's sub-issue list, open
and closed (`campaign-tracker index <N>`), and where one covers the same
mechanism, append the observation as a comment and reopen it (`gh issue reopen
<issue> -R kalaluthien/campaign-base --comment`), so its history stays under one
number; the reopened work cuts a fresh topic ref under that number. File a new
sub-issue only when none fits. A parent holds at most 100 sub-issues, closed
ones included, which is a cost every new number pays and a reopen does not.

**A sub-issue is filed only for work that outlives one review cycle.** A defect
one commit fixes goes into the pull request already open on that file, or as a
listed item into the next sub-issue that touches it, and never onto a number of
its own: a sub-issue costs a claim, a pull request and a review whatever its
size, and #195 measured three that could not cover it — #170, #171 and #175 were
each closed within 27 minutes of being filed, and #171's single review round
alone cost 57,374 input tokens for 21 changed lines.

**A sub-issue whose work lives only under `<campaign>/scripts/` has no commit to
land**: it closes as completed with no pull request, its closing comment saying
what was built. Quote `campaign-tracker settlement`'s note for that row, not its verdict.

## The `## Repos` list

**`## Repos`** says which repositories to clone when a campaign is opened, and
`scripts/campaign-repos.py <path>` is its one reader; `- none` is the whole list for
a repo-less campaign. An entry installed on this machine carries
`(installed: <path>, apply: <command>)`, § Installed repositories, and is
cloned like any other. **Work that lands no commit is claimed all the same**,
with `campaign-claim take`: one ref, cut on the base. **Two readers make that
true rather than remembered, one rule read at two moments.**
`scripts/check-campaign-claim.py` is a `PreToolUse` guard answering "may this
session make this change" — the claim for a worker, and since #185 the
session's ROLE for both — for what has an unambiguous
target — a file tool's path and a `gh` write — and allowing every other shell
command unread, saying so. Since #196 it writes **one line per verdict** to
`<campaign>/runtime/guard.log`, git-ignored scratch, and says beside every
verdict whether that line was written; `scripts/guard-precision.py` reads the
log and pairs each refusal with the same session's next allowed call on the
same target, so a false positive is found by measurement rather than by
whoever it hit. The model rule is `verdictIsDurable`.
`scripts/check-commit-claim.py` is the `pre-commit`
gate where a shell write lands: a commit on a base tree or under a campaign
directory whose branch is not a claim is refused. A change landing outside every
base tree and every campaign directory is not campaign work and neither refuses
it; how each reads its target, and what it does when it cannot, is its
docstring's. `install-hooks.sh` installs both — the commit gate as a git hook,
the guard in
`~/.claude/settings.json`, because a delegate's clone is a different repository
and reads none of this one's settings. **A member repository ships no installer,
so its clone gets the commit gate from `acquire-repo.sh`** instead, by absolute
path into this base; before that it got the no-main-commits guard alone and
every shell write there landed unjudged.

## Execution mode

**Do it here, hand it to a subagent, or hand it to a delegate.** The session
the request arrived at chooses the mode before the work starts, **first by the
repository and only then by cost**. It is the planner only in the second shape
(§ The binding). **The three modes are a WORKER's**: since #185 a planner
changes no code by its own hands and none through a subagent, which carries its
session id and so its role, so a planner's only shape here is the third —
a delegate, or a separate worker session that takes the sub-issue.

A worker that *changes* a repository runs in a process started in that
repository's checkout: a herdr delegate in `<campaign>/repos/<repo>/` for a member
repository, and a session or an in-process subagent on a worktree for the
base. Reading any repository, and writing under `<campaign>/`, may run in any
mode. The harness fact underneath: a subagent and an interactive session load the
skills of the session or directory they were *started in*, and a skill marked
`disable-model-invocation: true` must be spelled out in a brief, never named.
**A repo-less campaign therefore has the first two modes and not the third.**

Then, within what the repository allows, choose by cost:

- **your own hands** for one small edit needing nothing from the build loop
  (a worker's hands: a planner's FILE-TOOL writes are refused and the
  refusal says so, while a shell write is caught by nothing — § The binding);
- **a subagent on a worktree** when several sub-issues can run at once, or the work
  would eat the session's turns;
- **a herdr delegate in a clone** when the work needs the repository's own
  toolchain, will take many turns, or two repositories must move together.

**Read only the part of a file you need** — the Read tool, or a bounded
`sed -n a,bp`. #201 measured file reading through the shell at 7.9MB, 61% of
everything this campaign read back, against 0.7MB through the Read tool: `sed`
5.7MB over 914 calls, `grep` 1.3MB, `cat` 0.9MB. **That is a rule without its
cause.** Those 914 `sed` calls averaged 6.2 KB, so they were already bounded, and
the volume is how many reads happened rather than how wide each one was; #201's
first step was to group the calls by file and say whether the cost is breadth or
repetition, and that step was never run. The instruction asking for `cat`/`sed`/
`grep` is the harness's own auto-mode text, which this repository cannot edit —
so what is written here is the habit, and the setting is the owner's.

**Weigh the setup against the work**: the delegate's price is paid per launch, so
for the base it is the mode of last resort. All modes share the mechanics —
the branch is claimed by `campaign-claim take` after the issue exists, because the
number is minted there; the `post-commit` hook pushes; it lands by a pull request.
**Write atomic commits with a search-optimized message and land them without
waiting to be asked**, since work is not finished until it is merged and pushed.
**A hook is never bypassed** — not with `--no-verify`, and not by moving
`core.hooksPath`, which is the same bypass shaped like configuration; report what
it refused and ask.

**Open that pull request on the first commit, not when the work is ready.** The
hook has already pushed the branch, so a late pull request only keeps published
work out of sight. An open one is where a review writes its findings, and it is
what survives the session that opened it.

## The campaign issue body

**The campaign issue body is a charter, not a status board.** `## Intent`,
`## Scope` and `## Definition of done` say what a person signed up for and
change only when the scope genuinely changes; the sub-issue index is the decomposition, and
`campaign-tracker settlement <N>` derives progress from it. So the body is written
at exactly two moments — a scope change, and the close. Adding work is neither,
and **when a request reads both ways**, ask with `AskUserQuestion` first. Adding a
repository **is** a scope change, so it syncs when it happens; held back until the
close it is invisible to every other session.

`closing-campaign` step 4 is the only sanctioned write, at either moment: it
compares the body against the copy the campaign `README.md` was derived from and
refuses when it has moved, so one write cannot silently discard another.

## Delegate launch

Any `herdr` command that drives a pane, or resolves its target implicitly, is
guarded by `test "${HERDR_ENV:-}" = 1` and names its target explicitly; the guard
is against acting on somebody else's session, never against reading.

A delegate is launched by the planner in `<campaign>/repos/<repo>/`. Three
invariants: **the brief is the sub-issue**, named by a one-sentence prompt, so
there is nothing to keep in step with it and nothing that dies with a directory;
the prompt is delivered by **`herdr agent prompt`** and never on the launch
line, an instance of § The four messages' criterion rather than a second rule;
and **read the pane once after every launch**, because the dialogs that halt a
fresh delegate do not all report `blocked`. **`--add-dir <base>` is a member
repository's**, whose cwd cannot reach `<base>/scripts/`; a delegate in the
base's own clone reaches them in its own tree and is launched without the flag.
It buys back none of the duplicated rules #202 measured, and `launching.md` has
the probe that says why. The campaign's principles reach the
delegate as **`CLAUDE.local.md` written into its clone** and excluded via
`.git/info/exclude` — a file on disk, so nothing has to prove it arrived. A
campaign's principles only ever *add*. The full procedure — the launch line, the
outcome names, and the three dialogs — is
`.claude/skills/opening-campaign/references/launching.md`.

# The running agent

## Completion, liveness, and local-only work

Three readings, and never answer one with another. **A signal means less than
its name promises**: before acting on one, enumerate everything that produces it
and everything that reads it.

- **Completion is a GitHub fact.** A sub-issue is settled when its issue is closed —
  as completed with its pull request merged, or as **not planned**, which is how a
  sub-issue gets dropped. Both readings are needed, or a sub-issue dropped on purpose
  never reads settled and its campaign can never close. **Nothing on a terminal
  screen is evidence.** `campaign-tracker settlement <N>` is the one reader.
- **Liveness and attribution are different readings, and a gate needs both.**
  `herdr agent list` gives liveness for every session here; the remote's
  `<slug>/` refs give every claim; and where each is checked out gives
  attribution. `campaign-claim live <N>` makes all three and joins the last two
  on the branch name, which a restart and a rename both leave alone; it
  concludes nothing, a close reads its counts.
  **Attribution names a WORKSPACE, not a session, and that is measured rather
  than conceded**: herdr reports where a session was *started*, a worker on
  the base works in a worktree, and that worktree's owning repository is not
  even the clone the session sits in — so no fact on this machine ties a session
  to a branch. Which is fine, because the two readers ask a different question:
  `release` must not delete a ref somebody is standing in, and a close must know
  whether any claim is still occupied. **A session is addressed by `ListAgents`**
  and asked which claim it holds. Read a delegate's progress from its
  transcript, never from `agent_status`, which reports the screen and calls a
  mid-turn pause `idle`. **A liveness verdict needs a delta, never a snapshot**:
  read the screen or the counters twice and diff the target artifacts between
  the reads. **A delegate killed mid-task is not proof its work is lost** — diff
  its artifacts before re-running it.
- **What exists only on this machine is the third question**, and
  `scripts/campaign-local-work.py <N> [dir]` is its one reader.

**State the set beside every count, and count it yourself**; a number a delegate
reported is that delegate's until you re-derive it, so relay it as theirs or run
it. **Assert a loop's iteration count**, because a body that never ran still
prints one line per iteration.

## The four messages

`spec/campaign/orchestration/system.als` is the contract; this is the short
form. `ListAgents` resolves the address; herdr's pane label is not one.

| message | direction | carries |
| --- | --- | --- |
| `STATUS` | campaign → agent | doing what, blocked on what, what exists only on this machine, safe to stop |
| `REPORT` | agent → campaign | a pull request URL and the sha it sits at, once per round, unsolicited |
| `BLOCKED` | agent → campaign | a decision that is not the agent's to make |
| `STAND DOWN` | campaign → agent | finish the turn and stop |

Four messages between sessions, carrying **only what the agent alone knows**:
anything about finished work duplicates a GitHub fact, and the copy is what goes
stale. **The claim is not among them** — it is a ref, not an announcement.

**`REPORT` and `BLOCKED` are also comment kinds, and the relation is stated
here once: the comment is the durable record, the message is its
notification.** The message carries no fact the comment does not, so a peer that
missed it loses nothing but the timing. Which is why the comment goes where its
reader is — a `REPORT` on the pull request, beside the `REVIEW` it answers, so
one round is one thread and the disposition can be checked against the findings
mechanically; a `BLOCKED`, a `DECISION` and a `NOTE` on the sub-issue.
`STATUS` and `STAND DOWN` have no comment kind at all: they are prompts into a
pane, by the two-channel criterion below, and there is nothing durable in
either.
**A finished peer leaves the campaign by fact, not by saying so**: it stops its
pane, or leaves the base tree. **A rename alone does not**, unless the new name
is another campaign's — `campaign-claim live` believes a name that says whose
work it is, and counts a name that says nothing whenever the session sits under
the base root. There is no `STOOD DOWN` comment,
because a close reads `herdr agent list` and a peer still listed is asked, never
killed.

**Shape a briefing the way its final, clarified version would read**: the state
in one line, then what is open as a table or a list, then the reasons, then the
decisions that are the reader's, each under its own heading.

**A verdict, a fix report, or a `REPORT` that does not pin its sha is
unactionable**: verdicts and pushes race. **Between sessions, a relay is never the
authority** — an owner's word arriving through a peer is acted on through the
durable artifact it points at, read on GitHub yourself, or in your own pane.

**Shutdown is two steps, and both are yours.** `STATUS`, verify durability in
GitHub, then `STAND DOWN` — on the agent's own machine, since a verification run
from elsewhere reads *its* working tree and comes back clean regardless.

**Two channels, one criterion: an instruction to a session is a prompt into its
pane; information between sessions is one of the four messages.** So every
assignment, first or later, the answer to a `BLOCKED`, and any slash command are
prompts; the four above stay messages. A prompt is the session's own user turn,
so its hooks run and the relay caveat does not apply; a message is a peer's word,
which is never the authority — which is exactly why an instruction must not
travel as one. **Assigning a sub-issue to a session already running is
`scripts/campaign-assign.py <pane> <sub-issue>`**, and what it refuses and why
is its docstring's. A delegate's *first* brief is delivered by the launch
itself (§ Delegate launch) — the same channel, one step of a different
procedure, so the criterion is unbroken and there is no second rule.

## Merge conditions

**Three conditions gate a merge, and none names a role.** A pull request merges
only when (1) a review has been read **at the sha being merged**, (2) that review
was written by **an agent that did not write the commits**, and (3) the branch
**contains the current `main`** when it merges. Whoever satisfies all three may
merge, the author included; a session that cannot satisfy one may not.

Condition 3 serializes landings: 1 and 2 are each true of a branch *in isolation*,
so containing a `main` that moved means merging it in, that merge is a push, **a
push retires the review**, and the next merge needs a review at the combined sha.
**Conditions 1 and 3 are both enforced by GitHub**, through the same `check` job.
Condition 1's reader is `scripts/check-merge-review.py`: it answers `reviewed`,
`unreviewed` or `unknown` over the sha the run is recorded against and the
comments opening `REVIEW` that name it, and a pull request it could not read
fails the job exactly as one with no review does. `campaign-claim release` reads
it again before deleting a merged claim's ref, the last moment anything here
looks at that merge. **Posting the REVIEW does not turn the check green**: a
comment fires no workflow, so the merge waits on `gh run rerun <id>`.
`--report` asks the same sha from the writer's end — a `REPORT` pinning
anything but it — and **nothing calls that mode**: a session runs it or does
not.
Whether it still bites is `main`'s `required_status_checks.contexts`, and
`.github/workflows/check.yml`'s header says why. **A branch that has never been a
pull request head has no `check` at all**, so fast-forwarding `main` onto a
topic branch is refused — `HTTP 409: Required status check "check" is expected`.
Land through the pull request, whose head sha carries it: merge `main` *into* the
topic branch and resolve there, because the machine-wide no-main-commits guard
blocks the resolution commit the other direction needs.
**Condition 2 has no automatic reader**: one `gh` account signs every session's
merges, so it is held by whoever writes the review saying honestly that it did not
write the code.

**The push that retires a review does not start the next one, and whoever pushed
it asks**, because **a silent wait is indistinguishable from work**: the `REPORT`
names the new sha *and* asks; a session that asked and received nothing stops.

## The fix round

**One full review, at the pull request's final sha; every round after it is
reviewed on its own diff alone.** A full re-review is due at one moment only, a
reconciliation with `main` that needed a hand resolution (§ Concurrency). What a
round costs and how the narrowed brief is written are
`.claude/skills/opening-campaign/references/reviewing.md`, which keeps the
measurement.

**A fix round is: findings on the pull request, one worker, one `REPORT`.** The
worker verifies each finding at the site it names before touching anything.
Follow-ups fold into the same round, whose boundary is the `REPORT` and never a
push, and which ends in one `REPORT` carrying the sha and a per-finding
disposition. **Check that disposition against the findings list mechanically**: a
round claiming "all fixed" without re-running its sweep is what keeps happening.

**A round returning only refinement ends the loop**: findings that are wording, a
number in prose, a name or a claim softened -- with no behavioural defect in
shipped code
and no test that passes with its branch deleted -- are applied in one commit,
reviewed narrowed on that diff, and merged, rather than answered with another
round. A number a check enforces is not prose.

## Review

**Every review runs as an in-process subagent. There is no other way to run one** —
not a default and not the cheapest option, the one mode. It is launched by whoever
wants the merge, the author included: merge condition 2 is on who *writes* it.

**Name the model and the level on every launch**, and they answer different
questions: the model by the **depth** of the change, because a weaker reader
returns "looks fine" on exactly the reasoning that needed a reader; the level by
**how much there is to read**, `medium` being the baseline. **`/code-review`'s
level is the first token after the command and nowhere else**; asking in the
brief sets nothing. A plain brief sets no level mechanically at all — put it
after `at` anyway, since that is what `campaign-token-tally.py` reads for its
own accounting, and say what you mean in the rest of the brief.

**`/code-review` inside a reviewer subagent fans out**, into an orchestrator,
finders and their verifiers, each metered at the launching call's own turns
alone until `campaign-token-tally.py reviews` rolls a fan-out's nested
transcripts into the round that spawned it. PR #255's five fanned rounds cost
close to 5.0M input_new combined, against 57,374-134,222 for one narrowed round
(NOTE on #1, 2026-09-09). **Launch a reviewer with a plain brief, not
`/code-review`, until a fanned round prices under that narrowed-round figure.**

**A session that cannot start a subagent is blocked**: it says so and the pull
request waits, which is never a licence to review some other way. The call itself,
the two knobs in full, the three wrong modes and the shape of a round are
`.claude/skills/opening-campaign/references/reviewing.md`.

## Watching and retiring

**Watch a delegate for `blocked`, not only for gone** — a session at a permission
prompt is still listed and never proceeds, and clearing it is the person's
decision. **Do not trust the absence of that reading either**: a usage-limit menu
reports `idle` too; silence is a liveness question. The folder-trust dialog
also reports `idle` (whether the external-import one does is unmeasured), but
neither is a person's stop — the planner clears both itself
(`opening-campaign`'s `launching.md`).

**Anchor a wait on the run's own marker**, or write the run to a fresh file: an
appended log holds every previous run's success line. **Give a polling loop's
no-evidence verdict a terminal branch** — count the quiet polls, exit reporting
what was observed, and recover the true outcome from a durable source.

**A release compacts the releasing session's own pane**, so a reused worker
does not carry a finished sub-issue's transcript into the next one:
`campaign-claim release` enqueues it, and says so when it could not.

**The session limit is a first-class cause of death, and it kills in batches**;
a planner's own pacing against it is `.claude/skills/assuming-role/references/planner.md`
§ The planner's clock.

Retire finished agents as the campaign runs, not when it closes, and sweep with
all three readings (`campaign-claim live`). A campaign may not close while a
claim is checked out somewhere on this machine, or a session of it is still
listed; nor may a repository be dropped while an agent works one of its
sub-issues. **A listed peer is asked, never killed** — it is the only thing that
can say which claim it holds.

**Delete any local branch whose commits already sit on `main` or the remote**,
whoever created it, and report a branch holding the only copy of its work instead
of deleting it. `campaign-claim release` does the half it can see: after the ref
goes, it deletes that branch's local copies in clones of the repository it was
on, and keeps and reports one whose tip is not on `origin/main`. **It is narrow
on purpose** — a general sweep would take a fresh claim, which points at `main`
until it is worked, and let a second `take` succeed on the same sub-issue.

# Concurrency

One campaign, one machine settles the hard half: no lock is ever judged stale
across a network. It does not settle the campaign's own writes — the binding
serializes neither the campaign issue body nor the shared directory.

**`HEAD` is shared state**: do not assume the shared checkout stays on your
branch, read `git branch --show-current` before each commit, and read a branch's
log for commits you did not author before fast-forwarding it.

**Two open pull requests over the same normative files are normal, and the second
to land reconciles** — **the gate is condition 3**. The merge is a push, so
condition 1 still wants a review at the combined sha; what the reconciliation
decides is that review's *breadth*. A clean auto-merge earns a narrowed one, on
the merge commit's diff alone. A merge that needed a hand resolution earns a full
one, and its brief says it reads the combination: **containment buys attention
from nobody**, and the resolution is where the two branches actually met.

**The named cost: no concurrent cross-machine or cloud work on one campaign.**
Another machine may read a campaign, may file a sub-issue of it, and may open a
different one; none may write this one's campaign issue body or its `bound:` label, claim, or launch
into it. A campaign reaches another machine only by
migration — the price of every staleness question being answerable from one
machine's own disk.

# Authoring a script or a skill

**What a machine can decide here is a check, not a sentence.** `check-tree-shape`
refuses a script with no language extension and a skill directory of the wrong
shape, and `check-rule-readers` refuses a second reader of a rule a script owns,
so none of those is written below. What is left needs judgement.

## Scripts

**Name by who calls it.** A script a flow asks a question is
`<subject>-<question>`; one git or the harness runs unasked is `<verb>-<object>`.
They separate on the call and not on the topic, which is why
`campaign-primitives.py`'s listing groups them that way. **The line under the
shebang is the purpose**, and that listing prints it, so a hand-kept inventory
of scripts is never written. **Usage goes in the file** for a script anything
calls by hand, since a reader should not need this document to call one; a
script only a hook runs has no such caller and owes none.

**Exit status has two conventions here, and a guard takes the one its caller
reads.** A **harness hook** is read by the harness: **0 allows, 2 refuses, and
nothing else blocks** — `check-campaign-claim.py` is the only harness hook here
that refuses; the others announce. A **`pre-commit` guard** is read by git,
which blocks on any non-zero, so it is free to number its own findings and each
says which codes it uses in its docstring; take them from there rather than
from a convention. Both put the reason on stderr, and **a failure message names
only the conditions the code actually read**.

**Keep a guard's own crash apart from its refusal where the caller can act on
the difference**, because a guard that could not run has permitted nothing.
Under git it often cannot be kept apart — an unhandled exception exits 1, which
is also what three of these guards return for a finding — so a guard whose
caller must tell the two apart says so and handles its own errors.

**A check separates *I looked and found nothing* from *I could not look***,
because a stale input reaches it as an absence indistinguishable from a pass.
**Its last-resort handler permits**, so a bug in the check costs one unjudged
call that names itself rather than a wall across everything it guards.

**A script that answers a question prints the answer as a word on stdout**, and
the caller reads the word, never the status. The status says whether the
reading was made at all, and one script may need more than one code to say so:
`check-commit-claim.py --is-claim` answers `claim`, `no-claim` or `unknown` and
gives each its own status, because a caller about to push must tell an answered
no from a question it could not read.

**A case asserting an exit status is satisfied by every other cause that shares
it**, a crash and a refusal alike, so assert on what the run said: the diagnosis,
and the finding that must be absent. **Break each branch separately, not the
feature** — disable one alternation, flag or code path at a time, require a named
case to fail for each, and assert on what the mutation changes rather than on a
neighbour it leaves alone.

**Scope a dedupe or idempotency check to unsettled records only**, so a failed
record stays repeatable: a key naming what was asked for rather than which
attempt repeats whenever its subject returns to a state it has held.

Three harness facts, each of which makes a hook enforce nothing when it is
missed:

- **Exit 2 blocks only on events that can block.** On `PostToolUse`,
  `PermissionRequest`, `SessionStart`, `Notification` and their kind it prints
  and execution continues.
- **On `SessionStart`, `UserPromptSubmit` and their kind stdout is injected into
  the model's context, and only on exit 0.** A script that announces something
  always exits 0, or the announcement disappears.
- **A hook needing more than allow-or-refuse exits 0 and prints JSON under
  `hookSpecificOutput`**, which then decides. Exit 2 overrides that JSON, so
  never write both.

**One script answers one question.** A sequence with judgement in it is a skill;
a sequence with no judgement is a script; a judgement with no sequence is a
sentence. Prefer parsing formal syntax over prose: a claim extracted from a
declaration cannot be forged by editing a comment, and something deleted leaves
the extraction on its own.

**Default to a skill's own `scripts/`**, so the script is deleted with the
procedure that reaches it. The top-level `scripts/` is for what has no owning
skill: a script small enough to need no procedure around it, one a hook runs,
one CI runs, and one two skills call — whose alternative is a copy.

**Handle your own errors and assume no tool is installed.** A script that dies
on a missing binary reports a stack trace where it owed the caller a reading.

## Skills

**`description` carries the routing words in its first line**: one sentence of
what the skill does, then a `Use when …` clause naming the situations and the
words a person would actually type, third person. The listing truncates long
entries and drops the least-used first, so a trigger buried at the end can
disappear before the skill is ever considered. Add a `Not for …` clause when a
sibling can claim the same request — negative scope stops over-triggering, more
positive description does not. **`name` is the directory name**, and a
model-loaded skill takes the gerund form, verb plus object; a user-typed one
takes the voice of its pool.

**Zero to three body sections**, noun phrases, ordered so the reader meets each
one when it applies, and shaped to their material: a subject that reduces to a
small rule gets the rule; one thick with exceptions gets a few worked examples;
a term the skill encapsulates gets its definition; distinct situations get a
catalogue, the situation in one column and the action it selects in the next. A
row selecting a whole mode links a reference holding that mode — the row keeps
the selector, the reference keeps the body — and **a reference nothing names is
never read**. One over 100 lines opens with a summary or a table of contents,
because an unsummarized file gets previewed instead of read.

**State a finished state as a predicate the agent can check** ("every index
entry resolves to a file"), never an adjective. Name the failure modes that
raise no error. Match specificity to the cost of a wrong step: a narrow path
with real hazards gets exact instructions, open work gets direction and the
criteria that judge it.

**Write only what the agent cannot derive** — house conventions, defaults that
surprise, values that must match another file. **Cut a rule before you shorten
it**, since compliance falls with the number of rules held at once. Plain
imperative sentences, no capitals and no `MUST`: emphasis buys over-triggering,
not compliance. Keep a prohibition as a prohibition. One term per concept, no
dates or versions, no constant without the reason for its value. An example that
repeats its instruction anchors the agent to the sample instead of the rule.

**The body loads once and stays for the session**, so it holds standing
instructions and not one-time steps; compaction keeps only the opening of a
re-attached body, so a rule that must survive a long session sits near the top.
An unused skill still costs its description every turn: a fact belongs in this
file, and only a procedure earns a skill.

**`.claude/skills/herdr/` is vendored**, and the first line of its body, under
the frontmatter, names the upstream and the tag. An upgrade replaces the whole
file; any edit breaks the identity that makes that replacement safe.
