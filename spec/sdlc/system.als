/*
 * The stages a change passes through, what each owes the next, the tie by
 * name between a scenario, the test that witnesses it and the code path the
 * test drives, and the rule under which a stage may be skipped.
 *
 * It opens nothing. The moment its checks run is the commit, which
 * github/system does not model, and a tie is between files in one tree, which
 * no entity of spec/campaign holds. Composing `Change` with `Issue` and `Land`
 * with `MergePullRequest` is a layer above this one, and the whole of
 * spec/campaign folds this entity's six stages into its one `Launch` event --
 * which is the gap this entity fills, from beside it and not from inside it.
 *
 *   Stage       the six stages, and `feeds`, the order they owe each other in
 *   Profile     a campaign kind's profile: which stages it lets a change skip
 *   Change      one unit of work -- a sub-issue -- carrying its kind's profile
 *   Artifact    what a stage produced for a change, and what it NAMES
 *   GrowsShape  the spec artifacts that add a shape a person has to understand
 *   Written     the artifacts that exist; Landed, the changes that merged
 *   Now         the observer: which event, on which change, artifact and stage
 *
 * ORIENTATION
 *
 * Three modules, split as spec/campaign splits every entity:
 *
 *   sdlc/system.als     signatures, the tie, the skip rule, events, frame, trace
 *   sdlc/scenarios.als  the disciplines, and every witness `run`
 *   sdlc/checks.als     every `assert` and `check`, and the floor that says
 *                       each event is reachable at all
 *
 * The same reading rules hold: every command carries its own `expect`, the
 * solver is the one reader of a verdict, and the command list is stated a
 * second time in spec/commands.snapshot.json -- one snapshot over the whole
 * of spec/, so a command deleted from either entity is one line gone:
 *
 *   scripts/alloy-check.py spec/sdlc/checks.als -o /tmp/alloy-sdlc
 *   scripts/alloy-check.py --commands spec        -- and --write to update
 *
 * THE THREE MECHANISMS ARE DISCIPLINES, NOT FACTS. `orderDiscipline`,
 * `tieDiscipline` and `landDiscipline` in scenarios.als are each assumed by a
 * check and dropped by its `_Bites`, the shape github/system.als's
 * `closeDiscipline` takes, because a rule written into an event is true in
 * every world the model admits and no command can exhibit its absence. The
 * events below are therefore LOOSE: `write` does not read the order, `skip`
 * does not read the criterion, `land` does not read the tie.
 */
module sdlc/system

/* THE SIX STAGES. Two names are what a stage is called and what its artifact
   is at this base: intent and plan are the sub-issue's `## Intent` and
   `## Plan`; spec is a scenario or check in spec/; docs is an HTML view under
   docs/; test is a case in a scripts/*-test.* suite; code is a path in
   scripts/ or .claude/ that a test drives. A member repository maps the last
   four onto its own tree, and the profile line of its campaign's kind says
   which of them it has at all. */
abstract sig Stage {}
one sig Intent, Plan, Spec, Docs, Test, Code extends Stage {}

/* WHAT EACH STAGE OWES THE NEXT: its artifact, or a licensed skip, before the
   next stage's artifact is written. Docs and Test both follow Spec and both
   precede Code -- "spec, docs or test, code" -- so a change with a view and a
   test writes them in either order and its code after both. The relation is
   read by `orderDiscipline` and by nothing structural: a `write` out of order
   is what `OrderedByFeeds_Bites` shows. */
fun feeds: Stage -> Stage {
  Intent->Plan + Plan->Spec + Spec->Docs + Spec->Test + Docs->Code + Test->Code
}

/* THE STAGES A CHANGE MAY EVER SKIP. Intent and Plan are not among them: a
   change with no intent cannot be judged for anything below it, and
   `campaign-claim take` already refuses a sub-issue without `## Plan`. */
fun skippable: set Stage { Spec + Docs + Test + Code }

/* A CAMPAIGN KIND'S PROFILE: which of the skippable stages the kind lets a
   change skip at all. One input to `maySkip`, the criterion being the other;
   neither alone licenses a skip. A kind is a file under
   .claude/skills/opening-campaign/assets/agents/; the profile line each will
   carry is the procedure's to write (#247), in this vocabulary, and the two
   witnesses in scenarios.als (`developmentProfile`, `researchProfile`) are
   what it derives them from. No kind is an atom here: the model owns how a
   profile and a change combine, and the kinds own their profiles, so adding a
   kind changes no model. */
