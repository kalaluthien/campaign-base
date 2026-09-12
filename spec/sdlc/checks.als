/*
 * The disciplines over sdlc/system and the witnesses -- a full chain, a
 * prose-only change with nothing below its plan, the tie broken by a rename at
 * each of its three ends, and each half of the skip rule -- then what must
 * hold under each discipline, the counterexample each one's absence admits,
 * and the floor that says every event is reachable at all.
 * sdlc/system.als is this entity's entry point.
 */
module sdlc/checks

open sdlc/system

/* ---------------- profiles ---------------- */

/* THE TWO PROFILES THE WITNESSES RUN UNDER. `development` is this campaign's
   own kind: the model before the code, and a test that failed first. Neither
   is a stage the KIND forbids skipping, because each is already refused by
   the criterion wherever there is anything to refuse -- a change that wrote a
   code path may skip neither Spec nor Test. So its profile is every skippable
   stage, each still gated by the criterion: all three go for a change that
   writes nothing that runs (`S2a_ProseOnlyChange`), and Test and Code for one
   that wrote only its scenario (`S6a_DevelopmentTestWaiver`). `analysis`,
   `migration` and `research` state the same profile and differ only in what
   their changes write, which no command here separates, so they have no
   witness of their own.

   THE PROFILE IS WHAT A KIND NARROWS BELOW THE CRITERION, and development
   narrows nothing -- so it does not witness that half of `maySkip`, and
   `prototyping` is here to. It keeps the running thing, and
   `S6_PrototypingTestWaiver` is the profile half on its own. Its one optional
   stage, Spec, is dead as a waiver rather than narrow: a change the criterion
   lets skip Spec wrote nothing that runs, and this kind lets neither Test nor
   Code go, so no landing change of it ever skips its scenario
   (`S7_PrototypingSpecWaiver`, against `S7a_DevelopmentSpecWaiver` at the
   same scope). Every profile line is the procedure's to state, in this
   vocabulary: `development`'s is the default in the campaign's AGENTS.md,
   from the template .claude/skills/opening-campaign/assets/AGENTS.md, and the
   other four kinds' are one line each in their references, kind-<k>.md. */
pred developmentProfile[c: Change] { c.optional = skippable }
pred prototypingProfile[c: Change] { c.optional = Spec }

/* ---------------- disciplines ---------------- */

/* A STAGE IS WRITTEN ONLY AFTER EACH STAGE THAT FEEDS IT IS WRITTEN OR MAY
   BE SKIPPED, read against the change at the write. The procedure's own
   order, and `OrderedByFeeds_Bites` is what its absence admits. It reads the
   stage that feeds the one written and no further back, so it does not walk
   the chain: while nothing below Plan exists every stage the kind lets a
   change skip may be skipped, so its first artifact may be a test with no
   plan written, and, where the kind lets it skip Test, a code path. Nothing
   refuses that order: the landing reads what the change holds when it lands,
   not the order it was written in, and refuses such a change only if Intent
   or Plan is still absent then, since neither is ever skippable. It bounds
   when a stage may be reached and never whether the absence it leaves is
   licensed at the end: that reading is `landDiscipline`'s, and
   `S5b_WithoutTheLandingCheck` is the chain the order lets through. */
pred orderDiscipline {
  always (Step.event = Write implies
    (let c = Step.artifact.change |
       all p: feeds.(Step.artifact.stage) | p in writtenStages[c] or maySkip[c, p]))
}

/* THE CHECK AT THE COMMIT: the tree a commit leaves is tied, save what the
   allow-list exempts, and every witness it declares names a scenario. Read
   on the tree AFTER the commit, so a rename that leaves a name dangling is
   refused -- even where another name still ties the code path
   (`WitnessesResolve_Bites`). This is the pre-commit check the campaign's
   Scope names, scripts/check-sdlc-tie.py. */
pred commitCheck {
  always ((Step.event in Write + Rename) implies after (everyCodeHasScenario and everyWitnessExists))
}
/* THE ALLOW-LIST NEVER GROWS. Without it the commit check is green over any
   debt at all: a commit writes an untied code path and lists it in the same
   step (`DebtNeverGrows_Bites`). The guard keeps it by judging a path the
   commit adds, and a tied path the commit unties, before it reads the list;
   what the list may still do is shrink, one line per path tied. */
