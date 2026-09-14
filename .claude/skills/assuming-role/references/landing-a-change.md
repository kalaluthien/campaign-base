# Landing a change

The inside of a worker's step 3: which stage comes first, what each one
produces, and when one may be skipped. `spec/sdlc/system.als` is normative —
every row below cites the identifier that decides it and states no rule of its
own, so a disagreement is settled by reading the model, never this page.

## The five stages

`feeds` is the order and `orderDiscipline` reads it: intent, plan, spec, test,
then code. A stage is written only once every
stage feeding it is written or may be skipped. The order reads those feeding
stages and no further back, so it lets a test be the first thing a change
writes, and nothing refuses that order: the merge reads what the change holds
when it lands, and refuses it only if intent or plan is still missing then,
since neither is ever skippable. A skipped stage is one with no artifact;
nothing records the skip.

| stage | its artifact here | it owes the next | its skip criterion | in `spec/sdlc` |
| --- | --- | --- | --- | --- |
| intent | the sub-issue's `## Intent` | the problem the plan answers | never skippable | `Intent`, absent from `skippable` |
| plan | the sub-issue's `## Plan` | the shape the model formalises | never skippable | `Plan`, absent from `skippable` |
| spec | a scenario or check under `spec/` | the behaviour the test witnesses | nothing runs | `Spec`, `criterion` |
| test | a case in a `scripts/*-test.*` suite | the name the code path answers to | nothing runs | `Test`, `criterion` |
| code | a path under `scripts/` or `.claude/` that a test drives | the merge | nothing runs | `Code`, `criterion` |

A member repository maps the last three onto its own tree. The criterion column
is half of `maySkip`; reuse, in the next section, is the other half.

## The two readings of a skip

`maySkip` is the `criterion`, or reuse: a skippable stage may be absent while
the change has written nothing that runs, and a stage the change's tests
witness or drive is held, not skipped. No kind narrows this; a sub-issue's
`kind:<k>` label picks the reference beside this one, `kind-<k>.md`, which
says what its changes write.

The order reads `maySkip` for each absent stage when you write past it
(`orderDiscipline`), and the merge reads it again against the change as it
finally stands (`mergeDiscipline`, which `scripts/check-merge-review.py --merge`
reads in `check`). The second is not the first restated:
`criterion` reads `writtenOf`, which grows, so a skip licensed when you wrote
past the stage can be stale by the merge — `S5b_WithoutTheLandingCheck` is a
chain that keeps the first reading and still lands wrong. The remedy is to
write the stage after all.

So a skip is permission and not a plan, and two readings narrow it further.
`criterion` is that nothing runs, so a change that writes a test or a code path
cannot skip its scenario. And
`tieDiscipline` reads at every commit, not at the merge, so a code path a
commit leaves in the tree owes a scenario even on a branch that never lands.
The tie does not widen the skip -- `criterion` reads what the CHANGE wrote,
never what the tree ties -- so a change that lands a code path cannot waive its
scenario however that path ties (`S5a_WithoutTheCommitCheck`).

## The tie

`tie` reads two relations off one test: `witnesses`, the scenarios its
`# witnesses: <Name>[, ...]` line declares, and `drives`, the code path its own
name pairs with. Write that line in every suite -- a mention in prose ties
nothing since #268, and `scripts/check-sdlc-tie.py` matches the declared names
exactly against `spec/commands.snapshot.json`, so a scenario is nameable once
`scripts/alloy-check.py --commands spec --write` has run in the same commit.
`everyCodeHasScenario` asks for a tie at every code path in the tree the
allow-list does not exempt, read from the code path up and never from the scenario down — a scenario
with no test is a claim the solver checks on its own. Every name on the line must resolve as well
(`everyWitnessExists`): one live name ties the code path but does not cover a
dead one beside it. `tieDiscipline` is the reading at the commit.

A rename is the one commit that breaks a tie (`renameArtifact`), and the two relations
break at different ends: `witnesses` at the scenario's
(`S4b_ScenarioRenameBreak`), `drives` at either of its own
(`S4_CodeRenameBreak` for the code path, `S4c_TestRenameBreak`
for the suite). Move both ends in the same commit
(`S4a_TiedCodeRename`).

A code path this tree already held untied is licensed by name in the guard's
`LEGACY`, the model's `Licensed`. Tying one means deleting its line in the same
commit, and a path your change touches that is untied and unlisted is refused.
The list never grows (`licenceNeverGrows`): a path you add, or a tied path you
untie, is refused whatever the list says.
