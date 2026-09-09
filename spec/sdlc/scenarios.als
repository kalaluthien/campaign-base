/*
 * The disciplines over sdlc/system, and the witnesses: a full chain, a chain
 * that skips by the rule, a docs waiver and its remedy, and the tie broken by
 * a rename at each of its three ends.
 * sdlc/system.als is this entity's entry point.
 */
module sdlc/scenarios

open sdlc/system

/* ---------------- profiles ---------------- */

/* THE TWO KINDS THE WITNESSES RUN UNDER. `development` is this campaign's own
   kind: the model before the code, a test that failed first, and a view only
   when the model grew a shape -- so Docs is the one stage it lets a change
   skip. `research` refuses changing a repository beyond a scratch probe, so
   its changes are findings on an issue and every stage past Plan is
   skippable. The other kinds' profiles are the procedure's to state, one
   line each in assets/agents/*.md, in this vocabulary. */
pred developmentProfile[p: Profile] { p.optional = Docs }
pred researchProfile[p: Profile]    { p.optional = skippable }

/* ---------------- disciplines ---------------- */

/* A STAGE IS WRITTEN OR SKIPPED ONLY AFTER WHAT FEEDS IT IS DONE. The
   procedure's own order; `S5_CodeBeforeSpecRefused` is its sharpest case,
   with `skipDiscipline` closing the skip. */
pred orderDiscipline {
  always ((Now.event in Write + Skip) implies all p: feeds.(Now.at) | done[Now.subject, p])
}

/* THE WORKER READS THE SKIP RULE WHEN IT REACHES A STAGE. The early reading,
   and not the one that decides: `SkipReadAtTheTimeIsNotEnough` in checks.als
   is a chain that keeps it and still lands with an unlicensed absence. */
pred skipDiscipline {
  always (Now.event = Skip implies maySkip[Now.subject, Now.at])
}

/* THE CHECK AT THE COMMIT: the tree a commit leaves is tied. Read on the
   tree AFTER the commit, so a rename that rewrites its namers in the same
   commit passes and one that leaves a name dangling is refused. This is the
   pre-commit check the campaign's Scope names. */
pred tieDiscipline {
  always ((Now.event in Write + Rename) implies after treeTied)
}

/* THE CHECK AT THE LANDING: every stage the change has no artifact for is
   one the profile and the criterion license, read against the change as it
   is when it lands. A landing is a merge, so this reading belongs where the
   merge is gated -- the pull request's `check` -- and not to the commit,
   where a test written before its code path would read as an unlicensed
   absence of Code. */
pred landDiscipline {
  always (Now.event = Land implies all s: absentStages[Now.subject] | maySkip[Now.subject, s])
}

pred allDisciplines { orderDiscipline and skipDiscipline and tieDiscipline and landDiscipline }

/* ---------------- witnesses ---------------- */

/* One artifact per stage, written in the order `feeds` asks for, and the
   change lands with its code path walking back to its scenario. */
pred S1_FullChain {
  allDisciplines
  one c: Change {
    developmentProfile[c.profile]
    all s: Stage | one change.c & stage.s
    eventually (c in Landed and no c.skipped and all k: change.c & stage.Code | tied[k])
  }
}

/* A research change: intent and plan written, everything below skipped by
   the rule, and it lands. */
pred S2_SkippedChain {
  allDisciplines
  one c: Change {
    researchProfile[c.profile]
    change.c.stage = Intent + Plan
    eventually (c in Landed and c.skipped = skippable)
  }
}

/* A development change whose scenario grows no shape waives its view and
   lands with the rest of the chain written. */
pred S3_DocsWaived {
  allDisciplines
  no GrowsShape
  one c: Change {
    developmentProfile[c.profile]
    change.c.stage = Stage - Docs
    eventually (c in Landed and c.skipped = Docs)
  }
}

/* The same waiver when the scenario DID grow a shape: no trace lands it. */
pred S3a_DocsDemanded {
  allDisciplines
  one c: Change {
    developmentProfile[c.profile]
    eventually (c in Landed and Docs in c.skipped and some writtenOf[c] & GrowsShape)
  }
}

/* The remedy the landing check leaves: the same waiver, then a scenario that
   grows a shape, and the change writes the view it had waived -- the write
   retracts the skip, and this is the one command that reads the retraction --
   and lands. The finding in checks.als is this chain
   without the view; `write`'s comment in system.als names it. */
pred S3b_DocsWrittenAfterAll {
  allDisciplines
  one c: Change {
    developmentProfile[c.profile]
    eventually (Now.event = Write and Now.at = Docs and Docs in c.skipped
                and some writtenOf[c] & GrowsShape
                and after Docs not in c.skipped)
    eventually c in Landed
  }
}

/* A landed full chain, then its code path is renamed and no namer is
   rewritten: the tree is untied. Every discipline but the commit check holds,
   which is the point -- nothing else reads a tie. */
pred S4_RenameBreaksTheTie {
  orderDiscipline and skipDiscipline and landDiscipline
  one c: Change {
    developmentProfile[c.profile]
    all s: Stage | one change.c & stage.s
    eventually (c in Landed and no c.skipped and treeTied
                and eventually (Now.event = Rename and Now.at = Code and treeTied and after not treeTied))
  }
}

