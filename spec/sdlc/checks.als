/*
 * What must hold of sdlc/system under each discipline, the counterexample
 * each discipline's absence admits, the one chain that keeps the worker's
 * reading and still lands wrong, and the floor that says every event is
 * reachable at all. sdlc/system.als is this entity's entry point.
 */
module sdlc/checks

open sdlc/scenarios

/* ---------------- the order ---------------- */

/* Under `orderDiscipline`, no artifact exists whose feeding stages are not
   done. Monotonic on its own -- `done` only grows, since the one event that
   shrinks `skipped` writes the stage it retracts -- so the discipline at each
   write is the invariant between them. Without it the
   same shape has a counterexample, and `OrderedByFeeds_Bites` demands it:
   a code path written before the scenario that would have described it. */
assert OrderedByFeeds {
  orderDiscipline implies always all a: Written, p: feeds.(a.stage) | done[a.change, p]
}
pred OrderedByFeeds_Bites {
  not orderDiscipline
  eventually some a: Written, p: feeds.(a.stage) | not done[a.change, p]
}

/* ---------------- the tie ---------------- */

/* Under `tieDiscipline`, the tree is tied at every state and not only at
   each commit, since nothing but a commit moves Written, `witnesses` or
   `drives`. Without it: a code path no test drives, or a rename that left a
   declaration dangling. */
assert TreeStaysTied {
  tieDiscipline implies always treeTied
}
pred TreeStaysTied_Bites {
  not tieDiscipline
  eventually not treeTied
}

/* Under `tieDiscipline`, every declared witness names a scenario at every
   state, for the same reason. Without its second half the tree can stay tied
   at every state and still carry a dead name: a test declares two scenarios,
   one is renamed and the text is not rewritten, and the code path stays tied
   through the other -- bd2143d's shape, which a check reading `treeTied` alone
   passed. The last conjunct pins that shape: the test the rename left spelling
   a dead name still ties a written code path, so it declared two. */
assert WitnessesResolve {
  tieDiscipline implies always witnessesResolve
}
pred WitnessesResolve_Bites {
  always treeTied
  eventually (Now.event = Rename and Now.at = Spec
              and witnessesResolve and after not witnessesResolve
              and after some Dangling & (Artifact.tie).Written)
}

/* A DEAD NAME LEAVES ONLY BY A REWRITE OF ITS TEST. No other event clears
   `Dangling`: renaming something else does not fix a text that still spells a
   dead name, which is the frame `rename` holds it to. */
assert DanglingLeavesOnlyByAWrite {
  always all t: Dangling | t not in Dangling' implies (Now.event = Write and Now.artifact = t)
}

/* ---------------- the skip rule ---------------- */

/* Under `landDiscipline`, every stage a landed change has no artifact for
   was licensed, and stays so: a landed change writes nothing more, its
   profile is static, and so is which of its scenarios grew a shape. Without
   it: a change lands with an absence its kind or its criterion refuses. */
assert AbsenceLicensed {
  landDiscipline implies always all c: Landed, s: absentStages[c] | maySkip[c, s]
}
pred AbsenceLicensed_Bites {
  not landDiscipline
  eventually some c: Landed, s: absentStages[c] | not maySkip[c, s]
}

/* THE FINDING. A chain that keeps the worker's reading of the skip rule
   (`skipDiscipline`), the order, and the commit check, and still lands with
   a view it was not licensed to skip: the view was waived while no scenario
   grew a shape, and a later scenario of the same change grew one. The
   criterion is a function of the change's final shape, so the reading that
   decides is the landing's, and `landDiscipline` is a mechanism of its own
   rather than the worker's reading restated. */
pred SkipReadAtTheTimeIsNotEnough {
  orderDiscipline and skipDiscipline and tieDiscipline
  eventually some c: Landed | developmentProfile[c.profile] and Docs in absentStages[c] and not maySkip[c, Docs]
}

/* ---------------- reachability floor ----------------
 * An event no trace can reach silently removes a whole question from the
 * commands above, and an over-tight frame is the cheapest way to cause it
 * without any command turning red.
 */
pred Cov_Write  { eventually Now.event = Write }
pred Cov_Skip   { eventually Now.event = Skip }
pred Cov_Rename { eventually Now.event = Rename }
pred Cov_Land   { eventually Now.event = Land }

/* ---------------- commands ---------------- */

-- the order: holds under the discipline, and has a counterexample without it
check OrderedByFeeds           for 2 Change, 2 Profile, 6 Artifact, 10 steps expect 0
run   OrderedByFeeds_Bites     for 2 Change, 2 Profile, 6 Artifact, 10 steps expect 1

-- the tie: the tree stays tied under the commit check, and comes apart without it
check TreeStaysTied            for 2 Change, 2 Profile, 6 Artifact, 10 steps expect 0
run   TreeStaysTied_Bites      for 2 Change, 2 Profile, 6 Artifact, 10 steps expect 1
check WitnessesResolve         for 2 Change, 2 Profile, 6 Artifact, 10 steps expect 0
run   WitnessesResolve_Bites   for 2 Change, 2 Profile, 6 Artifact, 10 steps expect 1
check DanglingLeavesOnlyByAWrite for 2 Change, 2 Profile, 6 Artifact, 10 steps expect 0

-- the skip rule: every absence is licensed under the landing check, and not without it
check AbsenceLicensed          for 2 Change, 2 Profile, 6 Artifact, 10 steps expect 0
run   AbsenceLicensed_Bites    for 2 Change, 2 Profile, 6 Artifact, 10 steps expect 1

-- the worker's reading alone: licensed at every skip, unlicensed at the landing
run   SkipReadAtTheTimeIsNotEnough for exactly 1 Change, exactly 1 Profile, exactly 6 Artifact, 10 steps expect 1

-- every own event fires in some trace
run Cov_Write   for 2 Change, 2 Profile, 4 Artifact, 8 steps expect 1
run Cov_Skip    for 2 Change, 2 Profile, 4 Artifact, 8 steps expect 1
run Cov_Rename  for 2 Change, 2 Profile, 4 Artifact, 8 steps expect 1
run Cov_Land    for 2 Change, 2 Profile, 4 Artifact, 8 steps expect 1
