# Kind: maintenance

A sub-issue of this kind keeps a running system in order: it changes the
system's form with its behaviour kept, tidies it, and files what is found wrong
with it. What the base's `AGENTS.md` and the role references already say is
not repeated here.

## What good means

Behaviour is unchanged, and that was verified rather than argued. Every step
can be undone by a rollback that has actually been run. What was found wrong
is on the issue it belongs to.

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

## Standing work

A maintenance sub-issue stands when it wears `standing`: no one deliverable,
worked until a person closes it.

- A finding goes as a `NOTE` on the sub-issue that covers it, reopened. A new
  number only for work that outlives one review cycle.
- Each tidy is one topic ref under this sub-issue's number and one pull
  request.
- The sub-issue stays open until a person closes it, and only a person puts
  the label on or takes it off.
- With no claim it is not `unclaimed` in the planner's reading of the open
  sub-issues; while it holds one it is read like any other.

## What to refuse

- A behaviour change mixed into a change of form. The two land as separate
  units, or the equivalence check has nothing to compare.
- Deleting the old path in the change that enables the new one. Removal is a
  later sub-issue, filed once the new path has carried real load.
- A cutover with no rollback, or one whose rollback needs data it destroys.
