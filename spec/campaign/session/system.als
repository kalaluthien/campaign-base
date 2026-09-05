/*
 * A campaign session: what makes a session one, and what it may do. It opens
 * synchronization/system because a session runs from a base checkout and
 * cares how far behind it is.
 *
 * A SESSION is one harness session -- the `claude` process a herdr pane runs,
 * and the thing a campaign session name names. That name's shape is not
 * restated here: `scripts/campaign-name-session.py` owns it, and a second
 * statement of it would admit names that script refuses. An agent sits ABOVE
 * it, because an agent is a session working its own claim or a delegate a
 * session launched, so the dependency runs orchestration -> session and
 * cannot be nested the other way.
 *
 *   Request   the one request being routed, and which campaigns cover it.
 *   Session   a campaign session: its machine, what it is FOR, the campaign it
 *             works on, what its survey returned, the repository lists in its
 *             README and in the campaign issue body as it last read that body,
 *             and the sub-issues it has claimed.
 *   Role      what a session is for, read from its name: a Planner writes the
 *             campaign plane and never code; a Worker works its own
 *             campaign's sub-issues, and only the ones it has claimed.
 *   Surveyed  the sessions that have run the new-versus-follow-up survey.
 *   Binding   the campaign issue's `bound:<machine>` label.
 *   Who       the observer: which session performed the current event.
 *
 * A session is in a campaign exactly when the campaign is bound to its machine.
 * What this entity does NOT know is whether anything is running, so every
 * finding below is one a campaign session reaches with no delegate anywhere.
 *
 * "Covers the request" is a fixed bit, not a judgement over the Scope prose.
 * There is no `gh` latency here, so each window measured is a minimum.
 * Migration has no event, because nothing here can observe its premise.
 */
module session/system

open synchronization/system

/* `covers` hangs off a `one sig` because Campaign is github/system's signature and an
   entity above it may not add a field to it. */
one sig Request { covers: set Campaign }

/* WHAT A SESSION IS FOR, read from its name -- `campaign-<N>-<role>-<n>`, whose
   pattern `scripts/campaign-name-session.py` owns and which is not restated
   here for the same reason the name's shape is not. `herdr agent list` is what
   joins a harness session id to that name, so this is a fact a guard can read
   about its own caller.

   `lone`, not `one`: a session with no name, or a name of another shape, has no
   role, and that is the last row of #185's table -- refused on both planes,
   which `mayAct` in orchestration/scenarios.als states. A worker is bounded
   to its own campaign's sub-issues it has claimed, PLUS that campaign's own
   issue, which is no sub-issue and which no claim can cover (#207).

   It lives HERE and not in orchestration/system.als, where `Role` used to be a
   property of an Agent: the role is per SESSION and per its whole life, where an
   agent is per sub-issue, and a guard reading a tool call has a session and no
   agent. `Agent.role` stays, pinned to its session's by AgentWellFormed.

   Not `var`. A session that renames itself is out of scope here: nothing in this
   model reads a rename, and the records already written keep the old name. */
abstract sig Role {}
one sig Planner extends Role {}
one sig Worker  extends Role {}

/* WHETHER A SESSION SITS UNDER THE BASE TREE, and nothing more. Added by #187
   question 6 for the same reason `campaignNamed` was: a close gate reads
   herdr's `cwd` column, and this is the one bit a reader acts on. The PATH is
   not modelled -- `under(cwd, root)` in `campaign-claim.py` owns that, whole
   segments and both sides resolved.

   NOT a fact about any campaign: a session under the tree is under EVERY
   campaign's tree here, which is exactly why the cwd cannot attribute a
   session and the name has to. */
var sig UnderBase in Session {}

sig Session {
  machine:          one Machine,
  role:             lone Role,
  var worksOn:      lone Campaign,
  var surveyResult: set Campaign,  -- what its new-versus-follow-up survey returned
  var reposInReadme:     set Repo,        -- its campaign README's `## Repos` list
  var reposInBodyAsRead: set Repo,        -- the campaign issue body's list as it last read it
  var claimedIssues:     set Issue,       -- sub-issue branches it created on the remote
  /* WHICH CAMPAIGN THIS SESSION'S NAME SAYS IT IS OF, and `lone` because a
     name may say nothing -- a session that never named itself, or one whose
     name is not of the shape `campaign-<N>-<role>-<n>`. The name itself is not
     modelled and must not be: `scripts/campaign-name-session.py` owns its
     spelling, and a second statement of it here would admit names that script
     refuses. What is modelled is only the one thing a reader does with it --
     tell whose campaign a session claims to be of -- which is the discriminator
     orchestration/system.als's `namedForAnother` needs and which no other field
     can supply. It is `var` because a session renames itself. */
  var campaignNamed:     lone Campaign
}
var sig Surveyed in Session {}

