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

## The Scope survey

One shape of this kind, the one [planner](planner.md) step 10 files. Its
Definition of done is a table, one row per finding: the module or document,
the quality it fails, evidence a check can read, and the follow-up
(`reopen <slug>#N`, `covered by <slug>#N`, `new`). No evidence, no row; a fix
that changes what the campaign is goes up as a `BLOCKED`, not a row. The
script's output is the candidate set, the ruling per row is yours, and the
owner vetoes the table.
