# Kind: migration

A sub-issue of this kind moves a working system from one form to another
without changing what it does. What the base's `AGENTS.md` and the role
references already say is not repeated here.

## What good means

Behaviour is unchanged, and that was verified rather than argued. Every step
can be undone by a rollback that has actually been run.

## What a claim needs

- An equivalence check: old path and new path over the same inputs, outputs
  diffed, the diff empty or every difference explained. Real recorded inputs
  beat synthetic ones.
- A rollback executed at least once. One nobody has run is a plan, not a
  property.

## What to optimise for

- Reversibility at every step: many small cutovers, each undoable alone, over
  one large one undoable only whole.
- Coexistence over replacement: run old and new side by side, compare in the
  background, and switch once the comparison has been quiet for a full cycle of
  real traffic.

## What to refuse

- A behaviour change mixed into the migration. The change of form and the
  change of behaviour land as separate units, or the equivalence check has
  nothing to compare.
- Deleting the old path in the change that enables the new one. Removal is a
  later sub-issue, filed once the new path has carried real load.
- A cutover with no rollback, or one whose rollback needs data it destroys.

## SDLC profile

`optional = skippable` -- a runbook, a rollback note or an accepted difference
lands with every stage below the plan waived; a change that lands a code path
owes its scenario and test like any other.
