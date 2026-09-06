---
name: closing-campaign
description: Closes a campaign in the campaign-base repository and deletes its directory. Use when a person says a campaign is finished, done, over, or wrapped up, or asks to close, retire, archive, or clean up a campaign or its directory — gating the close on the binding, on live agents, on work that exists only on this machine, and on every open sub-issue having a disposition, then syncing the README into the campaign issue. Not for closing a single sub-issue or retiring one repository agent; not for opening or scaffolding a campaign, which is opening-campaign.
---

# Closing a campaign

Delete a campaign directory only after everything in it also exists somewhere
else.

Finished when `gh issue view <N> -R kalaluthien/campaign-base --json state`
reports `CLOSED`, `$CAMPAIGN_DIR` does not exist, and every step's `Holds when`
line held when that step ran — `grep '^Holds when' SKILL.md` is the whole list.

## Procedure

Each gate is cheaper than the next and step 5 is irreversible, so the order is
load-bearing. Run 0–4 without asking, except step 3's disposition, which is the
person's choice; run 5 only on explicit confirmation. Why each guard is shaped
this way: `references/rationale.md`.

### 0. Bind the campaign, once

**The ID first**: every step from 3 on reads `$N`. Take it from the person, or
match it among the open campaign issues and say which.

```sh
BASE=$(cd "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")" && pwd -P)
"$BASE"/scripts/campaign-tracker.py campaign-issues
"$BASE"/scripts/campaign-tracker.py bound "$N"   # here | elsewhere <machine> | unbound
```

`here` — carry on. Anything else, a failed read included, refuses the close:
another machine, refuse naming both and say nothing was closed; unbound, which is
not consent either, let the person bind it here or close it from the machine that
has been working it.

**Then the directory** — none yet is normal; take it first through
`opening-campaign`'s "No directory at all" arrival, **steps 2 and 4**, and set
`TOOK_IT_HERE=1`, on which steps 1 and 2 report not-applicable rather than a
pass. Bind `$CAMPAIGN_DIR` absolute and never rebuild it: steps 1 and 5 fail
silently on a relative value.

```sh
CAMPAIGN_DIR=$(cd "$BASE/$SLUG" && pwd -P)
[ "$(dirname "$CAMPAIGN_DIR")" = "$BASE" ] || echo "REFUSE: not a direct child of $BASE"
[ -f "$CAMPAIGN_DIR/.campaign" ] || echo "REFUSE: no .campaign marker, so this is not a campaign directory"
```

Stop on either. **The marker and not the name**: since #181 a campaign directory
is named for its slug, which is a word, and the `-YYMMDD` suffix that used to say
so is gone. A directory whose marker was swept is one `rm -rf` away from the
base's own `scripts/`.

Holds when: the campaign issue carries one `bound:` label naming this machine, and
`$CAMPAIGN_DIR` is absolute, a direct child of the base, and named
`<slug>`, carrying a `.campaign` marker.

### 1. Refuse while a claim is occupied or a session is still running

**If `TOOK_IT_HERE` is set, this step and step 2 are not applicable — report
that, not a pass**; run them anyway, they cost one command. **A peer leaves the
campaign by fact**: it stops its pane, or leaves the base tree. A rename alone
does not, unless the new name is another campaign's; a name that says nothing
still counts while the session sits under the base root.
There is nothing to say and nothing to post, and a peer still listed is asked,
not killed. One reader makes all three readings — the remote's claim refs, where
each is checked out, and herdr's liveness:

```sh
"$BASE/scripts/campaign-claim.py" live "$N"
```

Read the words, never the exit status, and refuse on any of:

- a non-zero exit — one of the readings did not happen, an unreadable repository
  included;
- any row under **claims checked out on this machine** — a workspace is standing
  in a claim;
- any row under **claims checked out nowhere on this machine** that does NOT
  read `landed as #<pr>` — a claim that outlived its workspace, or one held on a
  machine this cannot see. **`landed` blocks nothing**: its work is on `main`
  and only the ref survived, which is the ordinary state of this tracker
  (`delete_branch_on_merge` is off), and refusing on the whole group made the
  close unpassable — measured on campaign #1, whose `campaign-1/154-…` landed as
  #162 months ago. A row reading `MERGE UNREADABLE` refuses like any other
  failed reading;
- any row under **live sessions of campaign-N**.

For each row of the last kind, send `STATUS`, then `STAND DOWN`, to every such
session (`AGENTS.md` § The four messages), not only the first, and re-run this
step once its pane is gone. **`live` cannot say which session holds which claim
and does not pretend to** — herdr reports where a session started, not the
worktree it works in — so the sessions it lists are exactly who to ask
(`references/rationale.md`). This skill never kills an agent. No rows still
leaves two cases step 2 is what catches.

