<!-- The sub-issue. Title: a verb-first mission, at most 80 characters, carrying
     the words a search would use -- `Refuse a heredoc body the guard cannot
     split`, never a sentence about the situation. Body at most 2,000
     characters, bullets or tables, no prose paragraphs.

     NO `Campaign:` LINE. The `--parent` link is the index and
     `campaign-tracker index` reads it back; a line nothing read is the shape a
     declared contract takes just before it drifts.

     TWO MOMENTS. `## Intent`, `## Done when` and `## Lands in` are written when
     the issue is FILED. `## Plan` is added by whoever will prompt the work,
     BEFORE anybody is prompted onto it, so a worker reads one issue and nobody
     plans in a pane. `campaign-claim take` requires all four and refuses the
     claim without them, naming the escape: a planner edits the body.

     NO `## Working it` SECTION. It restated `AGENTS.md`, which every session
     loads from the tree it sits in, and the copy is the one that drifts. The
     branch, the pull request, the merge conditions, the review and the four
     messages are all there.

     THE `backlog` LABEL, not a section: a sub-issue carrying it is not worked
     until the owner takes it off, and `take` refuses a claim on it. -->

## Intent

- <what is wrong or missing now, and what says so>

## Done when

- <the condition that settles this issue, readable off the CLOSED issue -- the
  merged pull request, or for a sub-issue that lands no commit its closing
  `DECISION` comment -- rather than off a claim>

## Plan

- <the steps, and what constrains them: an ordering against another sub-issue, a
  decision already made, a file that is off limits. Bullets or one table.>

## Lands in

<!-- Exactly one entry: `- owner/repo` for a member repository, or `- none` for
     the base, which is where every sub-issue changing `spec/`, `scripts/` or
     `AGENTS.md` lands. The base's own slug means the same thing. Read by
     `campaign-repos.py`'s `lands_in`, which `campaign-claim take` calls to
     decide where the ref is cut. -->

- <owner/repo, or none>
