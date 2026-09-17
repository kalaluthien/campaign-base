/*
 * Everything GitHub records about a campaign -- and the entry point to spec/.
 * It opens nothing: this is the bottom entity.
 *
 *   Repo         a repository, with Base the one this model runs in.
 *   PullRequest  a pull request, and Merged the ones that landed.
 *   Issue        an issue: which repository its work lands in -- where its
 *                branch is cut and its pull request opened -- and which pull
 *                request it has. Open holds the ones still open. Every issue
 *                is FILED on the Base's tracker, whatever its `repo`; a
 *                member repository receives only branches and pull requests,
 *                so the tracker is a constant here and not a field.
 *   Campaign     a campaign: its campaign issue, the sub-issues that truly
 *                belong to it, the sub-issue index GitHub itself keeps, and the
 *                repository list in the campaign issue body. Filed holds the
 *                campaigns whose campaign issue exists.
 *   Claimed      the sub-issues whose branch is on the remote. A branch is a
 *                ref, readable from any machine, so the claim is a GitHub fact
 *                and not a local one -- which is why it lives here.
 *   Event        the events, one atom per event across all four entities.
 *   Now          the observer: which event is happening and to which issue.
 *
 * ORIENTATION
 *
 * Four entities, each opening the one below in the chain that
 * scripts/check-tree-shape.py's R9 reads and prints, so the composed model is
 * the top one and there is no fifth integration module:
 *
 *   github/          issues, pull requests, the sub-issue index, the campaign
 *                    issue body, and the claim
 *   directory/       one campaign's directory on a machine, its checkouts, and
 *                    how far behind origin each base checkout is
 *   session/         a campaign session: one role, bound to one machine
 *   orchestration/   agents, and how a campaign session coordinates them
 *
 * Each entity is two modules:
 *
 *   <entity>/system.als     signatures, observers, events, frame, trace
 *   <entity>/checks.als     every command: the witnesses, the checks, and the
 *                           floor that says each event is reachable at all
 *
 * `checks` opens its own `system`. A command declared in an OPENED module is
 * not executed, so running a system module runs nothing and `checks` is where
 * every command lives.
 *
 * WHAT CHECKS WHAT
 *
 * Every command states its own verdict, in the `expect` clause the solver
 * enforces: `expect 0` where the solver says UNSAT -- a check with no
 * counterexample, a run with no instance -- and `expect 1` where it says SAT.
 * Alloy exits non-zero and names each command that came out other than its
 * clause says. No comment restates a verdict; one that did would be a second
 * reader of what the solver already decided.
 *
 * A command someone DELETES misses no expectation, having none left to miss,
 * and nothing generated from these files can see that either. So the command
 * list is stated a second time, in commands.snapshot.json at the spec/ root,
 * one snapshot over every entity there, which is committed and compared
 * rather than regenerated:
 *
 *   scripts/alloy-check.py spec/campaign/github/checks.als -o /tmp/alloy-github
 *   scripts/alloy-check.py --commands spec               -- and --write to update
 *   scripts/alloy-check.py --digest spec/campaign/github/checks.als \
 *       /tmp/alloy-github/S1_HappyPath-solution-0.txt
 *
 * HOW THE ENTITIES COMPOSE
 *
 * Facts conjoin on `open`, so each entity's `step` is written as
 *
 *   stutter, or one of this entity's own events, or
 *   (the event is none of this entity's and this entity's state is framed)
 *
 * and a lower entity therefore frames its own state automatically whenever an
 * upper entity's event fires. No upper entity writes a frame for a lower
 * entity's variables.
 *
 * An event that crosses entities is ONE `Event` atom, declared in the lowest
 * entity that knows the fact, with a disjunct in each entity above that adds to
 * it: the lower entity owns the fact and the primitive, the upper entity owns
 * the session and the guard. The primitive stays loose so the refinement above it
 * is satisfiable together with it. Observer fields follow the same rule -- `Now`
 * here, `Where` in directory, `Who` in session, `Target` in orchestration -- so
 * no entity declares a field over a signature it does not own.
 */