Holds when: `campaign-claim live` exited 0 and printed no row of the three
refusing kinds — or `TOOK_IT_HERE` is set and this step reported not applicable
rather than passed.

### 2. Refuse while work exists only on this machine

Deleting the directory destroys it and nothing recovers it. One reader answers
the whole question, over this campaign's branches and worktrees, the base's
working tree, and every checkout under `repos/`. Do not re-derive any of it here.

```sh
"$BASE/scripts/campaign-local-work.py" "$N" "$CAMPAIGN_DIR" >| /tmp/local-work-$N
cat /tmp/local-work-$N
```

**Exit 1 is the reading having failed, not a clean tree**: print the `-- REFUSE:`
line it ends on, stop, and conclude nothing.

| in the output | what it means |
| --- | --- |
| an unmarked row | counted, and one counted row refuses: *nothing was deleted; clear every counted row, or say to discard it, then re-run* |
| a `~` row | named, not counted — pushed, landed over a squash merge, or a clean worktree |
| `-- REPORT: … could not read` | a check that did not run, counted apart and refusing on its own (`… and <n> place(s) went unread; NOT clear`). Read it by hand, then re-run |
| any other `-- REPORT:` | for the person; blocks nothing |
| the last line | the verdict, and the only pass is `0 item(s) … clear`. Zero counted rows is not by itself one |

Holds when: `campaign-local-work` exited 0 over this campaign and this directory
and its last line read clear, every counted row having been pushed, merged, or
discarded on the person's word, and every unread place read by hand and either
emptied or reported first. `NOT clear` with no counted row left names places it
could not reach: reach them, never read past the verdict.

### 3. Settle or dispose of every open sub-issue

**First, confirm `$N` is a campaign issue**, so step 5 does not close somebody's sub-issue.
Want `campaign` among the labels and `-` for the parent; anything else, stop and
say which issue `$N` actually is.

```sh
gh issue view "$N" -R kalaluthien/campaign-base --json labels,parent \
  -q '"\([.labels[].name] | join(","))\t\(.parent.number // "-")"'
"$BASE/scripts/campaign-tracker.py" settlement "$N" >| /tmp/settlement-$N
cat /tmp/settlement-$N
```

That prints one row per sub-issue, then whether the campaign is closable. Read the
note beside a `dropped` row before repeating the word.

**Every `open` row gets a disposition, and this step refuses without one** — a
campaign may close over unfinished work, never over *unexamined* work. One of
three per row, the person's choice:

| disposition | the act | what the row becomes |
| --- | --- | --- |
| `finish` | do the work, land the pull request, close the issue | `complete` |
| `not-planned` | `gh issue close <issue> -R <repo> --reason "not planned" --comment "<why>"` | `dropped` |
| `reparent` | `gh issue edit <issue> -R <repo> --parent <URL of the inheriting campaign issue>` | gone from this index — the sub-issue link is prunable |

Write one line per open row — `<owner/repo>#<issue>  <verb>  <reason or target>`
— then validate it against the settlement output by machine. A `<` line is an
open sub-issue with no disposition; a `>` line is stale, so re-run the script.

```sh
DISPOSITIONS=/tmp/dispositions-$N        # write it here, one line per open row
awk '$1 ~ /#[0-9]+$/ && $2 == "open" { print $1 }' /tmp/settlement-$N | sort >| /tmp/open-$N
awk 'NF { print $1 }' "$DISPOSITIONS" | sort >| /tmp/disposed-$N
command diff /tmp/open-$N /tmp/disposed-$N && echo "every open sub-issue has a disposition"
awk 'NF && $2 !~ /^(finish|not-planned|reparent)$/ { print "REFUSE: unknown disposition: " $0 }' "$DISPOSITIONS"
awk 'NF && $2 != "finish" && NF < 3 { print "REFUSE: no reason or target: " $0 }' "$DISPOSITIONS"
```

The refusal says nothing was closed, gives the count, lists `<owner/repo>#<issue>
<title>` per undisposed row, and says each needs `finish`, `not-planned` with a
reason, or `reparent` with the campaign issue that inherits it.

**Carry them out, then read the same script again** — the dispositions are claims
until GitHub shows them.

```sh
"$BASE/scripts/campaign-tracker.py" settlement "$N" >| /tmp/settlement-after-$N
cat /tmp/settlement-after-$N
grep -q '; closable$' /tmp/settlement-after-$N ||
  grep -q 'the index is empty' /tmp/settlement-after-$N ||
  echo "REFUSE: not closable -- read the NOT closable line for which cause"
```

