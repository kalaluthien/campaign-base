# Campaign principles: development

This campaign exists to build something new under a specification. These
principles are appended to the repository's own conventions and only add to
them; where a repository already has a rule, that rule stands.

## What good means

The spec, the test and the code say the same thing, and a reader can walk from
any one of them to the other two by name: a scenario in the model names the
test that exercises it, and the test names the code path it drives.

## What a claim needs

- The model before the code: a change is written first as the scenario or check
  that its plan implies, in whatever language the repository's spec is written
  in, and the checker's verdict on that model is the first evidence the change
  is coherent.
- A test that failed before the change and passes after it, named after the
  scenario it witnesses.
- A view a person can read, when the model grew a shape a person has to
  understand; a change the model already describes needs none.

## What to optimise for

The tie between the three, over the size of any one. A stage a change may skip
is one the model says it may skip, by a criterion the model states; a stage
skipped by judgement is the tie broken silently.

## What to refuse

- Code before its scenario. A change whose plan was never formalised has not
  been checked for coherence, only for compiling.
- A test that passes with the change reverted. It witnesses nothing.
- A verdict restated in prose. The checker is the one reader of its own verdict.

## SDLC profile

`optional = skippable` -- the kind narrows nothing below the criterion, which
already refuses each skip wherever there is anything to refuse: a change that
wrote a code path skips neither its scenario nor its test, and one whose
scenario grew a shape does not skip its view. What is left is a change with
nothing below its plan -- a procedure reference, a README, a comment -- and it
lands with every stage below Plan waived.

## Every session

What a session of this campaign does that the `assuming-role` skill does not
already say. The skill carries the lifecycle every campaign shares; this section
carries only the difference, and empty is the ordinary state.

## Planner

What this campaign's planner decides, files, or refuses beyond that lifecycle.

## Worker

What this campaign's worker owes beyond that lifecycle -- the checks its pull
requests must pass, and what it leaves behind when a sub-issue closes.
