---
name: opening-campaign
description: Opens a campaign in the campaign-base repository, or joins one already open. Use when a person says to open, start, kick off, set up, or join a campaign, or when a request will outlive the session it arrived in — files the campaign issue, binds it to this machine, scaffolds its directory, acquires the member repositories, and files the first sub-issues. Not for a request that finishes in the session it arrived in, not for closing a campaign, and not for a later sub-issue of a campaign already scaffolded here.
---

# Opening a campaign

Finished when all of these hold:

- An open issue in `kalaluthien/campaign-base` carries the label `campaign`,
  no parent, and the sections of the campaign issue template `assets/README.md`, with a
  `## Repos` list that `scripts/campaign-repos.py` reads and exits 0 on.
- The campaign issue carries exactly one `bound:` label, and it names this machine.
- `<slug>-<YYMMDD>/` exists at the base root and holds `AGENTS.md`,
  `CLAUDE.md`, `scripts/`, `runtime/repos`, and a `README.md` and `runtime/campaign-issue-body-derived.md` that
  each hold the campaign issue body as `gh issue view --json body` returns it --
  the read-back is the canonical form, because the round trip through `gh` is
  not byte-stable (a body sent with one trailing newline comes back with two).
- Every line `scripts/campaign-repos.py` prints resolves to a checkout at
  `<campaign>/repos/<name>/` — vacuous under `- none`, where it prints nothing.
- At least one sub-issue of the campaign issue is filed, and the reply names
  it along with the campaign ID, the directory and the campaign issue URL.

## Procedure

Ordered: the campaign issue number is the campaign ID, so nothing that needs the ID
runs before step 3. Why each guard is shaped this way: `references/rationale.md`.

### 1. Read the binding, then find the directory

A campaign that does not exist yet goes straight to step 2. Otherwise read the
binding before anything else about it, because joining one bound elsewhere is the
mistake this read exists to stop.

```sh
BASE=$(cd "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")" && pwd -P)
"$BASE"/scripts/campaign-tracker.py bound <N>    # here | elsewhere <machine> | unbound
```

`here` — carry on, and that one read is the whole membership question. Anything
else, a failed read included, stops you: file nothing, scaffold nothing, launch
nothing. Name the machine that holds it; on `unbound`, ask before binding it
here, since having its directory here is not what binds it.

Then find out whether this machine has a directory. "Already scaffolded" is a
fact about a directory, not about the campaign.

```sh
ls -d "$BASE"/*-[0-9][0-9][0-9][0-9][0-9][0-9]/ 2>/dev/null
CAMPAIGN=$(cd "$BASE/<the directory that matched>" && pwd -P)
```

A directory whose `README.md` names this campaign is the one to work in, peers
working in it too being the normal state.

**No directory at all** — name this session first (the last block of step 3,
with the ID the campaign issue already has), then run steps 2, 4 and 5 with the ID and
body from the campaign issue, and skip the rest of step 3, which exists only to
mint an ID it already has. The directory holds no claim and no brief since #176,
so it is a cache and not a precondition; scaffold it anyway, because `repos/` and
the README copy live there. Step 2 still runs, because neither the slug nor the kind is
recoverable from GitHub; say which kind you picked.

### 2. Name it and pick its kind

- **Slug** — kebab-case, meaningful, no date; step 4 appends the date.
- **Title** — the display name, in the requester's own words, not yours.
- **Kind** — which `assets/agents/*.md` becomes the campaign's `AGENTS.md`.

| the campaign exists to | kind |
| --- | --- |
| answer an open question | `research` |
| measure or audit something that already runs | `analysis` |
| find out whether an approach can work at all | `prototyping` |
| move a working system from one form to another | `migration` |

With a person in the conversation, propose all three in one message and wait;
from a sub-issue with nobody waiting, read all three from its body. Either
way state them in the reply, so each costs one line to veto — an unstated kind is
a wrong set of principles for every delegate.

### 3. File the campaign issue

**Survey again, in the same breath as the create.** The routing gate's survey is
minutes old, and two sessions that each surveyed before either filed both file,
so one scope gets two campaigns. Nothing closes that window, because a campaign
that does not exist yet is bound to nobody: if two campaign issues appear anyway, close
one as `not planned` and say which survived.

```sh
"$BASE"/scripts/campaign-tracker.py campaign-issues
gh issue create -R kalaluthien/campaign-base \
  --label campaign --title "<title>" --body-file <path>
```