`; closable$`, not `closable` — the failing line ends `NOT closable:` and then
names its cause. Two are possible and they want different repairs: `open
sub-issues remain` is work to finish, while `N sub-issue(s) could not be read` is a
reading to get back, an `unread` row whose issue or whose closing pull request
this account cannot see. Neither settles anything. The empty-index line is the
other accepted reading. A `-- REPORT:` line
about nested sub-issues isn't covered here: a sub-issue that is itself a campaign issue
hides its own members, so run the script on it too.

Holds when: `campaign-tracker settlement` reads every sub-issue in the campaign issue's
index as settled or moved to another campaign issue, each open one having been given a
named disposition and had that act carried out first.

### 4. Validate the README, compare, then overwrite the campaign issue body

This is the only sanctioned write of the campaign issue body, and it runs mid-campaign
too, when a repository is added to `## Repos`; nothing in step 3 edits the body.
The README and the body are the same template filled in
(`.claude/skills/opening-campaign/assets/README.md`), so the sync is an overwrite
with nothing to merge — a compose step is where the repository index gets
silently dropped. Validate first.

```sh
README="$CAMPAIGN_DIR/README.md"
rm -f /tmp/repos-before /tmp/repos-after
"$BASE/scripts/campaign-repos.py" "$README" >| /tmp/repos-before.tmp &&
  mv /tmp/repos-before.tmp /tmp/repos-before ||
  { rm -f /tmp/repos-before.tmp
    echo "REFUSE: the ## Repos list did not read; nothing was written"; }
```

`scripts/campaign-repos.py` is the one reader of that list. Stop on a non-zero exit;
read empty output as a repo-less campaign, not a failure. Keep the
`.tmp`-then-`mv` and the leading `rm -f`, or a failed read leaves what a
legitimate `- none` leaves.

**Then compare before you write** — `runtime/campaign-issue-body-derived.md` is the body
as it read when this README was derived; re-read the body now and require the two
to match, because without the comparison one write silently discards another.

```sh
DERIVED="$CAMPAIGN_DIR/runtime/campaign-issue-body-derived.md"
[ -f "$DERIVED" ] || echo "REFUSE: no runtime/campaign-issue-body-derived.md to compare against"
gh issue view "$N" -R kalaluthien/campaign-base --json body -q .body >| /tmp/body-now
command diff -u "$DERIVED" /tmp/body-now && echo "the body has not moved; safe to write"
```

A diff refuses the write, as does a missing derived copy — without it "has the
body moved?" has no answer. Say nothing was written, then repair the way
`references/rationale.md` says: read the diff for what the other writer did, name
the cause among its three, fold the changes into the README, refresh the derived
copy from `/tmp/body-now`, and re-run.

Only then overwrite, and refresh **both** the README and the derived copy from
the read-back, so the next write compares read-back against read-back. The round
trip is not byte-stable -- a body sent with one trailing newline comes back with
two -- so the body compare below strips trailing newlines on both sides; `gh
issue view --json body` is the canonical form, never the file that was sent.

```sh
gh issue edit "$N" -R kalaluthien/campaign-base --body-file "$README"
gh issue view "$N" -R kalaluthien/campaign-base --json body -q .body >| /tmp/body-after
"$BASE/scripts/campaign-repos.py" /tmp/body-after >| /tmp/repos-after.tmp &&
  mv /tmp/repos-after.tmp /tmp/repos-after ||
  { rm -f /tmp/repos-after.tmp
    echo "REFUSE: the body GitHub stored does not read; the index may be lost"; }
cmp -s /tmp/repos-before /tmp/repos-after && echo "index survived" &&
  command diff <(printf '%s\n' "$(cat "$README")") <(printf '%s\n' "$(cat /tmp/body-after)") &&
  echo "body survived" &&
  cp /tmp/body-after "$README" &&
  cp /tmp/body-after "$DERIVED"
```

Either compare failing: say so and stop before step 5, while the README still
exists. `"$(cat ...)"` drops every trailing newline and `printf` puts one back,
which is the whole normalisation; anything else that differs was lost in the
write.

Holds when: the campaign issue body is this campaign's README, `## Repos` list
included, compared against `runtime/campaign-issue-body-derived.md` before it was written
and read back through `campaign-repos` after.

### 5. Say you are closing, then close, then delete the directory

Only after the person confirms. **Say it on the campaign issue first, and read who
answers** — the campaign issue is the one place a machine working this campaign
against its `bound:` label could answer. Say what the delete will destroy in the
same comment.