module github/system

sig Repo {}
one sig Base extends Repo {}

sig PullRequest {}

sig Issue {
  repo:   one Repo,                  -- where the work lands, never where the issue is filed
  var pullRequest: lone PullRequest
}

/* A campaign has TWO names, and they answer different questions. The campaign
   issue's NUMBER is the identity: it is what `gh` is given, what `--parent`
   links, and what `bound` and `settlement` are asked about. The SLUG is what a
   person reads: every session name, claim branch and directory is built from
   it, and none of them carries the number.

   The slug is not modelled as a value, for the same reason the session name is
   not: `.claude/skills/assuming-role/scripts/campaign-name-session.py`
   owns its shape, and a second
   statement here would admit words that script refuses. What IS normative is
   where it lives and that it is one -- a single `campaign:<slug>` label on the
   campaign issue, so a slug cannot be minted twice (GitHub keeps label names
   unique per repository) and a campaign wearing two of them is a question no
   reader may answer. `campaign-tracker.py`'s `slug`, `issue` and `slugs` are
   the readers; `campaign-issues` refuses an open campaign that has none.

   A SUB-ISSUE'S KIND is a label of the same shape, `kind:<k>`:
   one per sub-issue, read by exact name by `campaign-tracker.py kind <N>`,
   and two of them a question no reader may answer; what `check` does with
   none and with two is AGENTS.md § Sub-issues' to state. It is a
   property of the sub-issue and not the campaign, since one campaign mixes
   kinds; what the label selects -- a reference under
   .claude/skills/assuming-role/references/ -- is the procedure's, and like the
   slug it is not modelled as a value.

   `campaignIssue` stays `one`, and the slug hangs off nothing: adding it as a
   field would put an atom per campaign into the composed universe, which the
   note on `CampaignDir` in directory/system.als says is exactly what this model
   cannot afford, and it would buy no check -- uniqueness is GitHub's, and every
   comparison the model makes is between Campaign atoms already. */
sig Campaign {
  campaignIssue:      one Issue,       -- the campaign issue; its number is the campaign ID
  var memberIssues: set Issue,       -- ground truth
  var subIssues:     set Issue,       -- the index: GitHub's native sub-issue link
  var reposInBody:    set Repo         -- the campaign issue body's `## Repos` list
}

var sig Open   in Issue {}
var sig Merged in PullRequest {}
var sig Filed  in Campaign {}
/* The sub-issue branch: a ref on the remote, so one set over Issue rather than
   one set per machine. A claim made on one machine is readable from every
   other, which is the whole reason the branch is the claim.

   A CLAIM'S IDENTITY IS THE SUB-ISSUE, and the repository is the sub-issue's
   own -- `Issue.repo`, "where the work lands, never where the issue is filed".
   It is therefore not the taker's to choose, which is what `claimOnTheIssuesRepo`
   in orchestration/checks.als says and what `R8_ClaimCutOnAnotherRepo` shows
   the cost of dropping. The script agrees: `take` and `release` read the
   sub-issue's own `## Lands in` section and `--repo` may only confirm it.

   `## Lands in` is one heading holding one entry, `- owner/repo` or `- none`,
   read through the same slug reader `## Repos` uses, because one purpose in
   two shapes -- a keyword line on a sub-issue, a heading on a campaign issue
   -- needs two readers that agree only by both being exact. `- none` and the base's
   own slug are the same destination, which is why `campaign-repos.py` may
   refuse the base in `## Repos` and admit it here: the two sections ask
   different questions -- which repositories to CLONE, and where ONE
   sub-issue's work lands -- of one vocabulary. */
var sig Claimed in Issue {}

