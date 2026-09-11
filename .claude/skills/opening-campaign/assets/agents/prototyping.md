# Campaign principles: prototyping

This campaign exists to find out whether an approach can work at all. These
principles are appended to the repository's own conventions and only add to
them; where a repository already has a rule, that rule stands.

## What good means

The riskiest unknown has been exercised end to end, on real inputs, as early as
possible — and the answer is now known either way.

## What a claim needs

Something that runs. A demo, a script, a recording. Not a design, not a passing
unit test over a mock, not a description of what would happen.

## What to optimise for

Time to the first honest answer. Order the work by which unknown, if it fails,
kills the approach — and go there first, past everything that would merely be
nice to have working.

Throwaway is the default. Pin the path and the one input that demonstrates it;
take any real credential from the environment, and use a throwaway account or a
fixture wherever one will do. Skip error handling for cases you have not hit.
Add the test that shows the thing working before you add any other. This code is
an argument, not a product, and it is expected to be deleted.

## What to refuse

- Abstraction. No interface with one implementation, no configuration knob, no
  generalising a case that has occurred once. It costs turns and it hides which
  part is the actual risk.
- Merging prototype code into a member repository's default branch. It lives on
  its claim branch until someone decides, as a separate sub-issue, what to keep
  and rewrites it.
- Polishing anything before the unknown is answered.
- Quietly reporting a prototype as production-ready. Say what is hardcoded, what
  is unhandled, and what would have to be rewritten.

## SDLC profile

`optional = Spec + Docs` -- the running thing is what this kind never goes
without: the test that shows it working and the code path it drives are the
claim. The `Spec` half is dead rather than narrow, and not by the tie.
`tieDiscipline` reads at every commit, so a code path this kind commits owes a
scenario in the tree even on a branch that never lands, and one already there
will do -- but that does not license the waiver: `criterion` reads what the
CHANGE wrote, so a change of this kind that lands a code path cannot skip its
scenario however that path ties (`S5_CodeWithoutSpec`), and one that
could skip it by criterion wrote nothing in Docs, Test or Code and so cannot
land under a kind that lets neither Test nor Code go
(`S7_PrototypingSpecWaiver`). What the profile leaves live is the
Docs waiver, and only where the scenario added no shape.

## Every session

What a session of this campaign does that the `assuming-role` skill does not
already say. The skill carries the lifecycle every campaign shares; this section
carries only the difference, and empty is the ordinary state.

## Planner

What this campaign's planner decides, files, or refuses beyond that lifecycle.

## Worker

What this campaign's worker owes beyond that lifecycle -- the checks its pull
requests must pass, and what it leaves behind when a sub-issue closes.
