# Campaign principles: analysis

This campaign exists to measure or audit a system that already runs. These
principles are appended to the repository's own conventions and only add to
them; where a repository already has a rule, that rule stands.

## What good means

Every claim is a number or a location — a measurement with its method, or a
file and line — and a second person can reproduce it from what you wrote.

## What a claim needs

- The method, written down before the number: what was measured, over what
  window, on what machine, against what baseline.
- The raw output kept, not just the conclusion drawn from it. Keep the script
  that produced it under the campaign's `scripts/` so the next run is one
  command.
- A named sample. "Representative" is itself a claim and needs its own evidence.

## What to optimise for

Reproducibility over coverage. A number that can be re-measured next month is
worth more than three that cannot, because the value of an audit is the delta it
lets you see later.

Tracing to a cause, not stopping at a symptom. A finding that names a metric
without naming the code or data that moves it leaves the reader where they
started.

## What to refuse

- Fixing what you find. Report a defect discovered mid-audit to the campaign
  session, which decides where it lands — a sub-issue only if it outlives one
  review cycle, otherwise an item on an open pull request or the next sub-issue
  that touches the file; changing it under you invalidates the
  measurement and hides the finding in a diff.
- An estimate presented in the shape of a measurement. If it was not measured,
  say it was not.
- Extrapolating a trend from two points, or from a window that includes a
  deploy, an incident, or a holiday, without saying so.

## SDLC profile

`optional = skippable` -- this kind refuses to change what it measures, so a
change of it may land nothing runnable at all. A measurement script kept under
the campaign's own `scripts/` never lands and so is never read here; one that
lands in a repository owes the scenario and the test above it like any other
code path.

## Every session

What a session of this campaign does that the `assuming-role` skill does not
already say. The skill carries the lifecycle every campaign shares; this section
carries only the difference, and empty is the ordinary state.

## Planner

What this campaign's planner decides, files, or refuses beyond that lifecycle.

## Worker

What this campaign's worker owes beyond that lifecycle -- the checks its pull
requests must pass, and what it leaves behind when a sub-issue closes.
