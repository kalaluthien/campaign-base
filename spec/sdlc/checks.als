/*
 * The disciplines over sdlc/system and the witnesses -- a full chain, a
 * prose-only change with nothing below its plan, the tie broken by a rename at
 * each of its three ends, each input of the skip rule, reuse being a change
 * that adds no feature, a scenario nothing witnesses removed -- then what
 * must hold under each discipline, the counterexample each one's absence
 * admits, and the floor that says every event is reachable at all.
 * sdlc/system.als is this entity's entry point.
 */
module sdlc/checks

open sdlc/system

/* NO KIND NARROWS THE SKIP: `maySkip` reads the criterion alone, and every
   kind's changes run under it. `development` is this campaign's own kind:
   the model before the code, and a test that failed first. All three
   skippable stages go for a change that writes nothing that runs
   (`S2a_ProseOnlyChange`), and Test and Code for one that wrote only its
   scenario (`S6a_DevelopmentTestWaiver`); `research` and `maintenance`
   differ only in what their changes write, which no command here separates,
   so they have no witness of their own. */

/* ---------------- disciplines ---------------- */

/* A STAGE IS WRITTEN ONLY AFTER EACH STAGE THAT FEEDS IT IS WRITTEN OR MAY
   BE SKIPPED, read against the change at the write. The procedure's own
   order, and `OrderedByFeeds_Bites` is what its absence admits. It reads the
   stage that feeds the one written and no further back, so it does not walk
   the chain: while nothing below Plan exists every skippable stage may be
   skipped, so its first artifact may be a test with no plan written, and so
   may a code path. Nothing
   refuses that order: the landing reads what the change holds when it lands,
   not the order it was written in, and refuses such a change only if Intent
   or Plan is still absent then, since neither is ever skippable. It bounds
   when a stage may be reached and never whether the absence it leaves is
   licensed at the end: that reading is `mergeDiscipline`'s, and
   `S5b_WithoutTheLandingCheck` is the chain the order lets through. */
pred orderDiscipline {
  always (Step.event = WriteArtifact implies
    (let c = Step.artifact.change |
       all p: feeds.(Step.artifact.stage) | p in writtenStages[c] or maySkip[c, p]))
}

/* THE CHECK AT THE COMMIT: the tree a commit leaves is tied, save what the
   allow-list exempts, and every witness it declares names a scenario. Read
   on the tree AFTER the commit, so a rename that leaves a name dangling is
   refused -- even where another name still ties the code path
   (`WitnessesResolve_Bites`), and so is a removal that takes a suite and
   leaves its code path, or takes a scenario a suite still declares. This is
   the pre-commit check the campaign's Scope names, scripts/check-sdlc-tie.py. */
pred commitCheck {
  always ((Step.event in WriteArtifact + RenameArtifact + RemoveArtifact) implies after (everyCodeHasScenario and everyWitnessExists))
}
/* THE ALLOW-LIST NEVER GROWS. Without it the commit check is green over any
   debt at all: a commit writes an untied code path and lists it in the same
   step (`DebtNeverGrows_Bites`). The guard keeps it by judging a path the
   commit adds, and a tied path the commit unties, before it reads the list;
   what the list may still do is shrink, one line per path tied. */
