/*
 * What must hold of sdlc/system under each discipline, the counterexample
 * each discipline's absence admits, the one chain that keeps the order and
 * the commit check and still lands wrong, and the floor that says every event
 * is reachable at all. sdlc/system.als is this entity's entry point.
 */
module sdlc/checks

open sdlc/scenarios

/* ---------------- the order ---------------- */

/* Under `orderDiscipline`, every stage a change has written stands on each
   stage that feeds it: written, or skippable when the stage was first
   written. The second half is read with `once` because a licence is read at
   the write -- a later artifact of the same change can turn it false, and the
   order still held (`SkipReadAtTheTimeIsNotEnough`). Without the discipline
   the same shape has a counterexample, and `OrderedByFeeds_Bites` demands it:
   a code path written before the scenario that would have described it. */
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

/* Under `tieDiscipline`, the tree is tied at every state and not only at
   each commit, since nothing but a commit moves Written. Without it: a code
   path no test drives, or a rename that left a declaration dangling. */
assert TreeStaysTied {
  tieDiscipline implies always everyCodeHasScenario
}
pred TreeStaysTied_Bites {
  not tieDiscipline
  eventually not everyCodeHasScenario
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
   keeps its stages and which of its scenarios added a shape, and its profile
   is static. Without it: a change lands with an absence its kind or its
   criterion refuses. */
assert AbsenceLicensed {
  landDiscipline implies always all c: Landed, s: absentStages[c] | maySkip[c, s]
}
pred AbsenceLicensed_Bites {
  not landDiscipline
  eventually some c: Landed, s: absentStages[c] | not maySkip[c, s]
}

/* THE FINDING. A chain that keeps the order -- which reads every absent
   stage as licensed at the write that passes it -- and the commit check, and
   still lands with a view it was not licensed to skip: the code path went in
   while no scenario added a shape, and a later scenario of the same change
   added one. The criterion is a function of the change's final shape, so the
   reading that decides is the landing's, and `landDiscipline` is a mechanism
   of its own rather than the order's reading restated. */
pred SkipReadAtTheTimeIsNotEnough {
  orderDiscipline and tieDiscipline
  eventually some c: Landed | developmentProfile[c] and Docs in absentStages[c] and not maySkip[c, Docs]
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

-- the order: holds under the discipline, and has a counterexample without it.
-- One change: every term of the order is one change's, so a second adds only
-- interleaving, and at 2 Change the check ran past ten minutes.
check OrderedByFeeds           for exactly 1 Change, 6 Artifact, 10 steps expect 0
run   OrderedByFeeds_Bites     for exactly 1 Change, 6 Artifact, 10 steps expect 1

-- the tie: the tree stays tied under the commit check, and comes apart without it
check TreeStaysTied            for 2 Change, 6 Artifact, 10 steps expect 0
run   TreeStaysTied_Bites      for 2 Change, 6 Artifact, 10 steps expect 1
check WitnessesResolve         for 2 Change, 6 Artifact, 10 steps expect 0
run   WitnessesResolve_Bites   for 2 Change, 6 Artifact, 10 steps expect 1

-- the skip rule: every absence is licensed under the landing check, and not without it
check AbsenceLicensed          for 2 Change, 6 Artifact, 10 steps expect 0
run   AbsenceLicensed_Bites    for 2 Change, 6 Artifact, 10 steps expect 1

-- the order alone: licensed at every write, unlicensed at the landing
run   SkipReadAtTheTimeIsNotEnough for exactly 1 Change, exactly 6 Artifact, 10 steps expect 1

-- every own event fires in some trace
run Cov_Write   for 2 Change, 4 Artifact, 8 steps expect 1
run Cov_Rename  for 2 Change, 4 Artifact, 8 steps expect 1
run Cov_Land    for 2 Change, 4 Artifact, 8 steps expect 1
