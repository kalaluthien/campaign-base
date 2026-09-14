# Kind: development

A sub-issue of this kind builds something new under a specification, or finds
out whether an approach can work at all. Its rules are the base's own; this
reference holds only its profile, which a sub-issue with no `kind:` label
takes too.

## SDLC profile

`optional = skippable` -- the criterion decides each stage below the plan, per
change.

A change that writes no scenario of its own -- a stronger suite over a
scenario and a code path already in the tree -- has its Spec and its Code by
its tests witnessing and driving them (`reusedStages`). Each profile a kind
states lets it write that test first, since each lets Spec go; and the change
drops no witness, every scenario witnessed before it staying witnessed
(`FeaturelessKeeps`, check-sdlc-tie.py's T8).