/* The same break read at the scenario's end: the landed chain's SCENARIO is
   renamed and the test still carries the old name, so the code path is
   untied. This is the one command that pins which text carries which name
   -- with the scenario naming the test (`s -> t`) a rename of the scenario
   drops no pair and this is UNSAT -- and it is the T3 the check refuses. */
pred S4b_RenameOfTheScenarioBreaksTheTie {
  orderDiscipline and skipDiscipline and landDiscipline
  one c: Change {
    developmentProfile[c.profile]
    all s: Stage | one change.c & stage.s
    eventually (c in Landed and no c.skipped and treeTied
                and eventually (Now.event = Rename and Now.at = Spec and treeTied and after not treeTied))
  }
}

/* The rename the check admits: the commit that renames the code path also
   renames the test paired with it, and the tree stays tied through it. */
pred S4a_RenameKeepsItsNamers {
  allDisciplines
  one c: Change {
    developmentProfile[c.profile]
    all s: Stage | one change.c & stage.s
    eventually (Now.event = Rename and Now.at = Code and some drives.(Now.artifact))
    always treeTied
  }
}

/* THE THIRD END: the landed chain's TEST is renamed, and the code path it
   drove is untied -- `drives` pairs two names, so moving either file breaks
   it. This is the guard's T2 read from the suite's side, the case a merged
   `names` relation broken only at its target left SAT here and refused there;
   the split is what closes that gap.

   `S4d` is the half the same rename does NOT break, and it is UNSAT: a test's
   `witnesses` arrow is a declaration in its own text, which survives the file
   being moved. The pair pins the asymmetry -- collapse `drives` back into a
   target-broken relation and `S4c` goes UNSAT; break `witnesses` at its source
   as well and `S4d` goes SAT. */
pred S4c_RenameOfTheTestBreaksTheTie {
  orderDiscipline and skipDiscipline and landDiscipline
  one c: Change {
    developmentProfile[c.profile]
    all s: Stage | one change.c & stage.s
    eventually (c in Landed and no c.skipped and treeTied
                and eventually (Now.event = Rename and Now.at = Test and treeTied and after not treeTied))
  }
}
pred S4d_RenameOfTheTestKeepsItsWitness {
  orderDiscipline and skipDiscipline and landDiscipline
  one t: Artifact | eventually (Now.event = Rename and Now.artifact = t and t.stage = Test
                                and some t.witnesses and after no t.witnesses)
}

/* Code before its scenario: no trace writes a development change's code
   path while the change has no scenario. The order and the worker's reading
   of the skip rule refuse it between them -- Code waits on Spec being done,
   and the development kind does not let Spec be skipped -- and the commit
   check is not what refuses it: the tie reads the tree, so a scenario and a
   test of ANOTHER change can tie the path, which is why the scope holds two
   changes and the subject's kind is pinned. `S5a` is the same chain under
   the order and the worker's reading alone, and it is refused all the same. */
pred codeBeforeSpec {
  eventually (Now.event = Write and Now.at = Code
              and developmentProfile[Now.subject.profile]
              and no writtenOf[Now.subject] & stage.Spec)
}
pred S5_CodeBeforeSpecRefused  { allDisciplines and codeBeforeSpec }
pred S5a_RefusedWithoutTheTie  { orderDiscipline and skipDiscipline and codeBeforeSpec }

/* ---------------- commands ---------------- */

run S1_FullChain              for exactly 1 Change, exactly 1 Profile, exactly 6 Artifact, 10 steps expect 1
run S2_SkippedChain           for exactly 1 Change, exactly 1 Profile, exactly 2 Artifact, 10 steps expect 1
run S3_DocsWaived             for exactly 1 Change, exactly 1 Profile, exactly 5 Artifact, 10 steps expect 1
run S3a_DocsDemanded          for exactly 1 Change, exactly 1 Profile, 6 Artifact, 10 steps expect 0
run S3b_DocsWrittenAfterAll   for exactly 1 Change, exactly 1 Profile, 7 Artifact, 12 steps expect 1
run S4_RenameBreaksTheTie     for exactly 1 Change, exactly 1 Profile, exactly 6 Artifact, 10 steps expect 1
run S4b_RenameOfTheScenarioBreaksTheTie for exactly 1 Change, exactly 1 Profile, exactly 6 Artifact, 10 steps expect 1
run S4a_RenameKeepsItsNamers  for exactly 1 Change, exactly 1 Profile, exactly 6 Artifact, 10 steps expect 1
run S4c_RenameOfTheTestBreaksTheTie     for exactly 1 Change, exactly 1 Profile, exactly 6 Artifact, 10 steps expect 1
run S4d_RenameOfTheTestKeepsItsWitness  for exactly 1 Change, exactly 1 Profile, exactly 6 Artifact, 10 steps expect 0
run S5_CodeBeforeSpecRefused  for 2 Change, 2 Profile, 6 Artifact, 10 steps expect 0
run S5a_RefusedWithoutTheTie  for 2 Change, 2 Profile, 6 Artifact, 10 steps expect 0
