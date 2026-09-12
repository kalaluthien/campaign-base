# Campaign principles

What a session of this campaign does that the base's `AGENTS.md` and the
`assuming-role` skill do not already say. A sub-issue's kind is its `kind:<k>`
label, and that kind's reference reaches the session assigned to it through the
brief hook, so nothing here restates a kind. Empty sections are the ordinary
state.

## SDLC profile

`optional = skippable` -- the profile of a sub-issue carrying no `kind:` label,
which is `development`'s; a labelled sub-issue takes the profile its kind's
reference states.

A change that writes no scenario of its own -- a stronger suite over a
scenario and a code path already in the tree -- has its Spec and its Code by
its tests witnessing and driving them (`reusedStages`). Each profile a kind
states lets it write that test first, since each lets Spec go; and the change
drops no witness, every scenario witnessed before it staying witnessed
(`FeaturelessKeeps`, check-sdlc-tie.py's T8).

## Every session

What a session of this campaign does that the `assuming-role` skill does not
already say.

## Planner

What this campaign's planner decides, files, or refuses beyond that lifecycle.

## Worker

What this campaign's worker owes beyond that lifecycle -- the checks its pull
requests must pass, and what it leaves behind when a sub-issue closes.