/* The campaign issue's `bound:<machine>` label. A GitHub fact, so the layering
   rule would put it in github/system.als -- but its value is a Machine and its
   source is the filing session's own `machine`, and this is the lowest entity
   that has either. The placement follows from that, not from the binding being
   local.

   A LABEL, NOT A COMMENT, and `lone` below is the whole difference. A comment
   thread holds every binding a campaign ever had and a reader has to pick the
   latest, so it parses prose and orders by time to answer one question. A
   label set is read by exact name, and a campaign carrying two `bound:` labels
   is a state the reader refuses rather than resolves -- which is what this
   fact says, and why nothing here models a history. */
one sig Binding {
  var bound: Campaign -> Machine
}

fact BindingWellFormed {
  always all c: Campaign | lone Binding.bound[c]
}

one sig Who { var session: lone Session }

/* Derived, so no event has to maintain it. */
fun working: set Session { { s: Session | some s.worksOn and s.machine in machinesHolding[s.worksOn] } }

/* ---------------- observable events ---------------- */

one sig Survey, Adopt, ReadBody, EditReadme extends Event {}

fun sessionOwn: set Event { Survey + Adopt + ReadBody + EditReadme }

/* `MergePullRequest` is here rather than in `unattended` because landing a pull request
   is somebody's act, and naming whose is what lets orchestration/scenarios.als's
   `mergedOnCurrentReview` hold the merger to a current review. */
fun sessionActed: set Event {
  sessionOwn + FileCampaignIssue + AddMember + CloseIssue + WriteBody + MergePullRequest
  + CreateDir + DeleteDir + Acquire + Claim + Release + Launch
}

/* `RemoveMember` is here because moving a sub-issue out has no sanctioned flow:
   it is a hand-run `gh issue edit --remove-parent`. */
fun unattended: set Event {
  OpenPullRequest + RemoveMember + PullBase + PullClone + CommitLocal
}

pred sessionFrame {
  worksOn' = worksOn and surveyResult' = surveyResult and reposInReadme' = reposInReadme
  and reposInBodyAsRead' = reposInBodyAsRead
  and claimedIssues' = claimedIssues and campaignNamed' = campaignNamed and UnderBase' = UnderBase and Surveyed' = Surveyed
  and bound' = bound
}

/* The result is remembered; nothing keeps it fresh. */
pred survey[s: Session] {
  let X = { c: Campaign | c in Filed and c.campaignIssue in Open and c in Request.covers } |
    surveyResult' = surveyResult - s->Campaign + s->X
  Surveyed' = Surveyed + s
  worksOn' = worksOn and reposInReadme' = reposInReadme and reposInBodyAsRead' = reposInBodyAsRead and claimedIssues' = claimedIssues and campaignNamed' = campaignNamed and UnderBase' = UnderBase
  bound' = bound
  Now.event = Survey and no Now.issue and Who.session = s
}

/* Nothing is taken: under one role, arriving is just starting to work.
   Unguarded here, so the unrepaired scenarios stay measurable against the same
   trace space; `boundOnly` is the membership rule applied per command. */
pred adopt[s: Session, c: Campaign] {
  c in Filed and c.campaignIssue in Open
  no s.worksOn
  worksOn'      = worksOn  - s->Campaign + s->c
  reposInReadme'     = reposInReadme - s->Repo + s->(c.reposInBody)
  reposInBodyAsRead' = reposInBodyAsRead - s->Repo + s->(c.reposInBody)
  surveyResult' = surveyResult and Surveyed' = Surveyed and claimedIssues' = claimedIssues and campaignNamed' = campaignNamed and UnderBase' = UnderBase
  bound' = bound
  Now.event = Adopt and no Now.issue and Who.session = s
}

