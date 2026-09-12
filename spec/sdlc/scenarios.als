/*
 * The disciplines over sdlc/system, and the witnesses: a full chain, a
 * prose-only change with nothing below its plan, a docs waiver and its
 * remedy, and the tie broken by a rename at each of its three ends.
 * sdlc/system.als is this entity's entry point.
 */
module sdlc/scenarios

open sdlc/system

/* ---------------- profiles ---------------- */

/* THE TWO KINDS THE WITNESSES RUN UNDER. `development` is this campaign's
   own kind: the model before the code, a test that failed first, and a view
   only when the model added a shape. None of those is a stage the KIND forbids
   skipping, because each is already refused by its own criterion wherever
   there is anything to refuse -- a change that wrote a code path may skip
   neither Spec nor Test, and one whose scenario added a shape may not skip
   Docs. So its profile is every skippable stage, each still gated by its own
   criterion: Test and Code go for every change that writes neither, whatever
   its scenario added (`S6b_TestWaiverWithAShape`), and Spec for one that
   also wrote no view. `maySkip` is a conjunction, so the profile has no say
   in a criterion, and the Docs criterion refuses that skip wherever the
   scenario added a shape (`S3a_DocsWaiverOverAShape`). A scenario and a
   view alone land (`S6a_DevelopmentTestWaiver`), and `S2a_ProseOnlyChange` is the
   narrowest. `research` states the same profile and differs only in what its
   changes write, which no command here separates, so it has no witness of
   its own.

   THE PROFILE IS WHAT A KIND NARROWS BELOW THE CRITERION, and development
   narrows nothing -- so it does not witness that half of `maySkip`, and
   `prototyping` is here to. It keeps the running thing, and
   `S6_PrototypingTestWaiver` is the profile half on its own.
   Its `Spec` is dead as a waiver rather than narrow: a change that could skip
   Spec by criterion wrote nothing in Docs, Test or Code, and this kind lets
   neither Test nor Code go, so no landing change of it ever skips its scenario
   (`S7_PrototypingSpecWaiver`, against `S7a_DevelopmentSpecWaiver` at
   the same scope). What the profile leaves live is the Docs waiver. The other
   kinds' profile lines are the procedure's to state, one line each in the
   kind references, kind-<k>.md, in this vocabulary. */
pred developmentProfile[c: Change] { c.optional = skippable }
pred prototypingProfile[c: Change] { c.optional = Spec + Docs }

/* ---------------- disciplines ---------------- */

/* A STAGE IS WRITTEN ONLY AFTER EACH STAGE THAT FEEDS IT IS WRITTEN OR MAY
   BE SKIPPED, read against the change at the write. The procedure's own
   order, and `OrderedByFeeds_Bites` in checks.als is what its absence admits.
   It reads the stages that feed the one written and no further back, so it
   does not walk the chain: while nothing below Plan exists every stage the
   kind lets a change skip may be skipped, so its first artifact may be a test
   with no plan written, and, where the kind lets it skip Test, a code path.
   Nothing refuses that order: the landing reads what the change holds when
   it lands, not the order it was written in, and refuses such a change only
   if Intent or Plan is still absent then, since neither is ever skippable. It
   bounds when a stage may be reached and never whether the absence it leaves
   is licensed at the end: that reading is `landDiscipline`'s, and
   `S5b_WithoutTheLandingCheck` is the chain the order lets through. */
pred orderDiscipline {
  always (Step.event = Write implies
    (let c = Step.artifact.change |
       all p: feeds.(Step.artifact.stage) | p in writtenStages[c] or maySkip[c, p]))
}

/* THE CHECK AT THE COMMIT: the tree a commit leaves is tied, and every
   witness it declares names a scenario. Read on the tree AFTER the commit, so
   a rename that leaves a name dangling is refused -- even where another name
   still ties the code path (`WitnessesResolve_Bites`). This is the pre-commit
   check the campaign's Scope names. */
