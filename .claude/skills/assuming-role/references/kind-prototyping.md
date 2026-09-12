# Kind: prototyping

A sub-issue of this kind finds out whether an approach can work at all. What
the base's `AGENTS.md` and the role references already say is not repeated
here.

## What good means

The riskiest unknown has been exercised end to end, on real inputs, as early as
possible, and the answer is known either way.

## What a claim needs

Something that runs: a demo, a script, a recording. Not a design, not a passing
unit test over a mock, not a description of what would happen.

## What to optimise for

- Time to the first honest answer: order the work by which unknown, if it
  fails, kills the approach, and go there first.
- Throwaway by default: pin the path and the one input that demonstrates it,
  take any real credential from the environment, use a fixture or a throwaway
  account wherever one will do, and add the test that shows the thing working
  before any other. The code is an argument, not a product, and it is expected
  to be deleted.

## What to refuse

- Merging prototype code into a member repository's default branch. It lives on
  its claim branch until a separate sub-issue decides what to keep and rewrites
  it.
- Polishing anything before the unknown is answered.

## SDLC profile

`optional = Spec + Docs` -- the test and the code path it drives are the claim,
so neither is ever waived; what the profile leaves live is the Docs waiver
(`prototypingProfile` in `spec/sdlc/scenarios.als`).
