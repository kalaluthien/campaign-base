# Kind: analysis

A sub-issue of this kind measures or audits something that already runs. What
the base's `AGENTS.md` and the role references already say is not repeated
here.

## What good means

Every claim is a number or a location, with its method beside it, and a second
person can reproduce it from what you wrote.

## What a claim needs

- The method written down before the number: what was measured, over what
  window, on what machine, against what baseline.
- The raw output kept beside the conclusion drawn from it.

## What to optimise for

- Reproducibility over coverage: a number that can be re-measured next month is
  worth more than three that cannot, because an audit's value is the delta it
  lets you see later.
- A cause, not a symptom: a finding that names a metric without naming the code
  or data that moves it leaves the reader where they started.

## SDLC profile

`optional = skippable` -- a change of this kind may land nothing runnable; one
that lands a script owes the scenario and the test above it like any other code
path.