pred licenceNeverGrows { always Licensed' in Licensed }
pred tieDiscipline { commitCheck and licenceNeverGrows }

/* THE CHECK AT THE LANDING: every stage the change has no artifact for is
   one the criterion licenses, read against the change as it
   is when it lands. A landing is a merge, so this reading belongs where the
   merge is gated -- the pull request's `check` -- and not to the commit,
   where a test written before its code path would read as an unlicensed
   absence of Code. scripts/check-merge-review.py --merge is that reading. */
pred mergeDiscipline {
  always (Step.event = MergeChange implies all s: absentStages[Step.subject] | maySkip[Step.subject, s])
}

/* A CHANGE THAT ADDS NO FEATURE TAKES NO SCENARIO AWAY: no commit of a
   change with no scenario of its own moves one out of the tree. A write never
   removes, so a rename is the step it bites; a removal is left out of its
   scope, a feature change by name as the guard reads a scenario's removal.
   Read by names, as scripts/check-sdlc-tie.py reads it, a commit that leaves
   the command list as it was keeps every scenario by definition; what the
   guard refuses, as T8, is the consequence, `FeaturelessKeeps`, over two
   edits this discipline does not read -- a suite's declaration rewritten in
   place, which this model has no step for, and a suite deleted in place,
   which is `removeArtifact`. */
pred keepDiscipline {
  always ((Step.event in WriteArtifact + RenameArtifact and featureless[Step.subject])
          implies Written & (stage.Spec - Html) in Written')
}

/* A REMOVAL LEAVES NO NAME BEHIND: after the step no written text names what
   left through `witnesses` or `refines`, unless that text left in the same
   step -- an artifact goes with everything naming it, in one commit. Under
   `tieDiscipline` its `witnesses` half is `everyWitnessExists` read after the
   removal; `refines`, an html form's names, is the half nothing else reads,
   so it is what `RemovalLeavesNoDangling_Bites` exhibits. `drives` is not
   read: a test may name a code path not yet written, and the tie guard
   refuses no suite whose code path is gone. scripts/check-sdlc-tie.py reads
   it as T3 and T6. */
pred removeDiscipline {
  always (Step.event = RemoveArtifact implies no Written'.(witnesses + refines) & (Written - Written'))
}

pred allDisciplines {
  orderDiscipline and tieDiscipline and mergeDiscipline and keepDiscipline and removeDiscipline
}

/* ---------------- witnesses ---------------- */

/* One artifact per stage, written in the order `feeds` asks for, and the
   change lands with its code path walking back to its scenario. */
pred S1_FullChain {
  allDisciplines
  one c: Change {
    all s: Stage | one change.c & stage.s
    eventually (c in Merged and no absentStages[c] and all k: change.c & stage.Code | tied[k])
  }
}

/* A PROSE-ONLY CHANGE OF A DEVELOPMENT CAMPAIGN: a procedure reference, a
   README, a comment. Intent and plan written, nothing below them, and every
   stage below Plan absent by the criterion -- the change wrote nothing that
   runs, so there is nothing to formalise and nothing to test. It lands, and
   the tree it leaves is tied vacuously: it wrote no code path for a scenario
   to reach. `S5a` is this absence once a code path exists. */
pred S2a_ProseOnlyChange {
  allDisciplines
  one c: Change {
    change.c.stage = Intent + Plan
    eventually (c in Merged and absentStages[c] = skippable and everyCodeHasScenario)
  }
}

/* A landed full chain, then its code path is renamed and nothing answers to
   the new name: the tree is untied. Every discipline but the commit check
   holds, which is the point -- nothing else reads a tie. The scope holds a
   sixth artifact for the new name. */
pred S4_CodeRenameBreak {
  orderDiscipline and mergeDiscipline
  one c: Change {
    eventually (c in Merged and (all s: Stage | one writtenOf[c] & stage.s) and everyCodeHasScenario
                and eventually (Step.event = RenameArtifact and Step.artifact.stage = Code
                                and everyCodeHasScenario and after not everyCodeHasScenario))
  }
}

/* The same break read at the scenario's end: the landed chain's SCENARIO is
   renamed and the test still declares the old one, so the code path is
   untied. This is the one command that pins which text carries which name
   -- with the scenario naming the test (`s -> t`) the rename would carry the
   arrow along and this is UNSAT -- and it is the rename the guard refuses:
   the one that moves no test with it. */
pred S4b_ScenarioRenameBreak {
  orderDiscipline and mergeDiscipline
  one c: Change {
    eventually (c in Merged and (all s: Stage | one writtenOf[c] & stage.s) and everyCodeHasScenario
                and eventually (Step.event = RenameArtifact and Step.artifact.stage = Spec
                                and everyCodeHasScenario and after not everyCodeHasScenario))
  }
}

/* The scenario rename the guard admits: the scenario is renamed and, in the
   same commit, the tests declaring it leave for fresh ones, so the tree is
   tied on both sides of the step. The test that enters belongs to another
   change than the scenario -- a test may declare a scenario of any change --
   which is where `renameArtifact`'s bound on the changes a test may enter reads
   anything: at one change it holds of every rename that moves a test. Bound
   it to the scenario's own change and this is UNSAT; drop it and
   `OrderedByFeeds` and `AbsenceLicensed` fail. */
pred S4e_ScenarioRenameWithItsTests {
  allDisciplines
  eventually (Step.event = RenameArtifact and Step.artifact.stage = Spec
              and some Written & stage.Code
              and some (Written' - Written) - change.(Step.artifact.change))
}

/* The rename the check admits: the code path's new name still answers to
   the test paired with it, and the tree stays tied through it. */
pred S4a_TiedCodeRename {
  allDisciplines
  one c: Change {
    change.c.stage = Stage
    eventually (Step.event = RenameArtifact and Step.artifact.stage = Code and some drives.(Step.artifact))
    always everyCodeHasScenario
  }
}

/* THE THIRD END: the landed chain's TEST is renamed, and the code path it
   drove is untied -- `drives` pairs two names, so moving either file breaks
   it.

   `S4d` is the half the same rename does NOT break, and it is UNSAT: a test's
   `witnesses` are a declaration in its own text, which survives the file
   being moved. The pair pins the asymmetry -- make `renameArtifact` copy `drives`
   too and `S4c` goes UNSAT; stop it copying `witnesses` and `S4d` goes SAT. */
pred S4c_TestRenameBreak {
  orderDiscipline and mergeDiscipline
  one c: Change {
    eventually (c in Merged and (all s: Stage | one writtenOf[c] & stage.s) and everyCodeHasScenario
                and eventually (Step.event = RenameArtifact and Step.artifact.stage = Test
                                and everyCodeHasScenario and after not everyCodeHasScenario))
  }
}
pred S4d_TestRenameWitnessLoss {
  orderDiscipline and mergeDiscipline
  eventually (Step.event = RenameArtifact and Step.artifact.stage = Test and some Step.artifact.witnesses
              and no b: Written' - Written | b.witnesses = Step.artifact.witnesses)
}

/* A CODE PATH WITH NO SCENARIO: no trace lands a change that wrote one, and
   the kind is not pinned because the criterion decides it alone. The order
   does not refuse the chain -- Spec is skippable, and the criterion is true
   for as long as nothing that runs is written -- so a
   change may go past its scenario and on to write the code path, which is
   `S5b`: the Spec skip licensed at the write that passed it and stale by the
   landing. What refuses it is the merge: the code path turns the criterion
   false, so the absence is unlicensed by the landing and `mergeDiscipline`
   reads the criterion again there. `S5a` drops the commit check and the chain
   is refused all the same, which says the tie is not what refuses it; the
   scope holds two changes because the tie reads the TREE, so a scenario and
   a test of another change could reach the path. The tie does not widen the
   licence either: `criterion` reads what the CHANGE wrote, never what the
   tree ties. "No scenario" is read at the landing and counts a reused one,
   which a later rename can take away from a change that landed with it. */
pred codeWithoutSpec[c: Change] {
  eventually (Step.event = MergeChange and Step.subject = c
              and some writtenOf[c] & stage.Code
              and Spec not in writtenStages[c] + reusedStages[c])
}
pred S5a_WithoutTheCommitCheck  { orderDiscipline and mergeDiscipline
                                  some c: Change | codeWithoutSpec[c] }
pred S5b_WithoutTheLandingCheck { orderDiscipline and some c: Change | codeWithoutSpec[c] }

pred S6a_DevelopmentTestWaiver {
  allDisciplines
  one c: Change {
    change.c.stage = Intent + Plan + Spec
    eventually (c in Merged and absentStages[c] = Test + Code)
  }
}

/* A CHANGE THAT ADDS NO FEATURE: a stronger suite over a scenario and a code
   path already in the tree. It writes its intent, its plan and a test and
   nothing else; the test witnesses a scenario another change wrote and drives
   that change's code path, so its Spec and its Code are reused, and it lands
   under every discipline. Its test turns the criterion false, so reuse is the
   one input of `maySkip` that licenses both absences. */
pred S8_FeaturelessChange {
  allDisciplines
  some c: Change {
    change.c.stage = Intent + Plan + Test
    eventually (c in Merged and featureless[c] and reusedStages[c] = Spec + Code
                and everyCodeHasScenario)
  }
}

/* DEAD ELIMINATION: a scenario no suite witnesses leaves the tree on its
   own, beside a code path that stays tied through another. What makes a
   scenario dead is judged outside the model; this says only how it leaves. */
pred S9_DeadElimination {
  allDisciplines
  eventually (Step.event = RemoveArtifact and Step.artifact.stage = Spec and Step.artifact not in Html
              and Step.artifact not in witnessed and Written' = Written - Step.artifact
              and (some k: Written & stage.Code | tied[k] and after tied[k])
              and everyCodeHasScenario and after everyCodeHasScenario)
}

/* A SCRIPT DELETED WITH ITS SUITE AND THE SCENARIO IT WITNESSED, in one
   commit: the scenario leaves with the suite declaring it and the code path
   tied through them. The removal the tie guard admits, and one a step
   taking one artifact at a time could not make: the suite left behind would
   declare a dead name. */
pred S9a_ChainRemovedInOneCommit {
  allDisciplines
  eventually (Step.event = RemoveArtifact and Step.artifact.stage = Spec
              and Step.artifact not in Written'
              and some k: (Written - Written') & stage.Code |
                    some Step.artifact.(tie.k) & (Written - Written'))
}

/* ---------------- the order ---------------- */

/* Under `orderDiscipline`, every stage a change has written stands on each
   stage that feeds it: written, or skippable at some earlier write of the
   stage. The second half is read with `once` because a licence is read at
   the write -- a later artifact of the same change can turn it false, and the
   order still held (`S5b_WithoutTheLandingCheck`). Without the discipline the
   same shape has a counterexample, and `OrderedByFeeds_Bites` demands it: a
   code path written before the scenario that would have described it. A
   removal takes a stage away from the change that wrote it, so a stage
   written on a feeding stage since removed stands on that removal. */
assert OrderedByFeeds {
  orderDiscipline implies always
    all c: Change, s: writtenStages[c], p: feeds.s |
      p in writtenStages[c]
      or once (Step.event = WriteArtifact and Step.artifact in change.c & stage.s and maySkip[c, p])
      or once (Step.event = RemoveArtifact and some (Written - Written') & change.c & stage.p
               and once (Step.event = WriteArtifact and Step.artifact in change.c & stage.s))
}
pred OrderedByFeeds_Bites {
  not orderDiscipline
  eventually some c: Change, s: writtenStages[c], p: feeds.s |
    p not in writtenStages[c]
    and historically not (Step.event = WriteArtifact and Step.artifact in change.c & stage.s and maySkip[c, p])
    and historically not (Step.event = RemoveArtifact and some (Written - Written') & change.c & stage.p
                          and once (Step.event = WriteArtifact and Step.artifact in change.c & stage.s))
}

/* ---------------- the tie ---------------- */

/* Under `tieDiscipline`, the tree is tied, save what the list exempts, at
   every state and not only at each commit, since nothing but a commit moves
   Written or the list. Without it: a code path no test drives, or a rename
   that left a declaration dangling. */
assert TreeStaysTied {
  tieDiscipline implies always everyCodeHasScenario
}
pred TreeStaysTied_Bites {
  not tieDiscipline
  eventually not everyCodeHasScenario
}

/* Under `tieDiscipline`, every untied code path in the tree has been on the
   list at every state so far: the debt is the list's as it stood at the
   start, never a path listed later. Without `licenceNeverGrows` the commit
   check alone passes a code path written untied and listed in the same
   commit, and the tree reads tied at every state. */
assert DebtNeverGrows {
  tieDiscipline implies always
    all k: Written & stage.Code | tied[k] or historically k in Licensed
}
pred DebtNeverGrows_Bites {
  commitCheck
  eventually some k: Written & stage.Code | not tied[k] and not historically k in Licensed
}

/* Under `tieDiscipline`, every declared witness names a written scenario at
   every state, for the same reason. Without its second half the tree can stay
   tied at every state and still carry a dead name: a test declares two
   scenarios, one is renamed and the text is not rewritten, and the code path
   stays tied through the other. The last conjunct pins that shape:
   the test the rename left declaring a dead name still ties a written code
   path, so it declared two. */
assert WitnessesResolve {
  tieDiscipline implies always everyWitnessExists
}
pred WitnessesResolve_Bites {
  always everyCodeHasScenario
  eventually (Step.event = RenameArtifact and Step.artifact.stage = Spec
              and everyWitnessExists and after not everyWitnessExists
              and after some witnesses.(Artifact - Written) & (Artifact.tie).Written)
}

/* No code path is tied through an html form: a test witnesses scenarios and a
   form refines them (`Html` in system.als), so a form is never the scenario a
   tie runs through. The tie guard reads a witness name against the commands
   alone, and would call such a code path T1. */
assert FormsTieNothing {
  always all k: Artifact | no (tie.k).Artifact & Html
}

/* ---------------- the skip rule ---------------- */

/* Under `mergeDiscipline`, every stage a landed change has no artifact for
   is licensed by the criterion, which stays so -- a landed change writes
   nothing more, and a rename keeps its stages -- or was reused when it
   landed. Reuse is read with `once` because it
   does not stay: a later rename can take the reused scenario away. Without
   the discipline: a change lands with an absence nothing licenses. A removal
   since the merge is the one other way a landed change loses a stage. */
assert AbsenceLicensed {
  mergeDiscipline implies always all c: Merged, s: absentStages[c] |
    (s in skippable and criterion[c])
    or once (Step.event = MergeChange and Step.subject = c and s in reusedStages[c])
    or once (Step.event = RemoveArtifact and c in Merged and some (Written - Written') & change.c & stage.s)
}
pred AbsenceLicensed_Bites {
  not mergeDiscipline
  eventually some c: Merged, s: absentStages[c] |
    not (s in skippable and criterion[c])
    and historically not (Step.event = MergeChange and Step.subject = c and s in reusedStages[c])
    and historically not (Step.event = RemoveArtifact and c in Merged and some (Written - Written') & change.c & stage.s)
}

/* ---------------- the keep rule ---------------- */

/* Under `keepDiscipline`, no write or rename by a change that adds no
   feature shrinks the witnessed set either, though the discipline names only the
   scenarios: a test leaves the tree only beside the scenario it witnesses,
   renamed in the same commit, and a renamed test keeps its declaration.
   Without it: such a change renames a scenario with the texts witnessing it,
   and the scenario they witnessed is gone. A removal is outside it: one by
   such a change can take a suite and shrink the set, which T8 reads by
   names and `keepDiscipline` does not. */
assert FeaturelessKeeps {
  keepDiscipline implies always
    ((Step.event in WriteArtifact + RenameArtifact and featureless[Step.subject]) implies witnessed in witnessed')
}
pred FeaturelessKeeps_Bites {
  orderDiscipline and tieDiscipline and mergeDiscipline
  eventually (Step.event in WriteArtifact + RenameArtifact and featureless[Step.subject]
              and witnessed not in witnessed')
}

/* ---------------- the removal rule ---------------- */

/* Under `removeDiscipline`, a removal from a tree whose every declared name
   resolves leaves one whose every declared name resolves: nothing the step
   takes is still named, and nothing enters. Without it, and with every other
   discipline kept: a scenario leaves while an html form still refines it. */
assert RemovalLeavesNoDangling {
  removeDiscipline implies always
    ((Step.event = RemoveArtifact and Written.(witnesses + refines) in Written)
     implies Written'.(witnesses + refines) in Written')
}
pred RemovalLeavesNoDangling_Bites {
  orderDiscipline and tieDiscipline and mergeDiscipline and keepDiscipline
  eventually (Step.event = RemoveArtifact and Written.(witnesses + refines) in Written
              and Written'.(witnesses + refines) not in Written')
}

/* ---------------- reachability floor ----------------
 * An event no trace can reach silently removes a whole question from the
 * commands above, and an over-tight frame is the cheapest way to cause it
 * without any command turning red.
 */
pred Cov_WriteArtifact  { eventually Step.event = WriteArtifact }
pred Cov_RenameArtifact { eventually Step.event = RenameArtifact }
pred Cov_RemoveArtifact { eventually Step.event = RemoveArtifact }
pred Cov_MergeChange   { eventually Step.event = MergeChange }

/* ---------------- commands ---------------- */

-- the witnesses
run S1_FullChain               for exactly 1 Change, exactly 5 Artifact, 10 steps expect 1
run S2a_ProseOnlyChange        for exactly 1 Change, exactly 2 Artifact, 10 steps expect 1
run S4_CodeRenameBreak         for exactly 1 Change, exactly 6 Artifact, 10 steps expect 1
run S4b_ScenarioRenameBreak    for exactly 1 Change, exactly 6 Artifact, 10 steps expect 1
run S4e_ScenarioRenameWithItsTests for 2 Change, 7 Artifact, 10 steps expect 1
run S4a_TiedCodeRename         for exactly 1 Change, exactly 6 Artifact, 10 steps expect 1
run S4c_TestRenameBreak        for exactly 1 Change, exactly 6 Artifact, 10 steps expect 1
run S4d_TestRenameWitnessLoss  for exactly 1 Change, exactly 6 Artifact, 10 steps expect 0
run S5a_WithoutTheCommitCheck  for 2 Change, 6 Artifact, 10 steps expect 0
run S5b_WithoutTheLandingCheck for 2 Change, 6 Artifact, 10 steps expect 1
run S6a_DevelopmentTestWaiver  for exactly 1 Change, exactly 3 Artifact, 10 steps expect 1
run S9_DeadElimination        for exactly 1 Change, exactly 6 Artifact, 10 steps expect 1
run S9a_ChainRemovedInOneCommit for exactly 1 Change, exactly 5 Artifact, 10 steps expect 1
-- S8 needs eight commits, so no trace shorter than nine states holds it; the
-- floor spares the solver refuting each shorter length, past ten minutes without it
run S8_FeaturelessChange       for 2 Change, 7 Artifact, 9..10 steps expect 1

-- the order: holds under the discipline, and has a counterexample without it.
-- One change: every term of the order is one change's, so a second adds only
-- interleaving.
check OrderedByFeeds           for exactly 1 Change, 6 Artifact, 10 steps expect 0
run   OrderedByFeeds_Bites     for exactly 1 Change, 6 Artifact, 10 steps expect 1

-- the tie: the tree stays tied under the commit check, and comes apart without
-- it; the list never grows under it, and grows without it
check TreeStaysTied            for 2 Change, 6 Artifact, 10 steps expect 0
run   TreeStaysTied_Bites      for 2 Change, 6 Artifact, 10 steps expect 1
check DebtNeverGrows           for 2 Change, 6 Artifact, 10 steps expect 0
run   DebtNeverGrows_Bites     for 2 Change, 6 Artifact, 10 steps expect 1
check WitnessesResolve         for 2 Change, 6 Artifact, 10 steps expect 0
run   WitnessesResolve_Bites   for 2 Change, 6 Artifact, 10 steps expect 1
check FormsTieNothing          for 1 Change, 6 Artifact, 10 steps expect 0

-- the skip rule: every absence is licensed under the landing check, and not without it
check AbsenceLicensed          for 2 Change, 6 Artifact, 10 steps expect 0
run   AbsenceLicensed_Bites    for 2 Change, 6 Artifact, 10 steps expect 1

-- the keep rule: a change that adds no feature keeps what is witnessed, and not without it
check FeaturelessKeeps         for 2 Change, 6 Artifact, 10 steps expect 0
run   FeaturelessKeeps_Bites   for 2 Change, 6 Artifact, 10 steps expect 1

-- the removal rule: a removal leaves no name behind under it, and does without it
check RemovalLeavesNoDangling  for 2 Change, 6 Artifact, 10 steps expect 0
run   RemovalLeavesNoDangling_Bites for 2 Change, 6 Artifact, 10 steps expect 1

-- every own event fires in some trace
run Cov_WriteArtifact   for 2 Change, 4 Artifact, 8 steps expect 1
run Cov_RenameArtifact  for 2 Change, 4 Artifact, 8 steps expect 1
run Cov_RemoveArtifact  for 2 Change, 4 Artifact, 8 steps expect 1
run Cov_MergeChange    for 2 Change, 4 Artifact, 8 steps expect 1
