# Why the close is shaped this way

One section per step of `SKILL.md`. Read a section when a guard there looks
arbitrary, or when you are about to change it.

## Step 0 — binding

`$CAMPAIGN_DIR` is bound once, absolute, because two later steps fail silently on
a relative value: step 1 compares it against herdr's absolute `cwd`, so a
relative value matches nothing and the refusal passes having found nothing; step
5 then deletes relative to whatever directory the session happens to hold.

It is always bound to a real directory. A campaign bound here with no directory
is scaffolded first — `opening-campaign` steps 2 and 4, step 2 being where the
slug and kind step 4 needs are chosen — because `repos/` and the README copy have
no other home. Unset or empty means step 0 never ran, which is the wrong-cwd
hazard the guard in step 5 exists for.

**What the gates are worth on that path, which is not what "restored" would
claim.** When step 0 creates the tree, step 1 and step 2 then read a directory
seconds old: no herdr `cwd` can be under it, no worktree of it exists, and there
is nothing uncommitted in it. They cannot fail, so they must not be reported as
passed. The soundness argument is that they have nothing to find: an agent of
this campaign is launched into `<campaign>/repos/<repo>/` and a session working
one of its sub-issues checks the claim out under the same tree, and both need a
directory that did not exist — so a campaign never worked on this machine can
have no local worker to miss.
The residue is the one case that breaks the premise: a directory that existed
here and was deleted by hand without a close, leaving agents alive with their
tree gone. Nothing local can see that, and step 5's announcement on the campaign issue
is what covers it. Step 1 reports "not applicable" on this path rather than
"passed", so a reader is never told a vacuous gate held.

## Step 1 — the agents

There is no holder to read. The holding session is retired (`AGENTS.md`
§ The binding), so this step asks what is live under the tree and whether it
has agreed the campaign is over, and it asks `campaign-claim live` because
either of its first two readings alone is blind to half the workers.

**The workspace is the evidence, and leaving is a fact rather than a claim.**
A peer used to pass this gate by posting `STOOD DOWN <name> <session-id>` on the
campaign issue, because a pane under the tree says a shell was opened there and
nothing about whether the session in it is done. #176 removed the comment: what
the gate reads now is whether a claim branch is **checked out** anywhere on this
machine, which is the same durability the comment had — a checkout survives a
restart and a rename exactly as a comment does — with nothing to write and
nothing to forget to write. A peer finishes by stopping its pane or renaming off
`campaign-<N>-*`, both facts. `spec/campaign/orchestration/system.als` carries
the reading as `holder`.

A claim checked out in a workspace whose session is gone reads as occupied. That
is the safe direction to be wrong in here: leaving a claim standing costs a
question, deleting a live session's tree costs its work.

**`live` cannot say which session holds which claim, and the gate does not need
it to.** herdr reports where a session was *started*, a worker on the base
works in a worktree, and that worktree's owning repository may not even be the
clone the session sits in — measured 2026-09-04, and it is why attribution names
a workspace. The gate asks two existence questions, "is any claim occupied" and
"is any session of this campaign still running", and both are answerable. **Do
not repair the gap by matching `ListAgents` names against branches**: a name and
a branch are two strings on purpose (`AGENTS.md` § The session name), a name
carries no sub-issue at all, and a test built on the string finds whatever
happens to match and misses the rest. Ask the session instead.

## Step 2 — work only on this machine

Step 1's two unenumerable cases land here: an agent herdr has forgotten and a
worker nothing recorded both still leave their work in a checkout. The delete
spares the base checkout, but step 5 closes the campaign issue indexing it, so it is
read here too.

**Why the reading is a script and not the nine commands it replaced.** Absent
`repos/` and unreadable `repos/`, a pipeline swallowing the enumeration's own
exit status, and a portable enumeration are four things a gate written in prose
has to get right in whatever shell the person is in — and each of them fails by
reporting nothing, which reads as a pass. `scripts/campaign-local-work.py` owns all
four, its exit status separates "the reading failed" from the verdict, and its
docstring carries the evidence. This step keeps only what a reader must decide:
which rows are blockers.

## Step 4 — validate, compare, write

