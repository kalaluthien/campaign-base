# Landing a change

The inside of a worker's step 3: which stage comes first, what each one
produces, and when one may be skipped. `spec/sdlc/system.als` is normative —
every row below cites the identifier that decides it and states no rule of its
own, so a disagreement is settled by reading the model, never this page.

## The six stages

`feeds` is the order: intent, plan, spec, then docs and test in either order,
then code. A stage is written or waived before anything it feeds is written.

| stage | its artifact here | it owes the next | may be waived when | in `spec/sdlc` |
| --- | --- | --- | --- | --- |
| intent | the sub-issue's `## Intent` | the problem the plan answers | never | `Intent`, absent from `skippable` |
| plan | the sub-issue's `## Plan` | the shape the model formalises | never | `Plan`, absent from `skippable` |
| spec | a scenario or check under `spec/` | the behaviour the view draws and the test witnesses | nothing below it exists | `Spec`, `criterion` |
| docs | the HTML view beside its model | the shape a person reads | the model grew no shape | `Docs`, `GrowsShape` |
| test | a case in a `scripts/*-test.*` suite | the name the code path answers to | nothing runs | `Test`, `criterion` |
| code | a path under `scripts/` or `.claude/` that a test drives | the merge | nothing runs | `Code`, `criterion` |

A member repository maps the last four onto its own tree. How the view itself is
drawn is `~/.claude/CLAUDE.md` § Visual encoding, and is not repeated here.

The `REPORT` names each stage's artifact, so a reader can check the chain
without re-deriving it from the diff.

## The two readings of a waiver

`maySkip` is the kind's profile **and** the stage's own `criterion`, together;
neither alone licenses a waiver. The profile is one line in the campaign's
`AGENTS.md`, seeded from `.claude/skills/opening-campaign/assets/agents/`, and
says what the kind never goes without. The criterion decides the rest, per
change.

You read `maySkip` when you reach the stage (`skipDiscipline`), and the merge
reads it again against the change as it finally stands (`landDiscipline`). The
second is not the first restated: `criterion` reads `writtenOf`, which grows, so
a waiver licensed when you reached the stage can be stale by the merge —
`SkipReadAtTheTimeIsNotEnough` is a chain that keeps the first reading and still
lands wrong. The remedy is to write the stage after all, which retracts the
waiver (`write`, `S3b_DocsWrittenAfterAll`).

So a profile is permission and not a plan. A prototyping change that writes a
code path cannot waive its scenario even though its profile allows one, because
`criterion` for `Spec` is that nothing below it exists.

## The tie

`tie` reads a scenario naming the test that witnesses it and that test naming
the code path it drives. `treeTied` asks it of every code path in the tree, read
from the code path up and never from the scenario down — a scenario with no test
is a claim the solver checks on its own.

A rename is the one commit that breaks a tie (`rename`,
`S4_RenameBreaksTheTie`). The commit that renames a path rewrites the texts
naming it in the same commit (`S4a_RenameKeepsItsNamers`).
