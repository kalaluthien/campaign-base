/*
 * The stages a change passes through, what each owes the next, the tie
 * between a scenario, the test that witnesses it and the code path the test
 * drives, and the rule under which a stage may be skipped.
 *
 * It opens nothing. The moment its checks run is the commit, which
 * github/system does not model, and a tie is between files in one tree, which
 * no entity of spec/campaign holds. Composing `Change` with `Issue` and `Land`
 * with `MergePullRequest` is a layer above this one, and the whole of
 * spec/campaign folds this entity's five stages into its one `Launch` event --
 * which is the gap this entity fills, from beside it and not from inside it.
 *
 *   Stage       the five stages, and `feeds`, the order they owe each other in
 *   Change      one unit of work -- a sub-issue -- and the stages its
 *               sub-issue's kind lets it skip
 *   Artifact    one text under one name: what a stage produced for a change,
 *               what it WITNESSES and what it DRIVES
 *   Written     the artifacts that exist; Landed, the changes that merged;
 *               Licensed, the code paths the tie guard's allow-list exempts
 *   Step        the observer: which event, on which artifact or change
 *
 * ORIENTATION
 *
 * Two modules:
 *
 *   sdlc/system.als     signatures, the tie, the skip rule, events, frame, trace
 *   sdlc/checks.als     the disciplines, every witness `run`, every `assert`
 *                       and `check`, and the floor that says each event is
 *                       reachable at all
 *
 * The reading rules are spec/campaign's: every command carries its own
 * `expect`, the solver is the one reader of a verdict, and the command list is
 * stated a second time in spec/commands.snapshot.json -- one snapshot over the
 * whole of spec/, so a command deleted from either entity is one line gone:
 *
 *   scripts/alloy-check.py spec/sdlc/checks.als -o /tmp/alloy-sdlc
 *   scripts/alloy-check.py --commands spec        -- and --write to update
 *
 * THE THREE MECHANISMS ARE DISCIPLINES, NOT FACTS. `orderDiscipline`,
 * `tieDiscipline` and `landDiscipline` in checks.als are each assumed by a
 * check and dropped by its `_Bites`, the shape github/system.als's
 * `closeDiscipline` takes, because a rule written into an event is true in
 * every world the model admits and no command can exhibit its absence. The
 * events below are therefore LOOSE: `write` does not read the order, the tie
 * or the allow-list, `land` does not read the skip rule.
 */
module sdlc/system

/* THE FIVE STAGES. Two names are what a stage is called and what its artifact
   is at this base: intent and plan are the sub-issue's `## Intent` and
   `## Plan`; spec is a `run` or `check` command under spec/, by the name
   spec/commands.snapshot.json records; test is a case in a scripts/*-test.*
   suite; code is a path in scripts/ or .claude/ that a test drives. A member
   repository maps the last three onto its own tree, and the profile line of
   its sub-issue's kind says which of them it has at all.

   A view drawn for a reader, docs/<model>.html, is no stage: check-tree-shape
   shapes one and nothing requires one, and this base keeps none. */
abstract sig Stage {}
one sig Intent, Plan, Spec, Test, Code extends Stage {}

/* WHAT EACH STAGE OWES THE NEXT: its artifact, or an absence the skip rule
   licenses, before the next stage's artifact is written. The relation is read
   by `orderDiscipline` and by nothing structural: a `write` out of order is
   what `OrderedByFeeds_Bites` shows. */
fun feeds: Stage -> Stage { Intent->Plan + Plan->Spec + Spec->Test + Test->Code }

/* THE STAGES A CHANGE MAY EVER SKIP. Intent and Plan are not among them: a
   change with no intent cannot be judged for anything below it, and
   `campaign-claim take` already refuses a sub-issue without `## Plan`. */
fun skippable: set Stage { Spec + Test + Code }

/* A CHANGE CARRIES ITS KIND'S PROFILE: `optional`, the skippable stages the
   sub-issue's kind lets it skip at all. One input to `maySkip`, the criterion
   being the other; neither alone licenses a skip. A kind is a `kind:<k>` label
   on the sub-issue (rule-check#314), and its reference under
   .claude/skills/assuming-role/references/, kind-<k>.md, states this set in
   one line; `development` has no reference, and its line is the default in the
   campaign's AGENTS.md. The two profiles in checks.als (`developmentProfile`,
   `narrowingProfile`) are what those lines derive from -- the second a
   profile no kind states since rule-check#354, kept as the only one that
   narrows anything, and so the only one that witnesses this half of
   `maySkip`. No kind is an atom here: the model owns how a
   profile and a change combine, and the kinds own their profiles, so adding
   a kind changes no model.

   A SKIPPED STAGE IS AN ABSENT ARTIFACT. Nothing records a waiver: the
   stages a change has no artifact for are its skips, and whether each is
   licensed is read off the change as it stands -- by the order at each write,
   and by the landing check at the merge. */