/* THE PERSON'S HOLD ON THE CLOSE, and the only precondition here that is not a
   fact about the work. `standing` is a label on the campaign issue, put on and
   taken off by a person alone: nothing can observe that they have changed their
   mind about keeping a campaign open, which is the same reason `backlog` is
   theirs. It sits in `closable` beside settlement because it is read at the
   same moment and refuses the same event -- `scripts/campaign-close.py`'s
   `campaign` scope, step 3, asks `campaign-tracker.py standing <N>` and
   stops on the word.

   `var` and otherwise unconstrained: a trace may drop a campaign out of
   `Standing` and close it in the next step, which is exactly what a person
   removing the label does. A frame condition would model a hold nobody can
   release, which is not the label. */
var sig Standing in Campaign {}

/* THE PERSON'S HOLD ON A SUB-ISSUE: `backlog`, a label on a sub-issue that
   the owner alone puts on and takes off, for the reason `standing` is
   theirs. A sub-issue carrying it is not worked, and `campaign-claim take`
   refuses a claim on one (`backlogDiscipline`); one without it is worked as
   soon as it is filed or reopened. `var` and unconstrained, as `Standing`
   is: the owner may lift it at any step. */
var sig Backlog in Issue {}

/* A JUDGMENT STANDS IN FOR AN AGENT'S READ, OR THE ISSUE GOES TO AN AGENT.
   `scripts/campaign-jev.py` asks a model one typed question about an issue's
   text and hands its caller a branch; `campaign-tracker.py check` is the first
   caller. FOUR bits decide whether that branch may replace the reading an
   agent would have made: the reading's tier is `act` (ACTING -- at `shadow` it
   only logs and at `advise` it only prints, so neither replaces anything), the
   call REPLIED (a key, an endpoint that answered, the pinned model, an answer
   for this question), the reply was CONFIDENT enough for its thresholds, and it
   FITS the question rather than naming the no-match option. Anything else is
   `unknown`, and the issue is handed up to an agent.

   `Replied` and not `Answered`: orchestration/system.als already has an
   `Answered`, over Agent, and a module that opens both would see two. `StandIn`
   and `HandUp` and not `Decide` or `Escalate` for the same reason: `Decide` is
   the planner's DECISION in orchestration/system.als, which opens this module,
   and `Escalat*` there names a BLOCKED going to a planner.

   THE RULE IS READ, which is what `advised` never was: `judgmentDiscipline`
   below gates `StandIn` on all four bits and `HandUp` on their absence, and
   `checks.als` runs that over traces with a `_Bites` that drops the tier bit
   and goes SAT. The retired `advised` was negated by its own scenario, so it
   could only fail when its one line was edited.

   ONE JUDGMENT, FOUR BITS, as `FileRead` in session/system.als: the rule
   judges one answer alone, so one atom with its bits free is every case, and a
   `one sig` needs no scope in any command that opens this module. */
one sig Judgment {}
sig Replied, Confident, Fits, Acting in Judgment {}

pred standsIn[j: Judgment] { j in Acting & Replied & Confident & Fits }

fact WellFormed {
  all c: Campaign | c.campaignIssue.repo = Base
  all disj c1, c2: Campaign | c1.campaignIssue != c2.campaignIssue
  always all p: PullRequest | lone pullRequest.p
  always all i: Issue | some i.pullRequest implies i.pullRequest' = i.pullRequest    -- a pull request link is never undone
  always all c: Campaign | c.campaignIssue not in c.memberIssues
  always all disj c1, c2: Campaign | no c1.memberIssues & c2.memberIssues
  always all p: PullRequest | p in Merged implies some pullRequest.p
  /* THE BASE IS NEVER IN `## Repos`. That list says which repositories to
     CLONE when a campaign opens, and the base reaches
     `<campaign>/repos/campaign-base/` by its own route, so a list naming it
     would have a campaign acquire a second checkout of the base over the
     first. It is the premise `claimWithinScope`'s `Base` disjunct rests on --
     no campaign lists the base, so no campaign is out of scope for changing
     it. `S20_TheBaseIsNeverListed` is the command that reddens when this line
     goes; `campaign-repos.py` is the reader that refuses the entry, and a
     fact stricter than its reader would be a false claim that reads as
     cautious. */
  always Base not in Campaign.reposInBody
}