sig Profile { optional: set Stage }

sig Change {
  profile:     one Profile,
  /* THE STAGES THIS CHANGE SKIPPED, by a Skip event. A stage neither written
     nor skipped is not done, and `land` waits on it. */
  var skipped: set Stage
}

/* WHAT A STAGE PRODUCED FOR A CHANGE, and what it names. An artifact a change
   REUSES -- a test witnessing a scenario that already existed -- is an
   artifact of that change here as much as one it wrote: the check reads a
   name against the tree, not against the diff, and the model does not say
   which commit first wrote a file.

   `names` IS THE TIE'S RAW MATERIAL: `a -> b` says a's text carries b's
   current name, and it is var for one reason, that a rename of b makes every
   text still carrying the old name stop naming b. Authored at `write`, broken
   at `rename`, and never a fact about b being written -- a test names the
   code path it will drive before that path exists, which is the order
   `feeds` asks for. */
sig Artifact {
  change:    one Change,
  stage:     one Stage,
  var names: set Artifact
}
/* THE SPEC ARTIFACTS THAT GROW A SHAPE: a signature, a relation or an event
   a person has to understand. Static, because a scenario either declares one
   or does not, and readable off a diff -- a `sig`, a `var` or a `one sig ...
   extends Event` added under spec/ -- which is what makes the docs criterion
   the check's to decide rather than a worker's. */
sig GrowsShape in Artifact {}

var sig Written in Artifact {}
var sig Landed  in Change {}

fact SdlcWellFormed {
  all p: Profile | p.optional in skippable
  GrowsShape in stage.Spec
}

fun writtenOf[c: Change]:     set Artifact { change.c & Written }
fun writtenStages[c: Change]: set Stage    { writtenOf[c].stage }
fun absentStages[c: Change]:  set Stage    { Stage - writtenStages[c] }
pred done[c: Change, s: Stage]             { s in writtenStages[c] or s in c.skipped }

/* THE TIE. A scenario names the test that witnesses it, and the test names
   the code path it drives: `s -> t -> k` where the two names hold and the
   scenario and the test exist. Read from the CODE PATH UP -- `tied[k]` asks
   whether some scenario reaches k -- and not from the scenario down, because
   a scenario with no test is a claim the solver checks on its own, and
   reading it the other way would refuse every scenario spec/campaign holds
   today. Whether the check reads the tree or only the diff is the check's;
   the model says what a tie is and when one is read. */
fun tie: Artifact -> Artifact -> Artifact {
  { s: Written & stage.Spec, t: Written & stage.Test, k: stage.Code | s->t in names and t->k in names }
}
pred tied[k: Artifact] { some tie.k }
/* EVERY CODE PATH IN THE TREE WALKS BACK TO A SCENARIO. The invariant
   `tieDiscipline` keeps and `TreeStaysTied_Bites` breaks. */
pred treeTied { all k: Written & stage.Code | tied[k] }

/* THE SKIP RULE. A stage may be skipped when the kind's profile lets it be
   AND the stage's own criterion holds of the change -- one criterion per
   skippable stage, each a fact about the change's artifacts and none a
   judgement:

     Spec   nothing below it exists: the change has written no view, no
            test and no code path, so there is nothing to formalise and
            nothing drawn for a model that is not there.
     Docs   the model grew no shape: no spec artifact of the change is in
            GrowsShape, so there is nothing a person has to be shown.
     Test   nothing runs -- the same reading as Spec's.
     Code   nothing runs. Test and Code share a criterion on purpose: a test
            with no code path witnesses nothing, and a code path with no test
            is unchecked, so a change has both or neither.

   The criteria read `writtenOf[c]`, WHICH CHANGES AS THE CHANGE IS WRITTEN,
   and that is the whole of `SkipReadAtTheTimeIsNotEnough` in checks.als: a
   skip licensed when the worker reached the stage is stale by landing if a
   later artifact of the same change turned its criterion false. The moment
   that decides is `land`, under `landDiscipline`. */
