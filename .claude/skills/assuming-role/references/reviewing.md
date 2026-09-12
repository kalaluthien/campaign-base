# Commissioning a review, in full

The one home of every judgement about a review; `AGENTS.md` § Review names the
mechanisms that decide the rest, and `AGENTS.md` § Merge conditions the three
conditions a review serves. A review is the only thing standing between a
branch and `main`, and the two ways it goes wrong are running it in the wrong
mode and running it at a level nobody chose.

## The call

**Every review runs as an in-process subagent. There is no other way to run
one** -- not a default and not the cheapest option, the one mode. It is
launched by whoever wants the merge, the author included, because merge
condition 2 is on who *writes* it; `review` in
`spec/campaign/orchestration/system.als` is why it has no guard on who
commissions it.

```
Agent(subagent_type: "general-purpose", model: "<named below>",
      description: "Review PR <N>",
      prompt: "review PR <N> at <level>\n\n…")
```

`general-purpose` because `fork` inherits the author's context and would review
the author's own reasoning. `description` because the tool requires it.
`isolation` unset, because a worktree or a remote environment buys a review
nothing -- it changes no working tree. The `model` is not optional:
`scripts/check-campaign-claim.py` refuses a launch naming none, and says why.

**`ultra` is not a level.** It is a person-only review mode, and putting it in
that slot is the one way to write this block illegally.

**A plain brief, not `/code-review` above `low`, until a fanned round prices
under a narrowed round.** The guard refuses the `Skill` call that does
otherwise, and its `FANS_OUT` comment keeps the two probes showing that a slash
command in an `Agent` prompt is plain text and runs no skill.
`/code-review` above `low` inside a reviewer subagent fans out into an
orchestrator, finders and their verifiers, each its own further subagent --
metered at the launching call's own turns alone until
`campaign-token-tally.py reviews` rolls a fan-out's nested transcripts into the
round that spawned it (`nested` counts how many). PR #255's five fanned rounds
cost 79,667 to 2,112,272 input_new each, ~5.0M combined, against 57,374-134,222
for one narrowed round below. **The rolled-up figures are #273's**, re-derived
over the same window at PR #276's merge sha (`97c6797`) and posted as a NOTE on
kalaluthien/campaign-base#272: 47 rounds, 98 nested transcripts folded in,
13,402,567 input_new in total. **PR #264 fanned out too**, 9-19 nested
transcripts per round at 656,852-1,566,076 input_new each, so #255 is not the
only one; the NOTE lists 15, 16, 254, 261, 263, 265 and 269 as nested-0 at the
time it was written (`campaign-token-tally.py reviews --campaign 244 --since 2026-09-08T07:00:00Z`).
Write the brief as `"review PR <N> at <level>"`, level right after `at`,
naming what to check after a blank line, and reserve `/code-review` above
`low` for a reviewer once a fanned round prices under that figure.

