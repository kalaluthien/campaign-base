# The worker's lifecycle

A worker takes one sub-issue and lands it. It writes its own campaign's plane
and, on a claim, the code the sub-issue names.

`campaign-roles.py` states the licence; these are the moments.

1. **Run `scripts/campaign-context.py <issue>`, then read the sub-issue
   body**, before touching anything: it prints the comments on the issue, on
   what its body cites, and the campaign issue's notes naming it. A decision
   on the issue outranks the brief that sent you.
2. **Cut the claim**: `campaign-claim take <N> <issue> <topic>`. Every
   sub-issue cuts one, work that lands no commit included. Create-ref is what
   makes it atomic across machines; a survey-then-file is not.
3. **Work in the checkout the claim names** — a worktree for the base, the
   clone for a member repository. The stages inside this step, what each
   produces and when one may be skipped, are
   [landing a change](landing-a-change.md).
4. **Sort each choice into one of four routes** before you act on it:
   - **decide it**: what a check settles, and how to build what the
     Definition of done names;
   - **the review**, step 6: whether work already written is right, a
     trade-off inside the Definition of done included;
   - **ask the planner**: the brief is silent, or reads two ways, on what it
     asks of you -- which step is next, what a line means, whether a file is in
     scope;
   - **hand it up**: it changes what the work is -- a Plan or Definition of
     done item added, dropped or moved, even one a check shows is moot, a rule
     found two ways, an off-limits file or target, a destructive step, a
     Definition of done you cannot meet, a pick the Plan reserves.

   A question and a hand-up take one channel: a `BLOCKED` on the sub-issue
   whose `BLOCKED <name>:` line says which of the two it is, then the message
   -- not a NOTE, a question in the pane, or a DECISION of your own -- and
   stop until the planner's prompt delivers its `DECISION`. With no planner
   running on the sub-issue, ask the owner with `AskUserQuestion` in your own
   turn instead of posting a `BLOCKED`. Where the planner drives the
   sub-issue a step at a time, the `NOTE` that ends a step is followed by a
   message to the planner naming it, then the same stop: the planner's watch
   counts a pull request's comments and none on the sub-issue.
5. **Open the pull request on the first commit**, not when the work is ready.
   The hook has already pushed the branch; a late pull request only keeps
   published work out of sight.
6. **Launch the review yourself after the push**, as
   `.claude/skills/assuming-role/references/reviewing.md` § The call says:
   full at the first sha, narrowed after a fix round. It checks that the
   implementation is correct; a decision, or a doubt about one, goes to the
   planner as a `BLOCKED` (step 4), never to the reviewer.
   The reviewer posts its own `REVIEW` on the pull request, pinning the
   sha; refused, you file a `BLOCKED`, never a retry from your own pane.
7. **Then post a `REPORT` asking for the merge**, once per round, on the pull
   request, pinning the sha, and send it to the planner. A verdict or a fix
   report that does not pin its sha is unactionable. After it the next move is
   the planner's -- the merge, the next pull request of a multi-PR Plan, or the
   next assignment -- so wait for its prompt and launch nothing.
8. **The merge is the planner's** ([planner](planner.md) step 9): it merges
   on the three conditions of `AGENTS.md` § Merge conditions and reaches the
   install. A worker that merges where no planner runs holds the same three
   conditions, then runs
   `scripts/campaign-installed.py reach <README> <owner/repo> <merge sha>` and
   quotes the line it prints, which names the install's sha, in its `REPORT`.
9. **At settlement, post a last `REPORT`, then release the claim, in one
   turn.** The `REPORT` goes on the pull request, or on the sub-issue where
   there is none, and to the planner: the merge sha beside the head it pins,
   or the closing comment of a sub-issue with no pull request; that nothing is
   left only on this machine; and that the release follows. A worker that
   merged with no planner folds it into step 8's `REPORT` and sends none. It
   is a `REPORT` and not a fifth message, so it comes before the release: the
   model's `report` needs a live agent and `agentRelease` needs none. The one
   turn is the pane's, not the model's: the release's compaction fires when
   the turn ends, after the `REPORT`. The planner reads the release off the
   ref. The release compacts this pane, so a reused worker does not carry a
   finished transcript into the next sub-issue.

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
4. **Only then it runs `scripts/campaign-close.py leave <N> <pane>`** on the
   predecessor's pane: `/exit`, the wait until herdr no longer lists it, and
   its tab closed. Refused at `gone`, it reports that on the sub-issue, never
   kills. The predecessor never exits itself, so the claim always has a live
   holder.

The state travels in the NOTE, the claim ref and its checkout, and the pull
request; the old pane, its transcript and a scratchpad carry none of it.
