# The planner's lifecycle

A planner decides what work exists and in what order. It writes the campaign
plane of any campaign and changes no code — not by its own hands, and not
through a subagent, which carries the planner's session id and so its role.

Contents: the moments below, then
[decomposing and assigning](#decomposing-and-assigning),
[the planner's clock](#the-planners-clock), [handing off](#handing-off).

`campaign-roles.py` states the licence; these are the moments.

1. **Read the binding** before the campaign issue body, the `bound:` label, a
   claim, or a launch. Only `campaign-tracker bound <N>` answers it, and only
   the word it prints counts.
2. **File each sub-issue** against the campaign issue with `--parent`, from
   `opening-campaign/assets/sub-issue.md`, with its `kind:<k>` label. That
   flag is the whole index; the label is what the worker's brief hook reads.
3. **Look for an existing sub-issue first.** Where one covers the same
   mechanism, reopen it with the observation as a comment rather than minting a
   number: a parent holds at most 100, closed ones included.
4. **File only work that outlives one review cycle.** A defect one commit fixes
   goes into the open pull request on that file, never onto a number of its own.
5. **Claim before you launch.** `campaign-claim take <N> <issue> <topic>` cuts
   the ref; the delegate checks it out, which is what makes the branch its own.
   The planner holds no claim of its own.
6. **Deliver an assignment as a prompt**, never as one of the four messages: a
   prompt is the session's own user turn, so its hooks run.
7. **Answer a `BLOCKED`** with the decision, or carry it to the owner. A relay
   is never the authority; point at the durable artifact instead.
8. **Retire agents as the campaign runs.** The heartbeat retires a worker its
   transcript shows released and compacted, holding no claim it cut, with no
   prompt since the release and no tool call since the compaction; any other
   listed peer is asked which claim it holds, never killed.

Changing code is the one thing no reading licenses. Hand it to a worker: a
session of its own on this machine, or a delegate on a claim.

## Decomposing and assigning

**Group by repository, then cut by mechanism**: a review is paid per landing
whatever its diff (`AGENTS.md` § Sub-issues), so all one mechanism changes is
one sub-issue. Ordered steps stay under it, one pull request at a time, each
topic ref taken once the previous is released; only the final one carries
`Closes`, since GitHub closes on the first merge of a pull request carrying it.

**Order the landings first**: a merge deletes a symptom a stacked branch only
shows and settles two sub-issues meeting in one file, where re-scoping costs a
worker its context. **Commission no review while `main` still has moves to
absorb**: absorbing one is a push, and a push retires the review.

**Brief a chosen mechanism whole and an open one a step at a time** (measure,
probe, choose), each decision yours from the worker's NOTE; run a large design
as design NOTE, adversarial NOTE, one superseding `DECISION`. Route, claim and
hand a defect to a worker in one turn: a note nobody works is never read again.

## The planner's clock

The wake is **one persistent Monitor** on
`.claude/skills/assuming-role/scripts/campaign-heartbeat.py <N> --watch`,
started once and left running. It prints only what changed and what is not as
it should be (`drift <rule>`), so each line is an event. On one, run the
**heartbeat**:

1. `.claude/skills/assuming-role/scripts/campaign-heartbeat.py <N> --apply`.
   It reads every session of the campaign, this planner included, and gives
   each one verdict: `fire` on a limit banner, `compact` at the context
   threshold, `retire` for a worker done and holding nothing, `keep` for the
   rest. Its header says what each reads and sends.
2. Act on the drift the heartbeat does not: assign an `unclaimed` sub-issue,
   ask about a `stuck` claim, release a `settled` one.

No cron and no idle subscription: a subscription on a session already idle
fires at once. The only timer is the one `fire` schedules: a detached sleeper
that prompts this pane a minute after the reset, and it lands even when this
session stops on the same limit. A cron lives in the session and fires into
the banner, which is what #244's 65 firings did, ~11 per window.
A watch that prints `error watchdog` has exited: start it again.

## Handing off

A fresh planner takes over when this one cannot go on: a slug rename, a
context too large to compact, a harness upgrade. The model is `handoff` in
`spec/campaign/orchestration/system.als`. The first run was the rename of
`upkeep` to `rule-check` (rule-check#272, 2026-09-10): `upkeep-planner-1`
posted its NOTE, started `rule-check-planner-10`, and the successor closed it.
Rename the slug only once `campaign-claim live <N>` prints no row under either
claims group, `landed` refs released first with `campaign-claim release`: a
claim ref keeps the old slug, and nothing reads that prefix after the rename.
Rewrite the `.campaign` marker with the label. The worker's side is in
[worker](worker.md).

1. **The predecessor posts its last comment**, `NOTE <old>: handed off to
   <new>`, on the campaign issue: the pending list (which sub-issue each
   session works, which wait) and the pane to close. A decision not yet on an
   issue goes first, as its own `DECISION`. It writes nothing after the NOTE.
2. **It starts the successor** in a pane of its own at the base root, named
   `<slug>-planner-<n>` by `campaign-name-session.py`. The first prompt is one
   sentence: take over from `<old>`, read its NOTE on `<slug>#N`.
3. **The successor reads that NOTE on GitHub**, then `bound <N>` and
   `campaign-claim live <N>`. It checks its own name carries this campaign's
   slug: no guard refuses a planner of another campaign.
4. **Only then it sends `/exit`** to the predecessor's pane with `herdr agent
   prompt`, and reads `herdr agent list` until the pane is gone; still listed
   after a minute, it reports that on the campaign issue, never kills. The
   predecessor never exits itself, so there is never an instant with no
   planner.

The state travels in the NOTE, the claim refs, and the sub-issue index; the
old pane, its transcript and a scratchpad carry none of it.