pred readBody[s: Session] {
  some s.worksOn
  reposInReadme'     = reposInReadme - s->Repo + s->(s.worksOn.reposInBody)
  reposInBodyAsRead' = reposInBodyAsRead - s->Repo + s->(s.worksOn.reposInBody)
  worksOn' = worksOn and surveyResult' = surveyResult and Surveyed' = Surveyed and claimedIssues' = claimedIssues and campaignNamed' = campaignNamed and UnderBase' = UnderBase
  bound' = bound
  Now.event = ReadBody and no Now.issue and Who.session = s
}

pred editReadme[s: Session, r: Repo] {
  some s.worksOn
  r not in s.reposInReadme
  reposInReadme' = reposInReadme + s->r
  worksOn' = worksOn and surveyResult' = surveyResult and reposInBodyAsRead' = reposInBodyAsRead
  and Surveyed' = Surveyed and claimedIssues' = claimedIssues and campaignNamed' = campaignNamed and UnderBase' = UnderBase
  bound' = bound
  Now.event = EditReadme and no Now.issue and Who.session = s
}

/* --- refinements: the session and the guard on a lower entity's event --- */

/* The binding is posted in the same step, because everything after it is a
   write or a launch and both are gated on it. */
pred sessionFileCampaignIssue[s: Session] {
  Now.event = FileCampaignIssue
  s in Surveyed
  no s.surveyResult             -- the survey found no campaign covering the request
  no s.worksOn
  worksOn' = worksOn - s->Campaign + s->campaignIssueOf[Now.issue]
  bound' = bound - Binding->campaignIssueOf[Now.issue]->Machine
           + Binding->campaignIssueOf[Now.issue]->s.machine
  surveyResult' = surveyResult and reposInReadme' = reposInReadme and reposInBodyAsRead' = reposInBodyAsRead
  and Surveyed' = Surveyed and claimedIssues' = claimedIssues and campaignNamed' = campaignNamed and UnderBase' = UnderBase
  Who.session = s
}

pred sessionAddMember[s: Session] {
  Now.event = AddMember
  some s.worksOn
  s.worksOn->Now.issue in memberIssues'
  sessionFrame
  Who.session = s
}

/* Any other issue is an ordinary sub-issue close and needs no such tie. */
pred sessionCloseIssue[s: Session] {
  Now.event = CloseIssue
  Now.issue in Campaign.campaignIssue implies s.worksOn = campaignIssueOf[Now.issue]
  sessionFrame
  Who.session = s
}

/* Where github's `writeBody` says whose README the list changed to.
   Unguarded as written; `compareThenWriteBody` is the repair. */
pred sessionWriteBody[s: Session] {
  Now.event = WriteBody
  some s.worksOn
  reposInBody' = reposInBody - s.worksOn->Repo + s.worksOn->(s.reposInReadme)
  reposInBodyAsRead' = reposInBodyAsRead - s->Repo + s->(s.reposInReadme)
  worksOn' = worksOn and surveyResult' = surveyResult and reposInReadme' = reposInReadme
  and Surveyed' = Surveyed and claimedIssues' = claimedIssues and campaignNamed' = campaignNamed and UnderBase' = UnderBase
  bound' = bound
  Who.session = s
}

/* Two sessions on one machine resolve <slug>-<YYMMDD>/ to the same path, so
   the directory is per campaign per machine, not per session. */
pred sessionCreateDir[s: Session] {
  Now.event = CreateDir
  some s.worksOn
  Where.machine = s.machine
  some campaignDirAt[s.worksOn, s.machine] and campaignDirAt[s.worksOn, s.machine] in OnDisk'
  bound' = bound
  worksOn' = worksOn and surveyResult' = surveyResult and reposInReadme' = reposInReadme
  and reposInBodyAsRead' = reposInBodyAsRead
  and claimedIssues' = claimedIssues and campaignNamed' = campaignNamed and UnderBase' = UnderBase and Surveyed' = Surveyed
  Who.session = s
}

/* `runtime/` goes with the directory, and nothing above has a bit with that
   lifetime any more: since the claim became a ref and attribution a checkout,
   orchestration/system.als frames straight through a delete. */
pred sessionDeleteDir[s: Session] {
  Now.event = DeleteDir
  some s.worksOn
  Where.machine = s.machine
  some campaignDirAt[s.worksOn, s.machine] and campaignDirAt[s.worksOn, s.machine] not in OnDisk'
  bound' = bound
  worksOn' = worksOn and surveyResult' = surveyResult and reposInReadme' = reposInReadme
  and reposInBodyAsRead' = reposInBodyAsRead
  and claimedIssues' = claimedIssues and campaignNamed' = campaignNamed and UnderBase' = UnderBase and Surveyed' = Surveyed
  Who.session = s
}