```sh
HOST=$(hostname -s)
[ -n "${CAMPAIGN_DIR-}" ] ||
  { echo "REFUSE: CAMPAIGN_DIR was never bound; step 0 did not run"; exit 1; }
[ -d "$CAMPAIGN_DIR/runtime" ] ||
  { echo "REFUSE: $CAMPAIGN_DIR holds no runtime/; not a campaign directory"; exit 1; }
LEFTOVERS=$(find "$CAMPAIGN_DIR" -mindepth 1 \
  \( -path "$CAMPAIGN_DIR/runtime" -o -path "$CAMPAIGN_DIR/repos" \) -prune -o -print \
  | sed "s|^$CAMPAIGN_DIR/||" | sort \
  | grep . || echo "no entries outside runtime/ and repos/")
BODY=$(printf 'Closing campaign #%s from %s. Say so here if you are still in it.\n\nThe delete destroys these entries under the campaign directory, `runtime/` and `repos/` excluded:\n\n```\n%s\n```\n' \
  "$N" "$HOST" "$LEFTOVERS")
gh issue comment "$N" -R kalaluthien/campaign-base --body "$BODY"
gh issue view "$N" -R kalaluthien/campaign-base --comments
```

**A directory and the file inside it both appear, and that is correct** —
`scripts/` ships a `.gitkeep`. Do not narrow the `find` to `-type f`: `rm -rf`
destroys files, directories and symlinks alike. **Read the listing knowing what
is on it**: `AGENTS.md`, `CLAUDE.md`, `README.md` and `scripts/` are the
scaffold, so skip those rows. It is a record, not a to-do — anything wanted out
of the tree is saved before close. A peer's note that it is working or closing:
stop and name it.

**Release the campaign's own claim refs on the base** — an unlanded sub-issue
leaves its branch outliving the campaign; step 3 makes this sighted.

```sh
gh api "repos/kalaluthien/campaign-base/git/matching-refs/heads/campaign-$N/" \
  --jq '.[] | "\(.ref)\t\(.object.sha)"' |
while IFS="$(printf '\t')" read -r REF SHA; do
  AHEAD=$(gh api "repos/kalaluthien/campaign-base/compare/main...$SHA" --jq .ahead_by) || exit 1
  if [ "$AHEAD" = 0 ]; then
    gh api -X DELETE "repos/kalaluthien/campaign-base/git/$REF" && echo "released $REF"
  else
    echo "REFUSE-ROW: $REF holds $AHEAD commit(s) beyond main — push a PR or say to discard"
  fi
done
```

**No `--paginate`** — `git/matching-refs` returns every ref in one response
(`references/gotchas.md`); the flag would claim otherwise. **Ancestry, not
equality**: `main` moves after the claim, so `ahead_by` catches what a sha
comparison would miss. Print a row that holds commits and never delete it; member
repositories' refs are released by their pull request merge.

Then close, in this order — the issue first, then a check that nobody else on
this machine is in the directory, then the delete of the bound path itself, not a
path retyped here, not its parent, not a wildcard.

```sh
gh issue close "$N" -R kalaluthien/campaign-base --comment "Campaign closed."
lsof +D "$CAMPAIGN_DIR" 2>/dev/null | tail -n +2
ls -A "$CAMPAIGN_DIR"
rm -rf -- "$CAMPAIGN_DIR"
```

Any `lsof` rows: name the processes and stop. It sees an open file, not an idle
session, so an empty result is weak evidence, paired with the announcement above
rather than trusted alone. `runtime/` goes with the delete; say so.

Holds when: the closing comment carries the listing taken immediately before the
delete — every entry under the directory outside `runtime/` and `repos/`, files
and directories and symlinks alike, because `rm -rf` destroys all of them — and
every `<slug>/` claim ref still sitting at `origin/main` is released, any
that holds commits reported and not deleted.

## Gotchas

The probes and the failures behind these: `references/gotchas.md`.

- An unmatched `repos/*/` glob fails silently in both shells, which is why no
  step here globs; `scripts/campaign-local-work.py` enumerates instead.
- `dropped` covers four closes and its note says which; only `not planned` is
  abandonment, so quote the note, not the word.
- `state_reason` is lowercase from `gh api` and uppercase from `gh issue list
  --json stateReason`, and the wrong one reads every sub-issue as unsettled.
- `set -- $var` does not word-split in zsh; split with `${spec%%:*}` and
  `${spec##*:}` instead.
- `diff` is shadowed in a Claude Code shell on this machine. Write `command diff`.
- Every session of a campaign shares its one directory, so this delete may hit a
  peer's live workspace — the checked-out claims catch that in step 1,
  `campaign-local-work` in step 2; a herdr `cwd` gate alone cannot, since a
  session working from the base root has the base as its `cwd`.