sig Change { optional: set Stage }

/* ONE TEXT UNDER ONE NAME: what a stage produced for a change, what it
   witnesses and what it drives. An artifact a change REUSES -- a test
   witnessing a scenario that already existed -- is an artifact of that change
   here as much as one it wrote: the check reads the tree, not the diff, and
   the model does not say which commit first wrote a file.

   THE TIE'S RAW MATERIAL IS TWO RELATIONS, NOT ONE, because the two halves
   break at different ends. `witnesses` is a DECLARATION carried in the test's
   own text -- `t -> s` says t's text declares s by s's name -- and `drives` is
   a PAIRING OF TWO NAMES, `t -> k` holding where the test's name and the code
   path's name answer to each other. Both are static, because an atom is one
   text under one name: a commit that renames puts a new atom in the old
   one's place (`rename`), and the arrows into the old atom stay on it,
   outside Written. So renaming a scenario leaves every text declaring it
   pointing at nothing unless the same commit replaces those texts, while
   renaming a test carries its text along -- `rename` copies `witnesses` and
   leaves `drives` to the new name -- which is the asymmetry
   `S4c_TestRenameBreak` and `S4d` pin.

   Neither arrow is a fact about its target being written: a test declares
   the code path it will drive before that path exists, which is the order
   `feeds` asks for. */
sig Artifact {
  change:    one Change,
  stage:     one Stage,
  witnesses: set Artifact,
  drives:    set Artifact
}

var sig Written in Artifact {}
var sig Landed  in Change {}

/* THE CODE PATHS THE ALLOW-LIST EXEMPTS from the tie: `LEGACY` in
   scripts/check-sdlc-tie.py, the paths the tree held untied when the guard
   was written. A var, so that a list which GROWS is a trace the model can
   show (`DebtNeverGrows_Bites`); `licenceNeverGrows` in checks.als is what
   keeps it from growing, and a commit may move it where no discipline is
   assumed.

   The trace starts from an empty tree, so the list as it stands at the start
   is the model's stand-in for the debt the tree held before the guard: a
   name on it that the trace writes later is such a path. The guard is
   stricter at two points and looser at one. It refuses a path a commit adds
   whether or not the list names it, and a tied path a commit unties, before
   it reads the list at all; and it licenses a renamed path by EITHER name,
   where here the new name must already be on the list. */
var sig Licensed in Artifact {}

fact SdlcWellFormed {
  all c: Change | c.optional in skippable
  /* WHICH STAGE MAY CARRY WHICH ARROW. A test is the one artifact that
     declares a scenario, and the one that pairs with a code path; nothing else
     carries either arrow, which is what makes `tie` a fact about tests. */
  witnesses in stage.Test -> stage.Spec
  drives    in stage.Test -> stage.Code
}

fun writtenOf[c: Change]:     set Artifact { change.c & Written }
fun writtenStages[c: Change]: set Stage    { writtenOf[c].stage }
fun absentStages[c: Change]:  set Stage    { Stage - writtenStages[c] }

/* THE TIE. A test declares the scenario it witnesses and pairs with the code
   path it drives -- `t -> s` in `witnesses` and `t -> k` in `drives`, the
   first read off the test's own text and the second off the two names, which
   is how scripts/check-sdlc-tie.py reads them -- so `s -> t -> k` holds where
   both arrows hold and all three are written. Read from the CODE PATH UP --
   `tied[k]` asks whether some scenario reaches k -- and not from the scenario
   down, because a scenario with no test is a claim the solver checks on its
   own, and reading it the other way would refuse every scenario spec/campaign
   holds today. Whether the check reads the tree or only the diff is the
   check's; the model says what a tie is and when one is read. */
fun tie: Artifact -> Artifact -> Artifact {
  { s: Written & stage.Spec, t: Written & stage.Test, k: Written & stage.Code |
      t->s in witnesses and t->k in drives }
}
pred tied[k: Artifact] { some tie.k }
/* EVERY CODE PATH IN THE TREE THE LIST DOES NOT EXEMPT WALKS BACK TO A
   SCENARIO. The invariant `tieDiscipline` keeps and `TreeStaysTied_Bites`
   breaks. */
pred everyCodeHasScenario { all k: Written & stage.Code - Licensed | tied[k] }
/* EVERY DECLARED WITNESS NAMES A WRITTEN SCENARIO: no test in the tree
   declares an atom a rename took out of it. Not implied by
   `everyCodeHasScenario`, which asks for SOME scenario per code path: a
   suite declaring two, one of them renamed away, stays tied through the
   other and still names nothing with the first. `WitnessesResolve_Bites` in
   checks.als is that trace. */