**Fill the campaign issue template** for the body, `assets/README.md` in this skill — its
sections, each placeholder replaced, and no others. Write Scope to be matched
against a request by the routing gate. The body carries no decomposition
(`AGENTS.md` § The campaign issue body); step 6 files the first sub-issues instead.

**Read the label back before scaffolding anything**, because a campaign issue filed
without it is invisible to every later survey and the next session opens a second
campaign over the same scope.

```sh
gh issue view <N> -R kalaluthien/campaign-base --json labels,parent
```

Want `campaign` among `labels` and `parent` null. A non-null `parent` means you
filed a sub-issue, not a campaign issue — `gh issue edit <N> --remove-parent` first.

**Then bind it to this machine, in the same step** — everything after is a write
or a launch, both gated on the binding. One of the two occasions a session binds,
read back as `AGENTS.md` § The binding says.

```sh
"$BASE/scripts/campaign-tracker.py" bind <N>
"$BASE/scripts/campaign-tracker.py" bound <N>     # want: here
```

**Then name this session, now that the number exists.** A session that opened
this campaign while named for another keeps that name until something sets it,
and nothing later does: every peer message and every `live` sweep would then
read it as another campaign's. `<role>` is `planner` when this session
will file the sub-issues and hand them out, `worker` when it will work the
one it files (`AGENTS.md` § The binding); `<n>` is the next free one among the
sessions `herdr agent list` shows for this campaign, counted as `AGENTS.md`
§ The session name says.

```sh
test "${HERDR_ENV:-}" = 1 &&
  "$BASE/scripts/campaign-name-session.py" "$HERDR_PANE_ID" campaign-<N>-<role>-<n>
```

Read what it reports applied, then confirm with `ListAgents` that the harness
name is `campaign-<N>-<role>-<n>` before step 4 begins. The caller's own
rename is the one most likely to need a person, so a `FAILED` line is a stop:
say so, and do not go on under the old name. **There is no second reader any
more**: `campaign-claim take` used to refuse a `--name` from another campaign,
and with the record gone there is nowhere to write a name and nothing to check
it against. What a stale name now costs is a close: `campaign-claim live`
believes a name that says whose campaign a session is of, so a session still
carrying another campaign's name is skipped by that campaign's close gate
wherever it sits. Set it here, and read back what `ListAgents` reports.

### 4. Scaffold the directory

Address every path below through `$BASE` from step 1: a later step runs with
a different working directory. Reject a slug that is not plain kebab-case before
it reaches a path — a slug comes from a person and lands in a `cp` destination,
so one containing `../` writes outside the base.

```sh
printf '%s' "<slug>" | grep -Eq '^[a-z0-9]+(-[a-z0-9]+)*$'
CAMPAIGN="$BASE/<slug>-$(date +%y%m%d)"
if mkdir "$CAMPAIGN" 2>/dev/null; then
  cp -R <skill>/assets/. "$CAMPAIGN"/
else
  echo "exists: read $CAMPAIGN/README.md before writing anything in it"
fi
```

**The `mkdir` without `-p` is the gate**, and the only atomic one here: two
sessions arriving with the same slug on the same day cannot both create the tree.
A `[ -e ]` test before the copy is a read and a write with a gap between, and
`cp -R` over a live campaign exits 0 while replacing a filled-in `README.md`
with placeholders.

Being told is not an error. Read `$CAMPAIGN/README.md`: the same campaign — work
in that directory and skip to step 5, which is safe to re-run; a different
campaign, or unreadable — stop and ask.

Then finish it:

- Move the chosen `agents/<kind>.md` to `AGENTS.md` and delete `agents/`.
- Delete `sub-issue.md`. It is filled once *per sub-issue* from the skill's own
  copy, so the top-level copy has no reader and a stale one could be filled long
  after.
- Everything else the copy brought stays.
- Overwrite `README.md` with the campaign issue body, which replaces every
  placeholder at once — the close-time sync run backwards:

  ```sh
  gh issue view <N> -R kalaluthien/campaign-base --json body --jq .body \
    >| "$CAMPAIGN/README.md"
  cp "$CAMPAIGN/README.md" "$CAMPAIGN/runtime/campaign-issue-body-derived.md"
  "$BASE/scripts/campaign-repos.py" "$CAMPAIGN/README.md" \
    >| "$CAMPAIGN/runtime/repos.tmp" &&
    mv "$CAMPAIGN/runtime/repos.tmp" "$CAMPAIGN/runtime/repos" ||
    { rm -f "$CAMPAIGN/runtime/repos.tmp"
      echo "REFUSE: the ## Repos list did not read; runtime/repos was not written"; }
  ```

  A non-zero exit is a body never filled in, or a list the reader refuses; stop
  and fix the body. Keep the `.tmp`-then-`mv`, and keep step 5 reading that file
  rather than a pipe, so a failed read cannot look like a deliberate `- none`.
  `>|`, not `>`.