pred tieDiscipline {
  always ((Step.event in Write + Rename) implies after (everyCodeHasScenario and everyWitnessExists))
}

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
   stage below Plan absent by its own criterion -- the change wrote no view, no
   test and no code path, so there is nothing to formalise, nothing to show and
   nothing that runs. It lands, and the tree it leaves is tied vacuously: it
   wrote no code path for a scenario to reach. `S5` is this absence once a
   code path exists. */
pred S2a_ProseOnlyChange {
  allDisciplines
  one c: Change {
    developmentProfile[c]
    change.c.stage = Intent + Plan
    eventually (c in Landed and absentStages[c] = skippable and everyCodeHasScenario)
  }
}

/* A development change whose scenario adds no shape skips its view and
   lands with the rest of the chain written. */
pred S3_DocsWaiver {
  allDisciplines
  no AddsShape
  one c: Change {
    developmentProfile[c]
    change.c.stage = Stage - Docs
    eventually (c in Landed and absentStages[c] = Docs)
  }
}

/* The same absence when the scenario DID add a shape: no trace lands it. */
pred S3a_DocsWaiverOverAShape {
  allDisciplines
  one c: Change {
    developmentProfile[c]
    eventually (c in Landed and Docs in absentStages[c] and some writtenOf[c] & AddsShape)
  }
}

/* The remedy the landing check leaves: the code path went in while the view
   could be skipped, a scenario then added a shape, and the change writes the
   view after all and lands. The finding in checks.als is this chain without
   the view. */
pred S3b_LateDocs {
  allDisciplines
  one c: Change {
    developmentProfile[c]
    eventually (Step.event = Write and Step.artifact in change.c & stage.Docs
                and Docs in absentStages[c]
                and some writtenOf[c] & stage.Code
                and some writtenOf[c] & AddsShape)
    eventually c in Landed
  }
}

/* A landed full chain, then its code path is renamed and nothing answers to
   the new name: the tree is untied. Every discipline but the commit check
   holds, which is the point -- nothing else reads a tie. The scope holds a
   seventh artifact for the new name. */
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
   arrow along and this is UNSAT -- and it is the T3 the check refuses: the
   rename that moves no test with it. */
pred S4b_ScenarioRenameBreak {
  orderDiscipline and landDiscipline
  one c: Change {
    developmentProfile[c]
    eventually (c in Landed and (all s: Stage | one writtenOf[c] & stage.s) and everyCodeHasScenario
                and eventually (Step.event = Rename and Step.artifact.stage = Spec
                                and everyCodeHasScenario and after not everyCodeHasScenario))
  }
}

/* The scenario rename the check admits, its T3 allow case: the scenario is
   renamed and, in the same commit, the tests declaring it leave for fresh
   ones, so the tree is tied on both sides of the step. The test that enters
   belongs to another change than the scenario -- a test may declare a
   scenario of any change -- which is where `rename`'s bound on the changes
   a test may enter reads anything: at one change it holds of every rename
   that moves a test. Bound it to the scenario's own change and this is
   UNSAT; drop it and `OrderedByFeeds` and `AbsenceLicensed` fail. */
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
   it. This is the guard's T2 read from the suite's side.

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
   its criterion is true for as long as nothing below Spec is written -- so a
   change may go past its scenario and on to write the code path, which is
   `S5b`. What refuses it is the merge: the code path turns Spec's criterion
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
   its scenario and its view and neither a test nor a code path: `criterion`
   holds for Test and for Code -- nothing runs -- and the kind refuses the
   absence all the same, because the running thing is what this kind never
   goes without. No trace lands it. `S6a` is the same chain under a kind that
   allows it, so neither the shape nor the scope is what refuses it here, and
   the pair is what catches `s in c.optional` going missing from `maySkip`. */