/* Read from GitHub, so it survives the agent's death and the machine's
   reboot. */
pred complete[i: Issue] { i not in Open and some i.pullRequest and i.pullRequest in Merged }

/* Completion alone has no way to say "dropped": a member closed without a
   merged pull request never reads complete, so a campaign could never close
   over one. Both readings are needed (S2_SubIssueDropped). */
pred dropped[i: Issue] { i not in Open and not complete[i] }
pred settled[i: Issue] { complete[i] or dropped[i] }

/* The GitHub half. The other -- no role live under the tree -- is
   orchestration/system.als's. */
pred closable[c: Campaign]       { (all i: c.memberIssues | settled[i])
                                   and c not in Standing }
pred campaignClosed[c: Campaign] { c.campaignIssue not in Open }

/* S8 is what happens without it. */
pred closeDiscipline[c: Campaign] {
  always ((Now.event = CloseIssue and Now.issue = c.campaignIssue) implies closable[c])
}

/* No claim is cut on a sub-issue the owner holds back. Assumed and not a
   fact, as `closeDiscipline` is: `campaign-claim take` is its reader, and a
   fact could not show the claim it refuses. S22 is what happens without it. */
pred backlogDiscipline {
  always (Now.event = Claim implies Now.issue not in Backlog)
}

/* A trace that closes first and merges later satisfies `settled` the whole
   way and is not the path anyone runs, so scenarios meaning "merged" say so. */
pred mergeClosed[s: set Issue] {
  always (all i: s | (Now.event = CloseIssue and Now.issue = i)
                     implies (some i.pullRequest and i.pullRequest in Merged))
}

fun campaignOf[i: Issue]: lone Campaign { memberIssues.i }
fun campaignIssueOf[i: Issue]: lone Campaign { campaignIssue.i }
fun indexOf[c: Campaign]: set Issue { c.subIssues }

/* ---------------- observable events ---------------- */

abstract sig Event {}
one sig Stutter, FileCampaignIssue, AddMember, RemoveMember,
        OpenPullRequest, MergePullRequest, CloseIssue, WriteBody, Claim, Release,
        StandIn, HandUp extends Event {}

one sig Now {
  var event:    one Event,
  var issue: lone Issue,
  /* WHICH REPOSITORY THE EVENT ACTED ON. Without it the model cannot state the
     defect it fixes. `Issue.repo` says where a sub-issue's work lands, but
     nothing said where a CLAIM was cut, so "a taker cut the ref on a
     repository that is not the sub-issue's" had no spelling here.

     UNCONSTRAINED BY EVERY EVENT, `claim` INCLUDED, and deliberately: it is a
     record of what happened, not state, and the rule that ties it to the
     sub-issue is `claimOnTheIssuesRepo` in orchestration/checks.als. Written
     into `claim` itself it would be true in every world the model admits, so no
     scenario could exhibit its absence and R8b could never redden. */
  var repo:  lone Repo
}

fun githubEvents: set Event {
  FileCampaignIssue + AddMember + RemoveMember + OpenPullRequest + MergePullRequest + CloseIssue + WriteBody
  + Claim + Release + StandIn + HandUp
}

pred githubFrame {
  Open' = Open and Merged' = Merged and pullRequest' = pullRequest
  and memberIssues' = memberIssues and subIssues' = subIssues and reposInBody' = reposInBody and Filed' = Filed
  and Claimed' = Claimed
}

pred fileCampaignIssue[c: Campaign] {
  c not in Filed
  no c.memberIssues and no c.subIssues and no c.reposInBody
  Filed' = Filed + c
  Open'  = Open + c.campaignIssue
  memberIssues' = memberIssues and subIssues' = subIssues and reposInBody' = reposInBody
  Merged' = Merged and pullRequest' = pullRequest
  Claimed' = Claimed
  Now.event = FileCampaignIssue and Now.issue = c.campaignIssue
}

