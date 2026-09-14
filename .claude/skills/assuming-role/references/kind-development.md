# Kind: development

A sub-issue of this kind builds something new under a specification, or finds
out whether an approach can work at all. Its rules are the base's own; a
sub-issue with no `kind:` label takes this reference too.

A change that writes no scenario of its own -- a stronger suite over a
scenario and a code path already in the tree -- has its Spec and its Code by
its tests witnessing and driving them (`reusedStages`). The skip rule lets it
write that test first, since Spec is skippable; and the change drops no
witness, every scenario witnessed before it staying witnessed
(`FeaturelessKeeps`, check-sdlc-tie.py's T8).
