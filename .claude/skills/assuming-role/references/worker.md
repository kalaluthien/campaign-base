# The worker's lifecycle

A worker takes one sub-issue and lands it. It writes its own campaign's plane
and, on a claim, the code the sub-issue names.

`campaign-roles.py` states the licence; these are the moments.

1. **Read the sub-issue body and its comments** before touching anything. A
   decision on the issue outranks the brief that sent you.
2. **Cut the claim**: `campaign-claim take <N> <issue> <topic>`. Every
   sub-issue cuts one, work that lands no commit included. Create-ref is what
   makes it atomic across machines; a survey-then-file is not.
3. **Work in the checkout the claim names** — a worktree for the base, the
   clone for a member repository. The stages inside this step, what each
   produces and when one may be skipped, are
   [landing a change](references/landing-a-change.md).
4. **Sort each choice into one of four routes** before you act on it:
   - **decide it**: what a check settles, and how to build what the
     Definition of done names;
   - **the review**, step 7: whether work already written is right;
   - **ask the planner**: the brief is silent, or reads two ways, on what it
     asks of you -- which step is next, what a line means, whether a file is in
     scope;
   - **hand it up**: it changes what the work is -- a Plan or Definition of
     done item added, dropped or moved, even one a check shows is moot, a rule
     found two ways, an off-limits file or target, a destructive step, a
     Definition of done you cannot meet, a pick the Plan reserves.

   A question and a hand-up take one channel: a `BLOCKED` on the sub-issue,
   its first line saying which, then the message -- not a NOTE, a question in
   the pane, or a DECISION of your own.
5. **Open the pull request on the first commit**, not when the work is ready.
   The hook has already pushed the branch; a late pull request only keeps
   published work out of sight.
6. **Post a `REPORT` once per round**, on the pull request, pinning the sha.
   A verdict or a fix report that does not pin its sha is unactionable.
7. **Launch the review as an in-process subagent**, naming the model and the
   level. A session that cannot start one is blocked and says so.
8. **Merge only on all three conditions**: a review read at the sha being
   merged, written by an agent that did not write the commits, and a branch
   containing the current `main`. **Then reach the install**, when the
   repository has one here — the base always does:
   `scripts/campaign-installed.py reach <README> <owner/repo> <merge sha>`,
   and the `REPORT` quotes the line it prints, which names the install's sha.
9. **Release the claim** when the sub-issue is settled. The release compacts
   this pane, so a reused worker does not carry a finished transcript into the
   next sub-issue.

How to review and to launch: `references/reviewing.md`, `references/launching.md`.

A subagent of a worker inherits the worker's role, because the guard reads the
parent's session id. It is briefed by the parent's context and by nothing else:
no hook reaches it.

**Run the full sweep once, just before the commit**: rerunning it after each
edit multiplies the cost, so batch a file's edits and run the suite they touch.

## Handing off

A fresh worker takes over when this one cannot go on: a context too large to
compact, a harness upgrade. Not a slug rename: the claim ref keeps the old
slug, the guard reads a branch as a claim only when a `.campaign` marker names
its slug, and it refuses a worker whose name carries another -- so whichever
slug the marker holds, one of the two sessions is refused. Told of a rename
while holding a claim, land and release it under the old name first. The model
is `handoff` in
`spec/campaign/orchestration/system.als`; the planner's reference names its
first run.

1. **The predecessor posts its last comment**, `NOTE <old>: handed off to
   <new>`, on the sub-issue: the checkout, the pull request and the sha it
   sits at, the round it is in, and the pane to close. It writes nothing after
   it, and does not release the claim.
2. **It starts the successor** at the base root, or in the same clone for a
   delegate (`references/launching.md`), named
   `<slug>-worker-<n>` by `campaign-name-session.py`. The first prompt is one
   sentence: take over `<slug>#N` from `<old>`, read its NOTE.
3. **The successor reads that NOTE on GitHub**, confirms the ref with
   `campaign-claim live <N>`, and works in the same checkout. A successor
   named for another campaign stops here: the guard would refuse it this
   campaign's issues.
4. **Only then it sends `/exit`** to the predecessor's pane with `herdr agent
   prompt`, and reads `herdr agent list` until the pane is gone; still listed
   after a minute, it reports that on the sub-issue, never kills. The
   predecessor never exits itself, so the claim always has a live holder.

The state travels in the NOTE, the claim ref and its checkout, and the pull
request; the old pane, its transcript and a scratchpad carry none of it.
