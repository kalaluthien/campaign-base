# Kind: research

A sub-issue of this kind answers a question nobody can currently answer, or
measures or audits something that already runs. What the base's `AGENTS.md`
and the role references already say is not repeated here.

## What good means

The question is answered, and a skeptic can re-run the evidence and reach the
same answer without asking you anything.

## What a claim needs

- The scope the claim is true within, stated. "It works" is not a finding; "it
  works on inputs under 4 KiB, fails above" is.
- The method written down before the number: what was measured, over what
  window, on what machine, against what baseline.
- The raw output kept beside the conclusion drawn from it.

## What to optimise for

- Breadth of hypotheses before depth on any one: the cost of this kind is the
  hypothesis nobody thought to test, not the one tested twice.
- A cause, not a symptom: a finding that names a metric without naming the code
  or data that moves it leaves the reader where they started.

## SDLC profile

`optional = skippable` -- a finding lands on an issue and runs nothing; a
change that lands something runnable owes the stages above it like any other.