pred S6_PrototypingTestWaiver {
  allDisciplines
  one c: Change {
    prototypingProfile[c]
    change.c.stage = Intent + Plan + Spec + Docs
    eventually (c in Landed and absentStages[c] = Test + Code)
  }
}
pred S6a_DevelopmentTestWaiver {
  allDisciplines
  one c: Change {
    developmentProfile[c]
    change.c.stage = Intent + Plan + Spec + Docs
    eventually (c in Landed and absentStages[c] = Test + Code)
  }
}

/* THE SAME ABSENCE WHEN THE SCENARIO DID ADD A SHAPE: it is licensed still,
   because the Test and Code criteria read what the change wrote below them
   and nothing else. The change owes its view and writes it. */
pred S6b_TestWaiverWithAShape {
  allDisciplines
  one c: Change {
    developmentProfile[c]
    change.c.stage = Intent + Plan + Spec + Docs
    eventually (c in Landed and absentStages[c] = Test + Code and some writtenOf[c] & AddsShape)
  }
}

/* THE `Spec` HALF OF `prototypingProfile` LICENSES NOTHING A LANDING CHANGE
   CAN USE, which is not the same as being narrow. `criterion` lets a change
   skip Spec only when it wrote nothing in Docs, Test or Code; this kind lets
   neither Test nor Code go, so such a change cannot land, and one that does
   land wrote a code path and is refused Spec by the criterion
   (`S5_CodeWithoutSpec`). `S7a` is the same question under a kind that
   narrows nothing, so neither the shape nor the scope is what refuses `S7`. */
pred S7_PrototypingSpecWaiver {
  allDisciplines
  one c: Change { prototypingProfile[c] and eventually (c in Landed and Spec in absentStages[c]) }
}
pred S7a_DevelopmentSpecWaiver {
  allDisciplines
  one c: Change { developmentProfile[c] and eventually (c in Landed and Spec in absentStages[c]) }
}

/* ---------------- commands ---------------- */

run S1_FullChain               for exactly 1 Change, exactly 6 Artifact, 10 steps expect 1
run S2a_ProseOnlyChange        for exactly 1 Change, exactly 2 Artifact, 10 steps expect 1
run S3_DocsWaiver              for exactly 1 Change, exactly 5 Artifact, 10 steps expect 1
run S3a_DocsWaiverOverAShape   for exactly 1 Change, 6 Artifact, 10 steps expect 0
run S3b_LateDocs               for exactly 1 Change, 7 Artifact, 12 steps expect 1
run S4_CodeRenameBreak         for exactly 1 Change, exactly 7 Artifact, 10 steps expect 1
run S4b_ScenarioRenameBreak    for exactly 1 Change, exactly 7 Artifact, 10 steps expect 1
run S4e_ScenarioRenameWithItsTests for 2 Change, 7 Artifact, 10 steps expect 1
run S4a_TiedCodeRename         for exactly 1 Change, exactly 7 Artifact, 10 steps expect 1
run S4c_TestRenameBreak        for exactly 1 Change, exactly 7 Artifact, 10 steps expect 1
run S4d_TestRenameWitnessLoss  for exactly 1 Change, exactly 7 Artifact, 10 steps expect 0
run S5_CodeWithoutSpec         for 2 Change, 6 Artifact, 10 steps expect 0
run S5a_WithoutTheCommitCheck  for 2 Change, 6 Artifact, 10 steps expect 0
run S5b_WithoutTheLandingCheck for 2 Change, 6 Artifact, 10 steps expect 1
run S6_PrototypingTestWaiver   for exactly 1 Change, exactly 4 Artifact, 10 steps expect 0
run S6a_DevelopmentTestWaiver  for exactly 1 Change, exactly 4 Artifact, 10 steps expect 1
run S6b_TestWaiverWithAShape   for exactly 1 Change, exactly 4 Artifact, 10 steps expect 1
run S7_PrototypingSpecWaiver   for exactly 1 Change, 6 Artifact, 12 steps expect 0
run S7a_DevelopmentSpecWaiver  for exactly 1 Change, 6 Artifact, 12 steps expect 1