/* The issue and its index entry are one write. A member already in the index
   is never added again (`i not in Campaign.memberIssues`). This model has NO
   reopen event: a later discovery of the same mechanism reopens the existing
   issue by AGENTS.md § Sub-issues alone, and no command here checks the close
   gate against a member that returns to Open. Deliberately no session, machine
   or binding precondition: filing a sub-issue is a record, not a claim, so any
   session on any machine may do it (AGENTS.md § The binding). The binding
   gates the claim, which the claim script reads, not this model. */
pred addMember[c: Campaign, i: Issue] {
  c in Filed
  i not in Campaign.memberIssues and i not in Campaign.campaignIssue
  i not in Open and no i.pullRequest
  memberIssues' = memberIssues + c->i
  subIssues'     = subIssues + c->i
  Open'    = Open + i
  Merged' = Merged and pullRequest' = pullRequest and reposInBody' = reposInBody and Filed' = Filed
  Claimed' = Claimed
  Now.event = AddMember and Now.issue = i
}

/* The index prunes with the membership. */
pred removeMember[c: Campaign, i: Issue] {
  i in c.memberIssues
  memberIssues' = memberIssues - c->i
  subIssues'     = subIssues - c->i
  Open' = Open and Merged' = Merged and pullRequest' = pullRequest and reposInBody' = reposInBody and Filed' = Filed
  Claimed' = Claimed
  Now.event = RemoveMember and Now.issue = i
}

pred openPullRequest[i: Issue] {
  i in Campaign.memberIssues and i in Open and no i.pullRequest
  some p: PullRequest - Issue.pullRequest | pullRequest' = pullRequest + i->p
  Open' = Open and Merged' = Merged
  memberIssues' = memberIssues and subIssues' = subIssues and reposInBody' = reposInBody and Filed' = Filed
  Claimed' = Claimed
  Now.event = OpenPullRequest and Now.issue = i
}

pred mergePullRequest[i: Issue] {
  some i.pullRequest and i.pullRequest not in Merged
  Merged' = Merged + i.pullRequest
  Open' = Open and pullRequest' = pullRequest
  memberIssues' = memberIssues and subIssues' = subIssues and reposInBody' = reposInBody and Filed' = Filed
  Claimed' = Claimed
  Now.event = MergePullRequest and Now.issue = i
}

/* Nothing forbids closing an issue whose pull request never merged. */
pred closeIssue[i: Issue] {
  i in Open
  Open' = Open - i
  Merged' = Merged and pullRequest' = pullRequest
  memberIssues' = memberIssues and subIssues' = subIssues and reposInBody' = reposInBody and Filed' = Filed
  Claimed' = Claimed
  Now.event = CloseIssue and Now.issue = i
}

/* Deliberately loose. What the list is overwritten WITH is session/system.als's
   `sessionWriteBody`, satisfiable together with this precisely because this does not pin
   the value. */
pred writeBody[c: Campaign] {
  c in Filed
  reposInBody' - c->Repo = reposInBody - c->Repo
  Open' = Open and Merged' = Merged and pullRequest' = pullRequest
  memberIssues' = memberIssues and subIssues' = subIssues and Filed' = Filed
  Claimed' = Claimed
  Now.event = WriteBody and no Now.issue
}