pred sessionAcquire[s: Session] {
  Now.event = Acquire
  some s.worksOn
  Where.machine = s.machine
  -- the checkout that moved is in this session's campaign tree
  checkedOut' - campaignDirsOf[s.worksOn]->Repo->Branch = checkedOut - campaignDirsOf[s.worksOn]->Repo->Branch
  sessionFrame
  Who.session = s
}

/* Which session created it is what `claimedIssues` records; that the ref exists at
   all is github/system.als's `Claimed`.

   A CLAIM IS A CAMPAIGN-PLANE WRITE, so #185's rule reaches it: a planner writes
   the campaign plane of any campaign, and the claim it cuts for a delegate may
   name a sub-issue of any campaign BOUND TO ITS OWN MACHINE -- the delegate then
   works that campaign under that campaign's name. A worker's claim stays
   pinned to the campaign it works on, and so does a session with no role, since
   `s.role != Planner` holds of an empty role. Q10/Q10b/Q10c are the witnesses.
   The binding conjunct is not decoration: it is the one campaign, one machine
   rule, and without it this would let a session claim into a campaign running
   somewhere else. */
pred sessionClaim[s: Session] {
  Now.event = Claim
  some s.worksOn
  s.role = Planner  implies s.machine in machinesHolding[campaignOf[Now.issue]]
  s.role != Planner implies Now.issue in s.worksOn.memberIssues
  claimedIssues' = claimedIssues + s->Now.issue
  campaignNamed' = campaignNamed and UnderBase' = UnderBase
  worksOn' = worksOn and surveyResult' = surveyResult and reposInReadme' = reposInReadme
  and reposInBodyAsRead' = reposInBodyAsRead and Surveyed' = Surveyed
  bound' = bound
  Who.session = s
}

/* Dropped by whoever reads the branch as dangling, not only by its maker.
   What may be released is orchestration/scenarios.als's guard. */
pred sessionRelease[s: Session] {
  Now.event = Release
  claimedIssues' = claimedIssues - Session->Now.issue
  campaignNamed' = campaignNamed and UnderBase' = UnderBase
  worksOn' = worksOn and surveyResult' = surveyResult and reposInReadme' = reposInReadme
  and reposInBodyAsRead' = reposInBodyAsRead and Surveyed' = Surveyed
  bound' = bound
  Who.session = s
}

/* Loose: this entity says only that a session did it. */
pred sessionMergePullRequest[s: Session] {
  Now.event = MergePullRequest
  sessionFrame
  Who.session = s
}

pred sessionLaunch[s: Session] {
  Now.event = Launch
  some s.worksOn
  Where.machine = s.machine
  s.machine in machinesHolding[s.worksOn]
  Now.issue in s.worksOn.memberIssues and Now.issue in Open
  sessionFrame
  Who.session = s
}

/* A session may already hold a campaign at time zero; the scenarios ABOUT
   arriving require the arrival events explicitly. `bound` is deliberately
   unconstrained: a campaign in flight was bound by a session this trace never
   contains. */
pred sessionInit {
  no Surveyed
  all s: Session {
    s.worksOn in Filed
    no s.surveyResult and no s.claimedIssues
    s.reposInReadme = s.worksOn.reposInBody and s.reposInBodyAsRead = s.worksOn.reposInBody
  }
}

pred sessionStep {
  (Now.event = Stutter and sessionFrame and no Who.session)
  or (some s: Session | survey[s] or readBody[s] or sessionWriteBody[s]
        or sessionFileCampaignIssue[s] or sessionAddMember[s] or sessionCloseIssue[s]
        or sessionCreateDir[s] or sessionDeleteDir[s] or sessionAcquire[s]
        or sessionClaim[s] or sessionRelease[s] or sessionLaunch[s] or sessionMergePullRequest[s])
  or (some s: Session, c: Campaign | adopt[s,c])
  or (some s: Session, r: Repo | editReadme[s,r])
  or (Now.event in unattended and sessionFrame and no Who.session)
  /* an event declared in an entity above: it names its own session, or none */
  or (Now.event not in Stutter + sessionActed + unattended and sessionFrame)
}

fact SessionTrace { sessionInit and always sessionStep }