**`.tmp` then `mv`, and both files removed first.** A refusal that has already
truncated `/tmp/repos-before` leaves a zero-length file, and zero-length is what
a legitimate `- none` leaves — so a failed read reads as a repo-less campaign,
the one shape whose index is *meant* to be empty. Worse, the read-back compares
the two files: two failures leave two empty files and `cmp -s` prints "index
survived" over a body nobody managed to read. Absent files make `cmp -s` exit 2,
and the pre-emptive `rm -f` stops a leftover from an earlier run standing in for
either of them.

**Why the compare is the everyday guard under one campaign, one machine.** Two
sessions on the one bound machine are both sessions of the campaign, so the
binding never serialized the body and this comparison is what does. The three
causes of a silent overwrite it catches are the table below; when the body may be
written at all is `AGENTS.md` § The campaign issue body.

## Step 5 — announce, close, delete

**Why announce at all.** Step 1's gate is local, and under one campaign, one
machine that covers everything legitimate: every agent and every worker session
is on the bound machine, step 1 reads every claim ref on the remote and where
each is checked out here, and step 2 read the base and `repos/` for work in no
claim at all. A machine working this
campaign against the binding is what neither can see, and no cheap local check
fixes it. Announcing narrows that window rather than closing it — a session that
never comments is invisible either way — and what keeps it survivable is that a
delegate pushes as soon as it has one commit, so a tree deleted underneath it
costs uncommitted work and nothing more.

**`-prune` on the two exact paths, not a `*/runtime*` pattern.** A pattern also
hides `scripts/repos-helper.sh` and anything else whose name merely contains
`repos` or `runtime` — an omission from a listing whose whole job is to omit
nothing (probed: the pattern form drops exactly that file).

**`grep . || echo` rather than a `${LEFTOVERS:-...}` default**, so the words are
written by a listing that really ran rather than by an assignment that never
happened. That branch fires only for a directory whose scaffold was taken out by
hand: an intact one always lists at least `AGENTS.md`, `CLAUDE.md`, `README.md`
and `scripts/`.

**What makes the claim-ref release sighted is step 3, not step 1.** Every sub-issue
is settled or disposed of by then, so no claim ref can be a worker's live
workspace — and step 3 runs on the no-directory path too, where step 1 was
skipped, and it sees hands and subagent workers that no `herdr agent list` row
would. `AGENTS.md` forbids deleting a claim ref while an agent on your machine
works it; this is the one place where that has been established for every ref at
once. Reaching into a member repository's refs from a close would be the
cross-repository sweep this base forbids.

**Ancestry, not equality**, in numbers: a zero-commit claim compared against
today's `main` sha reads unequal and would be refused as holding work — exactly
the ref the step exists to release. Probed: a claim four commits behind reads
`ahead_by=0 behind_by=4 status=behind`. `matching-refs` returns an empty array
rather than a 404 when a campaign claimed nothing (probed), so the loop runs zero
times and says nothing.

**A machine the campaign was bound to before a migration may still hold a
directory of its own**: a stale cache, untouched by this delete, with nothing
durable in it.

## A moved campaign issue body has three causes, and they look identical

Step 4's compare-then-write refuses when the body has moved since the `README.md`
was derived from it. Read the binding first: `campaign-tracker bound` saying anything but
`here` means *you* are out of position, and the write stops there whatever the
diff says. With the campaign bound here, the refusal is a diff and nothing else,
and three things produce it:

| cause | how to tell | what it wants |
| --- | --- | --- |
| a session on this machine wrote it | ask the peers: `ListAgents`, then `SendMessage` to each | ask what it meant, then fold. Moving a sub-issue between campaigns writes *two* campaign issues, and one of them is never the writer's own campaign |
| a person edited the charter on GitHub | no peer claims the write | their words win: fold them into the `README.md`, refresh the derived copy, re-run |
| a session on a machine the campaign issue's `bound:` label does not name wrote it | nothing on this machine can see it — one `gh` account signs a person's edit and a session's alike | ask the person. The fold is the same; what differs is that the binding was broken and the other machine has to be told |

**The last two are not separable from here, and the refusal says so** rather than
picking one. Naming all three is still worth it: a session meeting the refusal
knows to ask its peers before reconstructing anybody's intent from a diff.