**The brief says what a reviewer may do**: it reads, runs checks, and edits,
kills or launches nothing. That is one sentence of the brief and not a
mechanism -- no reviewer agent definition, and no branch in the guard reading
what kind of agent is being launched (owner's DECISION on #278, 2026-09-10).

**`low` is under the bar and outside it.** #282 ran both rows on one diff with
one model (2026-09-10): `/code-review low` cost 60,774 input_new, 101,697 with
the subagent that launched it, against 127,442 for the narrowed plain brief on
the same diff -- inside the 57,374-134,222 band below. It cannot fan out, which
is why the guard's `CHEAP_LEVEL` passes it. **What `low` does not do is satisfy
merge condition 1**: it skips test hunks and reads no full files, and on that
diff it returned 2 findings against the plain brief's 5, missing two of the
three behavioural ones. It is a cheap first pass, and the review a merge waits
on is still the plain brief.

## The two knobs

They answer different questions and are named on every launch.

**Model, by the depth of the change** -- the general model-selection rule applied
to the change rather than to the review. A change whose correctness is not local
(a state machine, a concurrency argument, an invariant spread across callers)
takes the heavier model, because a weaker reader returns "looks fine" on exactly
the reasoning that needed a reader. Broad and shallow takes a lighter one. Judge
the change; the launcher's own model is not the input, and a session running
light does not license a lighter reviewer.

**Level, by how much there is to read** -- many files, many call sites, a claim
to check everywhere it is stated. `medium` is the working baseline; a sweep goes
above it. **`/code-review`'s level is the first token after the command and
nowhere else**: asking for it in the brief sets nothing, and the guard refuses
a call naming none. **A plain brief sets no level mechanically at all** -- there
is no harness position that reads one, only the reviewer's own judgment of what
you wrote and, separately, `campaign-token-tally.py`'s own reading of the token
right after `at` for its own accounting. Put the level there anyway, since
that is the one place a launcher and the tally agree to look, but say what you
mean in the rest of the brief too.

So a broad mechanical sweep is a lighter model at a higher level, and a subtle
local change is a heavier model at a lower one. The knobs are independent, and a
review needing both at their limit is a brief covering two reviews.

**A reviewer that needs more than the brief allows is a brief written too wide.
Split the brief.**

**A brief over a guard reads the ALLOWS before the refusals.** A refusal branch
is easy to read and easy to agree with; what it catches by mistake is neither,
and five of #184's fix rounds stayed green while each opened a new false
positive. So the brief names the ordinary shapes the branch could catch, and the
review checks those first. The measured version of the same rule is
`scripts/guard-precision.py`, which reads the guard's verdict log, and the
replayed version is `scripts/fixtures/guard-allow-corpus.jsonl`, the calls this
machine's sessions really made.

## Three ways to get the mode wrong

**A peer session** is not a reviewer: it costs a re-explanation of context the
launching session already holds, and its findings arrive as a relay instead of on
the pull request.

**Reading the diff yourself** and calling it reviewed fails merge condition 2
at any length or care.

**A herdr session** buys nothing a review uses, and pays a process boundary for
it.

The one exception is an `ultra` review, which a person triggers and no session
may launch. A session that cannot start a subagent is **blocked**: it says so to
the person and the pull request waits. That is never a licence to review some
other way.

## The shape of a round

**One full review, at the final sha, and narrowed reviews after it.** The full
review is commissioned once, on the pull request as a whole, when the work is
what the author means to land. Every fix round after it is reviewed on that
round's diff only — a plain brief naming the diff range, launched by the
worker that made the fixes. A narrowed review does not re-run a
measurement the full review already made and reported, **unless the fix
touched what was measured**: a round that edits the script a number came from
retires that number, and the brief says to re-derive it.

**A fix round is: findings on the pull request, one worker, one `REPORT`.** The
worker verifies each finding at the site it names before touching anything.
Follow-ups fold into the same round, whose boundary is the `REPORT` and never a
push, and which ends in one `REPORT` carrying the sha and a per-finding
disposition. **Check that disposition against the findings list mechanically**: a
round claiming "all fixed" without re-running its sweep is what keeps happening.

**A reconciliation with `main` decides the breadth of the review it needs**, and
a full re-review is due at that one moment only. It is a push, so condition 1
wants a review at the combined sha either way. A clean auto-merge earns a
narrowed one, on the merge commit's diff alone. A merge that needed a hand
resolution earns a full one, and its brief says it reads the combination:
**containment buys attention from nobody**, and the resolution is where the two
branches actually met.

**What a round costs, so that "one more round" is a priced decision.** Measured
over 2026-09-04T00:45Z–2026-09-05T01:00Z (#200, `campaign-token-tally.py reviews`,
method on #195): one round runs **57,374 to 134,222 input tokens** at `medium` or
`high` on Opus. **This range predates #273's rollup**, which edited `reviews`
itself: it was read before the rollup existed, so it undercounts any round in
that window that fanned out the way #273's own NOTE describes. It remains the
working threshold wherever it is cited until a rollup-aware re-derivation over
the same window replaces it — a follow-up, not done here. The shape this
replaces is what the range hides —
PR #184 ran seven rounds at 800,567 input tokens, 38% of #177's *new input*,
because each round re-read the entire pull request to check a handful of
fixes.

**A round returning only refinement ends the loop**: when every finding is
wording, a number in prose, a name or a claim softened -- no behavioural defect
in shipped code and no test that passes with its branch deleted -- apply them in
one commit, review that diff narrowed, and merge, rather than commissioning
another round. A number a check enforces is not prose. Measured on PR #238: six
fix rounds followed the full review and every one of them fixed a real defect or
a test that passed with its branch deleted; only the review after the sixth
returned refinement alone.

One reviewer per pull request, one verifier per fix round. Every angle the review
should take is a section of the one reviewer's brief. Fan out into parallel
reviewers only when the angles are genuinely independent *and* the budget is
known to carry them: many parallel angles on one pull request risk the session
limit, for findings a single consolidated pass finds at a fraction of the spend.

**The pull request is the review's working memory.** A finding that exists only
inside a running session is not yet found. Findings are posted as a comment the
moment they consolidate, before anything else is launched, and a reviewer that
runs long writes them out as it goes -- findings held only in a session's context
do not survive the session limit, while findings on the pull request do, and let
a fix start while the rest of the review is still running.

## What the REVIEW comment has to carry

Two readers decide it, and a comment either fails costs a red required check
rather than a wasted round: its first line is the `KIND` shape
`scripts/check-campaign-claim.py` owns, and its body must name the pull
request's head sha the way `scripts/check-merge-review.py` reads one.