pred licenceNeverGrows { always Licensed' in Licensed }
pred tieDiscipline { commitCheck and licenceNeverGrows }

/* THE CHECK AT THE LANDING: every stage the change has no artifact for is
   one the profile and the criterion license, read against the change as it
   is when it lands. A landing is a merge, so this reading belongs where the
   merge is gated -- the pull request's `check` -- and not to the commit,
   where a test written before its code path would read as an unlicensed
   absence of Code. */
pred landDiscipline {
  always (Step.event = Land implies all s: absentStages[Step.subject] | maySkip[Step.subject, s])
}

pred allDisciplines { orderDiscipline and tieDiscipline and landDiscipline }

/* ---------------- witnesses ---------------- */

/* One artifact per stage, written in the order `feeds` asks for, and the
   change lands with its code path walking back to its scenario. */
pred S1_FullChain {
  allDisciplines
  one c: Change {
    developmentProfile[c]
    all s: Stage | one change.c & stage.s
    eventually (c in Landed and no absentStages[c] and all k: change.c & stage.Code | tied[k])
  }
}

/* A PROSE-ONLY CHANGE OF A DEVELOPMENT CAMPAIGN: a procedure reference, a
   README, a comment. Intent and plan written, nothing below them, and every
   stage below Plan absent by the criterion -- the change wrote nothing that
   runs, so there is nothing to formalise and nothing to test. It lands, and
   the tree it leaves is tied vacuously: it wrote no code path for a scenario
   to reach. `S5` is this absence once a code path exists. */
pred S2a_ProseOnlyChange {
  allDisciplines
  one c: Change {
    developmentProfile[c]
    change.c.stage = Intent + Plan
    eventually (c in Landed and absentStages[c] = skippable and everyCodeHasScenario)
  }
}

/* A landed full chain, then its code path is renamed and nothing answers to
   the new name: the tree is untied. Every discipline but the commit check
   holds, which is the point -- nothing else reads a tie. The scope holds a
   sixth artifact for the new name. */
pred S4_CodeRenameBreak {
  orderDiscipline and landDiscipline
  one c: Change {
    developmentProfile[c]
    eventually (c in Landed and (all s: Stage | one writtenOf[c] & stage.s) and everyCodeHasScenario
                and eventually (Step.event = Rename and Step.artifact.stage = Code
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
  orderDiscipline and landDiscipline
  one c: Change {
    developmentProfile[c]
    eventually (c in Landed and (all s: Stage | one writtenOf[c] & stage.s) and everyCodeHasScenario
                and eventually (Step.event = Rename and Step.artifact.stage = Spec
                                and everyCodeHasScenario and after not everyCodeHasScenario))
  }
}

/* The scenario rename the guard admits: the scenario is renamed and, in the
   same commit, the tests declaring it leave for fresh ones, so the tree is
   tied on both sides of the step. The test that enters belongs to another
   change than the scenario -- a test may declare a scenario of any change --
   which is where `rename`'s bound on the changes a test may enter reads
   anything: at one change it holds of every rename that moves a test. Bound
   it to the scenario's own change and this is UNSAT; drop it and
   `OrderedByFeeds` and `AbsenceLicensed` fail. */
pred S4e_ScenarioRenameWithItsTests {
  allDisciplines
  eventually (Step.event = Rename and Step.artifact.stage = Spec
              and some Written & stage.Code
              and some (Written' - Written) - change.(Step.artifact.change))
}

/* The rename the check admits: the code path's new name still answers to
   the test paired with it, and the tree stays tied through it. */
pred S4a_TiedCodeRename {
  allDisciplines
  one c: Change {
    developmentProfile[c]
    change.c.stage = Stage
    eventually (Step.event = Rename and Step.artifact.stage = Code and some drives.(Step.artifact))
    always everyCodeHasScenario
  }
}

/* THE THIRD END: the landed chain's TEST is renamed, and the code path it
   drove is untied -- `drives` pairs two names, so moving either file breaks
   it.

   `S4d` is the half the same rename does NOT break, and it is UNSAT: a test's
   `witnesses` are a declaration in its own text, which survives the file
   being moved. The pair pins the asymmetry -- make `rename` copy `drives`
   too and `S4c` goes UNSAT; stop it copying `witnesses` and `S4d` goes SAT. */
pred S4c_TestRenameBreak {
  orderDiscipline and landDiscipline
  one c: Change {
    developmentProfile[c]
    eventually (c in Landed and (all s: Stage | one writtenOf[c] & stage.s) and everyCodeHasScenario
                and eventually (Step.event = Rename and Step.artifact.stage = Test
                                and everyCodeHasScenario and after not everyCodeHasScenario))
  }
}
pred S4d_TestRenameWitnessLoss {
  orderDiscipline and landDiscipline
  eventually (Step.event = Rename and Step.artifact.stage = Test and some Step.artifact.witnesses
              and no b: Written' - Written | b.witnesses = Step.artifact.witnesses)
}

/* A CODE PATH WITH NO SCENARIO: no trace lands a change that wrote one, and
   the kind is not pinned because the criterion decides it alone. The order
   does not refuse the chain -- Spec is optional under every profile here, and
   the criterion is true for as long as nothing that runs is written -- so a
   change may go past its scenario and on to write the code path, which is
   `S5b`: the Spec skip licensed at the write that passed it and stale by the
   landing. What refuses it is the merge: the code path turns the criterion
   false, so the absence is unlicensed by the landing and `landDiscipline`
   reads the criterion again there. `S5a` drops the commit check and the chain
   is refused all the same, which says the tie is not what refuses it; the
   scope holds two changes because the tie reads the TREE, so a scenario and
   a test of another change could reach the path. The tie does not widen the
   licence either: `criterion` reads what the CHANGE wrote, never what the
   tree ties. */
pred codeWithoutSpec[c: Change] {
  eventually (c in Landed
              and some writtenOf[c] & stage.Code
              and no writtenOf[c] & stage.Spec)
}
pred S5_CodeWithoutSpec         { allDisciplines and some c: Change | codeWithoutSpec[c] }
pred S5a_WithoutTheCommitCheck  { orderDiscipline and landDiscipline
                                  some c: Change | codeWithoutSpec[c] }
pred S5b_WithoutTheLandingCheck { orderDiscipline and some c: Change | codeWithoutSpec[c] }

/* THE PROFILE HALF OF `maySkip`, ON ITS OWN. A `prototyping` change that wrote
   its scenario and neither a test nor a code path: the criterion holds --
   nothing runs -- and the kind refuses the absence all the same, because the
   running thing is what this kind never goes without. No trace lands it.
   `S6a` is the same chain under a kind that allows it, so neither the shape
   nor the scope is what refuses it here, and the pair is what catches
   `s in c.optional` going missing from `maySkip`. */
pred S6_PrototypingTestWaiver {
  allDisciplines
  one c: Change {
    prototypingProfile[c]
    change.c.stage = Intent + Plan + Spec
    eventually (c in Landed and absentStages[c] = Test + Code)
  }
}
pred S6a_DevelopmentTestWaiver {
  allDisciplines
  one c: Change {
    developmentProfile[c]
    change.c.stage = Intent + Plan + Spec
    eventually (c in Landed and absentStages[c] = Test + Code)
  }
}

/* `prototypingProfile` LICENSES NOTHING A LANDING CHANGE CAN USE, which is
   not the same as being narrow. The criterion lets a change skip Spec only
   when it wrote nothing that runs; this kind lets neither Test nor Code go, so
   such a change cannot land, and one that does land wrote a code path and is
   refused Spec by the criterion (`S5_CodeWithoutSpec`). `S7a` is the same
   question under a kind that narrows nothing, so neither the shape nor the
   scope is what refuses `S7`. */
pred S7_PrototypingSpecWaiver {
  allDisciplines
  one c: Change { prototypingProfile[c] and eventually (c in Landed and Spec in absentStages[c]) }
}
pred S7a_DevelopmentSpecWaiver {
  allDisciplines
  one c: Change { developmentProfile[c] and eventually (c in Landed and Spec in absentStages[c]) }
}

/* ---------------- the order ---------------- */

/* Under `orderDiscipline`, every stage a change has written stands on each
   stage that feeds it: written, or skippable at some earlier write of the
   stage. The second half is read with `once` because a licence is read at
   the write -- a later artifact of the same change can turn it false, and the
   order still held (`S5b_WithoutTheLandingCheck`). Without the discipline the
   same shape has a counterexample, and `OrderedByFeeds_Bites` demands it: a
   code path written before the scenario that would have described it. */
assert OrderedByFeeds {
  orderDiscipline implies always
    all c: Change, s: writtenStages[c], p: feeds.s |
      p in writtenStages[c]
      or once (Step.event = Write and Step.artifact in change.c & stage.s and maySkip[c, p])
}
pred OrderedByFeeds_Bites {
  not orderDiscipline
  eventually some c: Change, s: writtenStages[c], p: feeds.s |
    p not in writtenStages[c]
    and historically not (Step.event = Write and Step.artifact in change.c & stage.s and maySkip[c, p])
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
   stays tied through the other -- bd2143d's shape, which a check reading
   `everyCodeHasScenario` alone passed. The last conjunct pins that shape:
   the test the rename left declaring a dead name still ties a written code
   path, so it declared two. */
assert WitnessesResolve {
  tieDiscipline implies always everyWitnessExists
}
pred WitnessesResolve_Bites {
  always everyCodeHasScenario
  eventually (Step.event = Rename and Step.artifact.stage = Spec
              and everyWitnessExists and after not everyWitnessExists
              and after some witnesses.(Artifact - Written) & (Artifact.tie).Written)
}

/* ---------------- the skip rule ---------------- */

/* Under `landDiscipline`, every stage a landed change has no artifact for
   was licensed, and stays so: a landed change writes nothing more, a rename
   keeps its stages, and its profile is static. Without it: a change lands
   with an absence its kind or the criterion refuses. */
assert AbsenceLicensed {
  landDiscipline implies always all c: Landed, s: absentStages[c] | maySkip[c, s]
}
pred AbsenceLicensed_Bites {
  not landDiscipline
  eventually some c: Landed, s: absentStages[c] | not maySkip[c, s]
}

/* ---------------- reachability floor ----------------
 * An event no trace can reach silently removes a whole question from the
 * commands above, and an over-tight frame is the cheapest way to cause it
 * without any command turning red.
 */
pred Cov_Write  { eventually Step.event = Write }
pred Cov_Rename { eventually Step.event = Rename }
pred Cov_Land   { eventually Step.event = Land }

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
run S5_CodeWithoutSpec         for 2 Change, 6 Artifact, 10 steps expect 0
run S5a_WithoutTheCommitCheck  for 2 Change, 6 Artifact, 10 steps expect 0
run S5b_WithoutTheLandingCheck for 2 Change, 6 Artifact, 10 steps expect 1
run S6_PrototypingTestWaiver   for exactly 1 Change, exactly 3 Artifact, 10 steps expect 0
run S6a_DevelopmentTestWaiver  for exactly 1 Change, exactly 3 Artifact, 10 steps expect 1
run S7_PrototypingSpecWaiver   for exactly 1 Change, 6 Artifact, 12 steps expect 0
run S7a_DevelopmentSpecWaiver  for exactly 1 Change, 6 Artifact, 12 steps expect 1

-- the order: holds under the discipline, and has a counterexample without it.
-- One change: every term of the order is one change's, so a second adds only
-- interleaving, and at 2 Change the check ran past ten minutes.
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

-- the skip rule: every absence is licensed under the landing check, and not without it
check AbsenceLicensed          for 2 Change, 6 Artifact, 10 steps expect 0
run   AbsenceLicensed_Bites    for 2 Change, 6 Artifact, 10 steps expect 1

-- every own event fires in some trace
run Cov_Write   for 2 Change, 4 Artifact, 8 steps expect 1
run Cov_Rename  for 2 Change, 4 Artifact, 8 steps expect 1
run Cov_Land    for 2 Change, 4 Artifact, 8 steps expect 1
