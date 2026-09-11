# Landing a change

The inside of a worker's step 3: which stage comes first, what each one
produces, and when one may be skipped. `spec/sdlc/system.als` is normative —
every row below cites the identifier that decides it and states no rule of its
own, so a disagreement is settled by reading the model, never this page.

## The six stages

`feeds` is the order and `orderDiscipline` reads it: intent, plan, spec, then
docs and test in either order, then code. A stage is written only once every
stage feeding it is written or may be skipped. A skipped stage is one with no
artifact; nothing records the skip.

| stage | its artifact here | it owes the next | its own skip criterion | in `spec/sdlc` |
| --- | --- | --- | --- | --- |
| intent | the sub-issue's `## Intent` | the problem the plan answers | never skippable | `Intent`, absent from `skippable` |
| plan | the sub-issue's `## Plan` | the shape the model formalises | never skippable | `Plan`, absent from `skippable` |
| spec | a scenario or check under `spec/` | the behaviour the view draws and the test witnesses | nothing below it exists | `Spec`, `criterion` |
| docs | a view beside its model; this base keeps none | the shape a person reads, before code | the model added no shape | `Docs`, `criterion`, `AddsShape` |
| test | a case in a `scripts/*-test.*` suite | the name the code path answers to | nothing runs | `Test`, `criterion` |
| code | a path under `scripts/` or `.claude/` that a test drives | the merge | nothing runs | `Code`, `criterion` |

A member repository maps the last four onto its own tree. The criterion column
is only half of `maySkip`; the other half is the next section.

## The two readings of a skip

`maySkip` is the kind's profile and the stage's own `criterion` together;
neither alone licenses a skip. The profile is one line in the campaign's
`AGENTS.md`, seeded from `.claude/skills/opening-campaign/assets/agents/`, and
says what the kind never goes without. The criterion decides the rest, per
change.

The order reads `maySkip` for each absent stage when you write past it
(`orderDiscipline`), and the merge reads it again against the change as it
finally stands (`landDiscipline`). The second is not the first restated:
`criterion` reads `writtenOf`, which grows, so a skip licensed when you wrote
past the stage can be stale by the merge — `SkipReadAtTheTimeIsNotEnough` is a
chain that keeps the first reading and still lands wrong. The remedy is to
write the stage after all (`S3b_LateDocs`).

So a profile is permission and not a plan, and two readings narrow it further.
`criterion` for `Spec` is that nothing below it exists, so a change that writes
a test or a code path cannot skip its scenario whatever its kind allows. And
`tieDiscipline` reads at every commit, not at the merge, so a code path a
commit leaves in the tree owes a scenario even on a branch that never lands.
A profile naming `Spec` is live only for a change that writes nothing below its
plan. The tie does not widen it -- `criterion` reads what the CHANGE wrote,
never what the tree ties -- so a change that lands a code path cannot waive its
scenario however that path ties (`S5_CodeWithoutSpec`).

## The tie

`tie` reads two relations off one test: `witnesses`, the scenarios its
`# witnesses: <Name>[, ...]` line declares, and `drives`, the code path its own
name pairs with. Write that line in every suite -- a mention in prose ties
nothing since #268, and `scripts/check-sdlc-tie.py` matches the declared names
exactly. `everyCodeHasScenario` asks for a tie at every code path in the
tree, read from the code path up and never from the scenario down — a scenario
with no test is a claim the solver checks on its own. Every name on the line must resolve as well
(`everyWitnessExists`): one live name ties the code path but does not cover a
dead one beside it. `tieDiscipline` is the reading at the commit.

A rename is the one commit that breaks a tie (`rename`), and the two relations
break at different ends: `witnesses` at the scenario's
(`S4b_ScenarioRenameBreak`), `drives` at either of its own
(`S4_CodeRenameBreak` for the code path, `S4c_TestRenameBreak`
for the suite). Move both ends in the same commit
(`S4a_TiedCodeRename`).

A code path this tree already held untied is licensed by name in the guard's
`LEGACY`. Tying one means deleting its line in the same commit, and a path your
change touches that is untied and unlisted is refused.