/* Deliberately LOOSE -- it does not require the ref to be absent -- so that
   the atomicity is a named discipline above (orchestration/checks.als's
   `claimAtomic`) with its absence runnable as a control.

   AND `claimAtomic` IS NOT create-ref ALONE. `Claimed` is a set of ISSUES, so
   the discipline is per sub-issue; the ref that carries a claim is named
   `<slug>/<issue>-<topic>`, so create-ref's server-side refusal serialises ref
   NAMES and admits two topics on one sub-issue. Nothing here models a topic.
   What closes it is in the script: `take` reads the campaign's refs again
   AFTER its own create, and where two name one sub-issue, EVERY taker that
   sees a rival deletes what it just cut. A smallest-name tiebreak is wrong:
   the racers do not read the same set, so two of them can each believe they
   won. Yielding has no such state, and its worst case -- both yield, the
   sub-issue is left unclaimed -- the next `take` fixes.

   NOT scoped to a single repository. A claim is the sub-issue, and the
   repository is the sub-issue's own -- see `claimOnTheIssuesRepo` in
   orchestration/checks.als, whose R8b is what reddens if that stops
   holding. */
pred claim[i: Issue] {
  i in Campaign.memberIssues and i in Open
  Claimed' = Claimed + i
  Open' = Open and Merged' = Merged and pullRequest' = pullRequest
  memberIssues' = memberIssues and subIssues' = subIssues and reposInBody' = reposInBody and Filed' = Filed
  Now.event = Claim and Now.issue = i
}

/* What may be released is guarded above, in orchestration/checks.als: the condition
   is about an agent, which this entity does not have. */
pred release[i: Issue] {
  i in Claimed
  Claimed' = Claimed - i
  Open' = Open and Merged' = Merged and pullRequest' = pullRequest
  memberIssues' = memberIssues and subIssues' = subIssues and reposInBody' = reposInBody and Filed' = Filed
  Now.event = Release and Now.issue = i
}

/* THE TWO WAYS AN ISSUE GETS READ. `StandIn` is the judgment replacing the
   reading an agent would have made; `HandUp` is the same issue going to an
   agent instead. Neither changes a GitHub fact -- a reading is not a write --
   so both frame, and what they record is WHICH issue was read that way.

   NEITHER IS GUARDED HERE, and that is the point. `judgmentDiscipline` below
   is the rule, stated once and read by `checks.als` over traces; written into
   the preds instead, the rule would hold by construction and its check would
   be the shape `advised`/JV1b was -- true in every world the model admits, so
   no scenario could exhibit its absence. */
pred standIn[i: Issue] {
  i in Open
  githubFrame
  Now.event = StandIn and Now.issue = i
}

pred handUp[i: Issue] {
  i in Open
  githubFrame
  Now.event = HandUp and Now.issue = i
}

/* A judgment stands in only at tier `act` and only when the call replied,
   cleared its threshold and fits; otherwise the issue is handed up to an
   agent. `scripts/campaign-jev.py`'s `does` is the code side: `nothing` at
   `shadow` and for every `unknown`, `show` at `advise`, and only at `act` the
   reversible thing its entry names. */
pred judgmentDiscipline {
  always (Now.event = StandIn implies standsIn[Judgment])
  always (Now.event = HandUp implies not standsIn[Judgment])
}

pred stutter {
  githubFrame
  Now.event = Stutter and no Now.issue
}

/* Admits a campaign already in flight, an unfiled one, or any mixture:
   session/system.als has to be able to file a campaign issue, and the scenarios have to be
   able to start with one already filed. */
pred githubInit {
  no Merged
  no Claimed
  no pullRequest
  all c: Campaign - Filed | no c.memberIssues and no c.subIssues and no c.reposInBody
  Open = Filed.campaignIssue + Campaign.memberIssues
  all c: Campaign | c.subIssues = c.memberIssues
}

pred githubStep {
  stutter
  or (some c: Campaign | fileCampaignIssue[c] or writeBody[c])
  or (some c: Campaign, i: Issue | addMember[c,i] or removeMember[c,i])
  or (some i: Issue | openPullRequest[i] or mergePullRequest[i] or closeIssue[i]
                      or claim[i] or release[i] or standIn[i] or handUp[i])
  or (Now.event not in Stutter + githubEvents and githubFrame)
}

fact GithubTrace { githubInit and always githubStep }
