# Commissioning a review, in full

The procedure behind `AGENTS.md` § Review, which keeps the
rules. A review is the only thing standing between a branch and `main`, and the
two ways it goes wrong are running it in the wrong mode and running it at a
level nobody chose.

## The call

```
Agent(subagent_type: "general-purpose", model: "<named below>",
      description: "Review PR <N>",
      prompt: "/code-review <low|medium|high|xhigh|max> <PR#>\n\n…")
```

`general-purpose` because `fork` inherits the author's context and would review
the author's own reasoning. `description` because the tool requires it.
`isolation` unset, because a worktree or a remote environment buys a review
nothing -- it changes no working tree.

**Name the model, always.** Leaving it out inherits a default rather than
expressing a choice, and there is no value meaning "whatever the launcher is".

**`ultra` is not a level.** It is a person-only review mode, and putting it in
that slot is the one way to write this block illegally.

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
above it. **The level is the first token after the command and nowhere else**:
asking for it in the brief sets nothing, because only that token is parsed, and
omitting it falls back to a persisted setting and then to the session's own
effort -- a level chosen by neither the launcher nor the work.

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

**Reading the diff yourself** and calling it reviewed fails merge condition 2,
which is about who wrote the commits -- the author's own read is not a review at
any length or care.

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
round's diff only — `/code-review <level> <PR#>` with the brief naming the diff
range, launched by the worker that made the fixes. A narrowed review does not
re-run a measurement the full review already made and reported, **unless the fix
touched what was measured**: a round that edits the script a number came from
retires that number, and the brief says to re-derive it.

A reconciliation with `main` is a push, so condition 1 wants a review at the
combined sha either way; the reconciliation decides its breadth. Clean auto-merge,
narrowed on the merge diff. Hand-resolved, full, reading the combination
(`AGENTS.md` § Concurrency).

**What a round costs, so that "one more round" is a priced decision.** Measured
over 2026-09-04T00:45Z–2026-09-05T01:00Z (#200, `campaign-token-tally.py reviews`,
method on #195): one round runs **57,374 to 134,222 input tokens** at `medium` or
`high` on Opus. The shape this replaces is what the range hides — PR #184 ran
seven rounds at 800,567 input tokens, 38% of #177's *new input*, because each
round re-read the entire pull request to check a handful of fixes.

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