pred everyWitnessExists { all t: Written | t.witnesses in Written }

/* THE SKIP RULE. A stage may be skipped when the kind's profile lets it be
   AND the criterion holds of the change: it has written no test and no code
   path -- nothing runs. One criterion serves all three skippable stages, a
   fact about the change's artifacts and not a judgement: Spec because
   nothing below it exists to formalise, and Test and Code together because
   a test with no code path witnesses nothing and a code path with no test is
   unchecked, so a change has both or neither.

   The criterion reads `writtenOf[c]`, WHICH GROWS AS THE CHANGE IS WRITTEN:
   an absence licensed at one write is stale by landing if a later artifact
   of the same change turned the criterion false -- a scenario skipped at the
   change's first test, and a code path written after it, which is
   `S5b_WithoutTheLandingCheck`. The moment that decides is `land`, under
   `landDiscipline`. */
pred criterion[c: Change] { no writtenOf[c] & stage.(Test + Code) }
pred maySkip[c: Change, s: Stage] { s in c.optional and criterion[c] }

/* ---------------- observable events ---------------- */

abstract sig Event {}
one sig Stutter, Write, Rename, Land extends Event {}

/* The artifact a write or a rename is about, and the change a landing is
   about; the stage is the artifact's. */
one sig Step {
  var event:    one Event,
  var artifact: lone Artifact,
  var subject:  lone Change
}

/* A commit is the one step that may move the allow-list, so every other step
   holds it where it was. */
pred sdlcFrame { Written' = Written and Landed' = Landed and Licensed' = Licensed }

/* ONE COMMIT WRITING ONE NEW TEXT. Loose on the order (`orderDiscipline`),
   on the tie and on the allow-list (`tieDiscipline`). What the artifact
   witnesses and drives came with its text. */
pred write[a: Artifact] {
  a.change not in Landed
  a not in Written
  Written' = Written + a and Landed' = Landed
  Step.event = Write and Step.artifact = a and no Step.subject
}

/* A COMMIT THAT RENAMES AN ARTIFACT. The text moves: `b` declares what `a`
   declared. The name does not: what `b` drives, and what drives `b`, is
   whatever answers to the new name. So a test's `witnesses` survive its
   rename, a scenario's inbound `witnesses` do not survive its own, and
   `drives` may break at either end.

   It can remove a tie by moving a name alone, and a check must refuse that
   when what it drops was load-bearing. The rename's breaks:
   `S4_CodeRenameBreak` at the code path's end, `S4b` at the scenario's, `S4c`
   at the test's. After landing a change writes nothing more, but what it
   wrote can still be renamed: a rename is a later commit on the tree, and the
   check that reads it is the commit's, not the landing's.

   The same commit may replace the tests that declare `a`: any of them may
   leave the tree and fresh tests may enter it, so a scenario and the texts
   naming it move together (`S4e`). A test that enters is a new text, so it
   may tie otherwise than the one it replaced, and the commit check reads it
   as it reads a write. Nothing else moves, and the tests that enter belong to
   the changes whose tests left, so a rename adds no stage to a change, takes
   none away, and turns no criterion: what `AbsenceLicensed` and
   `OrderedByFeeds` rest on, since neither discipline reads a rename. */
pred rename[a, b: Artifact] {
  a in Written and b not in Written
  b.change = a.change and b.stage = a.stage
  Landed' = Landed
  a not in Written' and b in Written'
  Written - Written' - a in witnesses.a & stage.Test
  Written' - Written - b in stage.Test
  (Written - Written' - a).change = (Written' - Written - b).change
  b.witnesses = a.witnesses
  Step.event = Rename and Step.artifact = a and no Step.subject
}

/* THE CHANGE MERGES. Structurally it waits on nothing: whether each absent
   stage was LICENSED is `landDiscipline`'s, and whether what was written TIES
   is `tieDiscipline`'s. */
pred land[c: Change] {
  c not in Landed
  Landed' = Landed + c and Written' = Written and Licensed' = Licensed
  Step.event = Land and no Step.artifact and Step.subject = c
}

pred stutter {
  sdlcFrame
  Step.event = Stutter and no Step.artifact and no Step.subject
}

pred sdlcInit { no Written and no Landed }

pred sdlcStep {
  stutter
  or (some a: Artifact | write[a])
  or (some a, b: Artifact | rename[a, b])
  or (some c: Change | land[c])
}

fact SdlcTrace { sdlcInit and always sdlcStep }
