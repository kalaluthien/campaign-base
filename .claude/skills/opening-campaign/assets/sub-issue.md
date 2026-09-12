<!-- The sub-issue. Title: one plain sentence, verb first, carrying the words
     a search would use -- `Refuse a heredoc the guard cannot split`, never a
     description of the situation. No clause of reason: the reason goes in
     `## Intent`, where a reader can ask for it. No internal word a newcomer
     has no key to. The example is under the ceiling on purpose, and a case in
     `scripts/campaign-tracker-test.py` keeps it there when the number moves. Body: bullets or tables, no prose
     paragraphs. Both ceilings are numbers in `scripts/campaign-tracker.py`
     and are not repeated here; `campaign-tracker.py check <N>` prints each
     one beside what it measured.

     NO `Campaign:` LINE. The `--parent` link is the index and
     `campaign-tracker index` reads it back; a line nothing read is the shape a
     declared contract takes just before it drifts.

     TWO MOMENTS. `## Intent`, `## Definition of done` and `## Lands in` are
     written when the issue is FILED. `## Plan` is added by whoever will prompt the work,
     BEFORE anybody is prompted onto it, so a worker reads one issue and nobody
     plans in a pane. `campaign-claim take` requires all four and refuses the
     claim without them, naming the escape: a planner edits the body.

     NO `## Working it` SECTION. It restated `AGENTS.md`, which every session
     loads from the tree it sits in, and the copy is the one that drifts. The
     branch, the pull request, the merge conditions, the review and the four
     messages are all there.

     REFERENCES CARRY THEIR SLUG. An issue is `<slug>#N` -- `machinery#1`,
     `sdlc-alloy#246` -- and a pull request is `pr#N`; five campaigns file onto
     one tracker, so a bare `#N` names no campaign. `campaign-tracker.py check`
     prints a bare one as a warning, not a finding, because every body written
     before the rule carries them.

     THE `backlog` LABEL, not a section: a sub-issue carrying it is not worked
     until the owner takes it off, and `take` refuses a claim on it.

     THE `kind:<k>` LABEL, one per sub-issue, given at `gh issue create` as
     `--label kind:<k>`. It says what the work is, and the session assigned
     the sub-issue is handed that kind's reference from
     `assuming-role/references/kind-<k>.md` by the brief hook; a campaign mixes
     kinds, so the label is the sub-issue's and not the campaign's.
     `campaign-tracker.py kind <N>` reads it back, and what
     `campaign-tracker.py check` does with a missing or doubled label is
     AGENTS.md § Sub-issues'. The words and what each is for are the
     `assuming-role` skill's table, "The kind of a sub-issue", and
     `campaign-tracker.py`'s `WORK_KINDS` is the list `check` enforces. -->

## Intent

- <what is wrong or missing now, and what says so>

## Definition of done

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
