# Campaign principles: migration

This campaign exists to move a working system from one form to another without
changing what it does. These principles are appended to the repository's own
conventions and only add to them; where a repository already has a rule, that
rule stands.

## What good means

Behaviour is unchanged, and that was verified rather than argued. Every step can
be undone by a rollback that has actually been run.

## What a claim needs

- An equivalence check: old path and new path over the same inputs, outputs
  diffed, the diff empty or every difference explained. Real recorded inputs
  beat synthetic ones.
- A rollback that was executed at least once, not merely described. A rollback
  path nobody has run is a plan, not a property.

## What to optimise for

Reversibility at every step. Prefer many small cutovers each of which can be
undone alone to one large one that can only be undone whole.

Coexistence over replacement. Run old and new side by side, compare in the
background, and switch only once that comparison has been quiet for a full
cycle of real traffic.

## What to refuse

- Mixing a behaviour change into the migration itself. Whatever this repository
  merges as one unit, the change of form and the change of behaviour go in
  separate ones, or the equivalence check has nothing to compare.
- Deleting the old path in the same change that enables the new one. Removal is
  a later sub-issue, filed once the new path has carried real load.
- A cutover with no rollback, or one whose rollback needs data it destroys.
- Silence about a difference you found and accepted. Write it down with the
  reason; it is the thing an incident will point at.

## SDLC profile

`optional = Docs` -- a migration always lands a code path, and `criterion` for
`Spec` is that nothing below it exists, so its scenario is never skippable; the
view is, because this kind changes no behaviour and so grows no shape.

## Every session

What a session of this campaign does that the `assuming-role` skill does not
already say. The skill carries the lifecycle every campaign shares; this section
carries only the difference, and empty is the ordinary state.

## Planner

What this campaign's planner decides, files, or refuses beyond that lifecycle.

## Worker

What this campaign's worker owes beyond that lifecycle -- the checks its pull
requests must pass, and what it leaves behind when a sub-issue closes.