- **Keep `runtime/campaign-issue-body-derived.md`**, refreshed after every re-derivation
  and every sync — the only thing that can later answer "has the body moved?",
  and `closing-campaign` step 4 refuses without it.

### 5. Acquire the member repositories

Yours whenever you launch a delegate. For each line `scripts/campaign-repos.py`
printed in step 4, by absolute path — step 4 has just created an empty
`$CAMPAIGN/scripts/`, so a relative path resolves there and fails.

```sh
ACQUIRE="$BASE/.claude/skills/opening-campaign/scripts/acquire-repo.sh"
while read -r REPO; do
  "$ACQUIRE" "$REPO" "$CAMPAIGN/repos/${REPO##*/}"
done < "$CAMPAIGN/runtime/repos"
```

`- none` gets no special case: the loop runs zero times and `repos/` is never
created. Say in the reply that no repository was acquired, so a campaign that was
*meant* to have some is one line to correct.

Safe to re-run; do not clone by hand, and do not read the script — its interface
is the contract. **No `--branch` here**: a re-run with one would switch a shared
checkout under a delegate already working in it.

### 6. File the first sub-issues, then report

File the sub-issues the opening already implies, a campaign whose scope is one
sub-issue filing one. Then report the campaign ID, the directory path, the campaign issue
issue URL, and the sub-issues filed, saying of the first whether you are doing it
here or handing it to a repository agent.

### Filing a sub-issue

Step 6's sub-issues and one the routing gate sent here to join are filed and
claimed the same way. File it as `AGENTS.md` § Sub-issues says. **Filing needs no
binding**: any session anywhere may file a sub-issue of any campaign, since the
link is a record and not a claim (`AGENTS.md` § The binding); the claim below is
what the binding gates. **The issue number
is half the branch name, and the branch is the claim**, so the claim cannot be
cut until the issue exists and this is the step that mints it.

```sh
"$BASE/scripts/campaign-claim.py" take <N> <issue> <topic> --repo <owner/repo>
```

One call cuts the branch from the named remote and writes nothing else: **the
ref is the whole claim**. Exit 3 is the ref already existing, which is the
sub-issue being taken: read who is standing in it with `campaign-claim live <N>`,
and do not push past it. **When a delegate will do the work** the same one call
does it, before the launch — the delegate checks the branch out when it starts,
and that checkout is what attributes the claim to its workspace. A repo-less
campaign claims on the base all the same — `--repo` defaults there. Give the
branch a local checkout only where the sub-issue has one:

```sh
B=campaign-<N>/<issue>-<topic>
git -C "$CAMPAIGN/repos/<name>" fetch origin "$B" &&
  git -C "$CAMPAIGN/repos/<name>" switch -c "$B" --track "origin/$B"
```

**A repository the campaign issue's `## Repos` list does not name** is a scope change, so
it syncs at that moment rather than at the close: edit the campaign `README.md`,
re-run the reader over it as step 4 does, sync with `closing-campaign` step 4's
compare-then-write in full, then acquire it as in step 5. The first repository
**replaces** `- none`, and `campaign-repos` refuses a list mixing the two.

## Gotchas

The probes and the failures behind these: `references/gotchas.md`.

- A delegate does not pick up the campaign `AGENTS.md` from its parent
  directories. It reaches one as `CLAUDE.local.md` written into its clone and
  excluded in `.git/info/exclude` — a file in its own cwd, so nothing has to
  prove it arrived. It sits beside the repository's own conventions: adding a
  principle is free, contradicting one hands the delegate a conflict it
  resolves without telling you.
- `gh issue create` without `--parent` succeeds, returning a live issue in no
  campaign; only a later listing coming back short shows anything is wrong.
- This machine's zsh sets `noclobber` and leaves `APPEND_CREATE` unset, so plain
  `>` onto an existing file and plain `>>` onto a missing one fail without
  stopping the steps around them. Write `>|` and `>>|`.