pred criterion[c: Change, s: Stage] {
  s = Spec          implies no writtenOf[c] & stage.(Docs + Test + Code)
  s = Docs          implies no writtenOf[c] & GrowsShape
  s in Test + Code  implies no writtenOf[c] & stage.(Test + Code)
}
pred maySkip[c: Change, s: Stage] { s in c.profile.optional and criterion[c, s] }

/* ---------------- observable events ---------------- */

abstract sig Event {}
one sig Stutter, Write, Skip, Rename, Land extends Event {}

one sig Now {
  var event:    one Event,
  var subject:  lone Change,
  var artifact: lone Artifact,
  var at:       lone Stage
}

pred sdlcFrame { Written' = Written and Landed' = Landed and skipped' = skipped and names' = names }

/* ONE COMMIT WRITING ONE ARTIFACT. Loose on the order (`orderDiscipline`) and
   on the tie (`tieDiscipline`). A second write of the same artifact is a
   rewrite, which is how a test takes a renamed code path's new name. What
   the artifact names is authored here and nowhere else; everything else's
   names hold.

   WRITING A SKIPPED STAGE RETRACTS THE SKIP: a stage is written or skipped,
   never both, and the write is the later word. This is the remedy the
   landing check leaves a worker whose waiver went stale
   (`SkipReadAtTheTimeIsNotEnough`): write the view after all, and land,
   which is `S3b_DocsWrittenAfterAll`. */
pred write[a: Artifact] {
  a.change not in Landed
  Written' = Written + a
  skipped' = skipped - a.change->a.stage
  names' - a->Artifact = names - a->Artifact
  Landed' = Landed
  Now.event = Write and Now.subject = a.change and Now.artifact = a and Now.at = a.stage
}

/* A STAGE WAIVED. Loose on the criterion: `skipDiscipline` is the worker
   reading `maySkip` when it reaches the stage, and `landDiscipline` is the
   check reading it again when the change lands. */
pred skip[c: Change, s: Stage] {
  c not in Landed
  s not in c.skipped and s not in writtenStages[c]
  skipped' = skipped + c->s
  Written' = Written and Landed' = Landed and names' = names
  Now.event = Skip and Now.subject = c and no Now.artifact and Now.at = s
}

/* A COMMIT THAT RENAMES AN ARTIFACT. Every text carrying its old name stops
   naming it, except those the same commit rewrote, which the model leaves to
   the solver: `names'` may keep any of a's inbound pairs and drops the rest.
   It is the one event that removes a tie, and the one a check must refuse
   when what it drops was load-bearing (`S4_RenameBreaksTheTie`). */
pred rename[a: Artifact] {
  a in Written
  names' in names
  names' - Artifact->a = names - Artifact->a
  Written' = Written and Landed' = Landed and skipped' = skipped
  Now.event = Rename and Now.subject = a.change and Now.artifact = a and Now.at = a.stage
}

/* THE CHANGE MERGES. Structurally it waits on every stage being done --
   written or skipped -- because a change with a stage that is neither is not
   finished, and that is a definition, not a mechanism. Whether each absence
   was LICENSED is `landDiscipline`'s, and whether what was written TIES is
   `tieDiscipline`'s. After landing a change writes and skips nothing more,
   but what it wrote can still be renamed: a rename is a later commit on the
   tree, and the check that reads it is the commit's, not the landing's
   (`S4_RenameBreaksTheTie` renames a landed chain's code path). */
pred land[c: Change] {
  c not in Landed
  all s: Stage | done[c, s]
  Landed' = Landed + c
  Written' = Written and skipped' = skipped and names' = names
  Now.event = Land and Now.subject = c and no Now.artifact and no Now.at
}

pred stutter {
  sdlcFrame
  Now.event = Stutter and no Now.subject and no Now.artifact and no Now.at
}

pred sdlcInit {
  no Written and no Landed and no skipped and no names
}

pred sdlcStep {
  stutter
  or (some a: Artifact | write[a] or rename[a])
  or (some c: Change, s: Stage | skip[c, s])
  or (some c: Change | land[c])
}

fact SdlcTrace { sdlcInit and always sdlcStep }
