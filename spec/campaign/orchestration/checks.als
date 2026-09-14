/*
 * The disciplines a shutdown, a claim, a delete and a merge might follow, the
 * witnesses that measure each, what must hold of orchestration/system, and
 * the floor that says its events are reachable at all. github/system.als is
 * spec/'s entry point.
 */
module orchestration/checks

open orchestration/system

/* ---------------- the property ---------------- */

/* The one thing the protocol is for. */
pred noWorkDestroyed {
  always (Now.event = Retire implies Target.agent not in LocalOnly)
}

/* ---------------- disciplines: the shutdown ---------------- */

/* The confirmation is the session looking for itself, and it is what keeps
   the work: without it TwoStepShutdownSuffices has a counterexample. The
   answer names work only the agent can see; `noWorkDestroyed` does not need
   it, since `confirm` requires `a not in LocalOnly` and `work` clears
   `Confirmed`. */
pred twoStepShutdown {
  always (Now.event in StandDown + Retire implies
            (Target.agent in Answered and Target.agent in Confirmed))
}

/* Rule 3: an agent that is gone may be stood down on the confirmation
   alone, and only on it. */
pred resolveSilenceExternally {
  always (Now.event in StandDown + Retire implies
            (Target.agent in Confirmed
             and (Target.agent in Answered or Target.agent not in Live)))
}

/* THE FRESH CLAIM, and the hole `agentRelease` leaves. Its two guards are both
   over AGENTS -- nothing on this issue is pushed, and nothing of it is live
   here -- so a claim cut before any agent exists satisfies both VACUOUSLY and
   is releasable by anyone. That is not a modelling artefact: a claim is cut
   before the delegate that will work it is launched, so every claim passes
   through exactly this state, and on GitHub it is indistinguishable from
   finished work -- both are a branch level with main.

   The discipline: release only what some agent has actually been launched on,
   or what is complete. NOT MODELLED is the escape the script keeps for the
   case a person has established the holder is gone (`--confirmed-absent`),
   because no atom here carries a person's word. No command pins the
   `Launched` disjunct: R7b is its expect-0 half, and R7d and R7e exclude
   `Launched`.

   THE `Launched` DISJUNCT IS WIDER THAN THE SCRIPT. `Launched` is a fact
   about an agent, and the script has no reader for it: on GitHub that state
   -- launched, dead, nothing pushed -- is a ref 0 ahead of the base whose
   branch was never a merged pull request's head, which is the one shape
   `cmd_release` refuses without `--confirmed-absent WHO`. And that is the SECOND
   refusal that state hits, not the first: `launch` checks the branch out and
   neither `agentDie` nor `retire` undoes it, so the dead delegate's clone still
   holds the branch and the occupant check refuses before the merge question is
   ever asked -- a refusal `--confirmed-absent` does not lift, since removing a
   worktree is not something a person's word stands in for. So the release
   this disjunct admits is, on the machine, a worktree removal and then a
   release that asks a person. What
   would close the gap is a durable fact saying a holder was launched at all. */
pred releaseNeedsAWorker {
  always (Now.event = Release implies
            (settled[Now.issue]
             or some a: Agent | a.task = Now.issue and a in Launched))
}

/* R4g drops `claimAtomic` alone and the collision returns, so the server-side
   half -- not the ritual -- is load-bearing. `claimAtomic` is keyed on the
   ISSUE, and create-ref is keyed on the ref NAME, which carries a topic this
   model does not have; github/system.als's `claim` says what closes the
   difference. */
pred claimBeforeLaunch { always (Now.event = Launch implies Now.issue in Who.session.claimedIssues) }
pred claimAtomic       { always (Now.event = Claim  implies Now.issue not in Claimed) }

/* THE REPOSITORY IS THE SUB-ISSUE'S, NOT THE TAKER'S. `claimAtomic` above is
   keyed on the issue and already forbids two claims on one sub-issue -- but it
   forbids them only among takers who agree about where the ref goes. Let each
   taker name its own repository and the two cut different refs, neither sees
   the other's listing, and the model's one-claim-per-issue reading is satisfied
   by a world in which two workers are working the same sub-issue. The repair
   is not a wider sweep, which would still be a survey of a set the takers do
   not agree about; it is that the destination is a FACT ABOUT THE SUB-ISSUE
   (`Issue.repo`, read from its `## Lands in` section) that no taker supplies. */
pred claimOnTheIssuesRepo {
  always (Now.event = Claim implies Now.repo = Now.issue.repo)
}

/* ...AND THE SUB-ISSUE'S REPOSITORY IS ONE THE CAMPAIGN IS FOR. The rule above
   makes the destination the sub-issue's own fact; this is the other half, that
   the fact agrees with the charter. `## Repos` is what a person signed up for
   (`Campaign.reposInBody`), so a sub-issue naming a member repository outside
   it is a scope change filed as a typo, and cutting the ref would widen the
   campaign silently.

   THE `Base` DISJUNCT IS THE WHOLE DIFFICULTY, and it is not a special case
   bolted on: `## Repos` lists the MEMBER repositories a campaign clones when it
   opens, and the base is a member of its own campaign by another route, so no
   campaign lists it and no campaign is out of scope for changing it.
   A sub-issue may land in the base (`i.repo = Base` reads "its work lands in
   the base", github/system.als); `R4_RepolessCampaign` already claims one with
   `always no c.reposInBody`. What neither covers is a NON-EMPTY list that does
   not hold the base -- the shape every campaign with a member repository has.
   R14d is that world, and it goes UNSAT the moment this disjunct is dropped.

   `campaignOf[Now.issue]` is the sub-issue's ACTUAL parent. campaign-claim.py's
   `take` reads the parent and refuses a sub-issue whose parent is a campaign
   other than the one named. Two outcomes it does NOT refuse, and each prints
   apart: a parent that could not be read (not a parent that disagrees), and an
   issue with no parent at all, which #1 sitting at GitHub's 100-sub-issue cap
   keeps producing. `release` and `live` stay keyed on the typed number on
   purpose -- they read refs already cut, so a parentage check there would
   refuse to reach exactly the mis-cut ref this closes.

   `campaignOf` is NEVER EMPTY at a Claim, so no vacuous branch hides in the
   second disjunct: `claim` in github/system.als already requires
   `i in Campaign.memberIssues`. That is why the membership conjunct in R14 and
   R14c is a statement of the world rather than a constraint, and why removing
   it moves no verdict.
   Separately, the base's absence from `## Repos` is `WellFormed`'s last
   conjunct in github/system.als, pinned by
   `S20_TheBaseIsNeverListed`, and refused by `campaign-repos.py`. R14d's own
   `Base not in c.reposInBody` is therefore a statement of the world rather
   than a constraint, and removing it moves no verdict -- it is kept because
   the command's comment argues from it.

   A RULE WITH ONE READER IS A RULE WITH ONE ROUTE, and there is a second.
   `campaign-claim take` is the reader of this
   rule; `gh issue develop --name <slug>/<issue>-<topic>` cuts the same
   ref and reads none of it -- not this scope, not the parent `campaignOf`
   names, not the binding. Nothing in the model separates the two, and nothing
   can: a `Claim` is a `Claim` whichever command made it, which is the point.
   So the separation is the guard's, and `PLANNER_GH_EXCEPT` in
   check-campaign-claim.py is where it is written: the one `gh issue` verb a
   planner's campaign-plane licence does not carry, kept out for the route it
   is and not for the plane it is on -- `Claim` is in `campaignPlaneEvents` in
   system.als, so a plane reading admits it.

   WHAT IS ENFORCED IS THE PLANNER'S ROUTE AND ONLY IT. The guard REFUSES the
   verb in its planner branch; every other session still reaches it through the
   claim reading, so one already holding a claim on an issue may cut a second,
   unscoped branch for that issue and this rule does not see it. Narrower --
   it needs a claim on the very issue named -- and unenforced all the same. */
pred claimWithinScope {
  always (Now.event = Claim implies
            (Now.issue.repo = Base
             or Now.issue.repo in campaignOf[Now.issue].reposInBody))
}

/* The gate on LAUNCH covers the agent a session starts and says nothing
   about the agent a session IS: `work` carries no `Who.session`, so a session
   working its own claim reaches the same sub-issue along an edge
   `claimBeforeLaunch` never touches. R4h is that hole and R4i is its repair --
   scripts/check-campaign-claim.py, a PreToolUse guard refusing a changing call
   from a session holding no claim. Keyed on `a.peer` because a delegate has no
   session to hold one; its launcher was gated already.

   `Work` is what the gate is on, and what makes a call `Work` is its TARGET,
   not where the session sits: a change landing outside every base tree,
   every campaign directory and every install a `## Repos` entry names (the
   last read by the commit half alone, #389) is not work on a sub-issue and
   is no step of this relation. The guard reads the target over two bounded languages and
   no other: a file tool's path, and a `gh` command, which is one program with
   a stable grammar -- a write to the campaign plane through it has no
   filesystem target at all and is always `Work`, and a `gh` call the guard
   READS AS A CALL and cannot parse is refused, never guessed. The narrower
   verb is deliberate: a `gh` write can always be hidden
   from a bounded reader by a shell that is not read -- a here-string, a pipe
   into a shell, a script file, an interpreter that is not a shell -- so a
   sentence promising that no `gh` write escapes is one the code cannot make
   true. What
   the guard does promise: a `gh` TOKEN it can see and cannot resolve to a
   call is refused rather than guessed at. On the other side of that line the
   guard reads the `-c` string of the shells it NAMES, spelled alone or last in
   a cluster -- a named list, not the category, because there is no test for
   "is a shell" and a shell it does not name (`csh`, `tcsh`) is unread like any
   other interpreter. The line is drawn at a list rather than at a category on
   purpose: a category is a promise about programs this has never seen.

   A shell command is NOT read for a target: an arbitrary shell string is an
   unbounded language, and every reader of it is one more alternation for the
   next bypass. Such a call is
   allowed at the moment it is made, printing that it was unread, and its
   write is `Work` at the moment it LANDS -- `claimBeforeCommit` below, the
   pre-commit gate. R4k states the gap that leaves open until the commit. No
   atom here carries a path, so the reading itself is the script's and is
   stated in its docstring; the model says only that a write on nothing this
   campaign owns is outside `Work`. */
pred claimBeforeWork {
  always (Now.event = Work and some Target.agent.peer
            implies Now.issue in Target.agent.peer.claimedIssues)
}

/* THE VERDICT IS DURABLE. `claimBeforeWork`
   above is the gate; this is the rule that the gate leaves a record of what it
   decided. Without it a guard that judged every call and wrote nothing
   satisfied the whole model: its precision could only be reconstructed from
   the memory of whoever it refused.

   ON `Work` AND NOT ON EVERY EVENT, and the bound is the reader's: the guard
   is a PreToolUse hook, so what it can log is the calls it is handed. A rule
   over every event would be a claim about writes no hook sees -- a `sed -i`,
   a shell redirect -- and a model stricter than its reader is a false claim
   that reads as cautious.

   R15 is the world without it, R15b the repair, R15c the control that the
   repair does not forbid the work itself. */
pred verdictIsDurable {
  always (Now.event = Work implies Now.issue in Judged')
}

/* ---------------- discipline: permission by role ---------------- */

/* The events a worker may not reach on the campaign plane whatever it holds.
   `WriteBody` because the campaign issue body changes only at a scope change or
   at the close, both a person's decision carried by a planner; and
   `FileCampaignIssue` because filing one is opening a campaign. Filing a
   SUB-ISSUE is not here: `addMember` in github/system.als has no actor
   precondition on purpose, and any session may file one. */
fun plannerOnlyEvents: set Event { WriteBody + FileCampaignIssue }

/* Whether a session may perform this event on this issue. The table:

     planner    campaign plane, any campaign            code plane: never
     worker     campaign plane, its own campaign and
                only a sub-issue it holds a claim on    code plane: only a
                                                        sub-issue it has claimed
     no role    refused on both planes

   A comment and a reopen are no event here, so the table is silent on them;
   the guard lets a worker comment on its own campaign's issue, and
   comment on or reopen any sub-issue of that campaign without a claim.

   The issue argument is `lone` and the `in` tests are vacuously true when there
   is none, which is the right reading and not an accident: `writeBody` and the
   directory events name no issue, and for those the rule is the plane and the
   event, not the issue. `plannerOnlyEvents` is what carries the body and the
   filing, since the issue test alone would let `writeBody` through.

   `Claim` is carved out of the worker's claim test because taking a claim
   cannot itself require one -- `claimedIssues` grows in the NEXT state. What
   still bounds it is `sessionClaim`, which requires the issue to be in the
   session's own campaign.

   `Release` by a planner requires the claim to be VACANT: a planner may drop a
   dangling claim, and may not take one out from under a worker holding it.

   `mayAct` for a planner drops the `worksOn` conjunct, so this discipline
   permits a planner to claim for a delegate on any campaign. `sessionClaim` in
   session/system.als agrees. It splits by role
   and bounds the planner's by the MACHINE -- any campaign whose directory is
   on the session's own machine (`machinesHolding`) -- and Q10/Q10b/Q10c are the three that say which of
   the two rules refuses a worker the same claim. */
/* WHAT THIS IS NOT. `s.role` is read from the session's own name, and a session
   can rename itself -- so this table bounds MISTAKES and not adversaries. It is
   not weaker than what it replaces: every session on a machine shares one `gh`
   account, so a session that renames itself a planner already holds the power
   the name would grant, and what the rule buys is that the role is explicit and
   the mistake is loud. Stated here because a permission table is the thing a
   reader is most likely to mistake for a security boundary. */
/* THE CAMPAIGN ISSUE IS NOT A SUB-ISSUE. `memberIssues` excludes it
   (github/system.als), so `i in s.worksOn.memberIssues` refuses a worker every
   write to the issue of the campaign it works -- including a comment, which
   the model has no precondition on. The worker's campaign-plane row therefore
   admits the campaign issue of its OWN campaign, and `Q11` is the witness.

   Bounded by the EVENT and not by a claim: the guard admits only a comment
   there, because `WriteBody` is the charter and belongs to the close, and a
   claim on some other sub-issue makes an irreversible write no safer. The
   guard's `own_campaign_gh` (campaign-roles.py) is the verb list; this is the event.

   WHICH CAMPAIGN'S issue this rule holds -- `i = s.worksOn.campaignIssue`,
   the session's own and no other -- is pinned by Q14, through Release. Not
   through CloseIssue: `sessionCloseIssue` in session/system.als already ties
   every campaign-issue close to the acting session's own campaign, for every
   role. `sessionRelease` has no such tie and no claim precondition, and a
   campaign issue may start as another campaign's sub-issue (WellFormed bars
   only its own), be claimed there and leave by RemoveMember -- so a worker
   releasing that claim is refused by this conjunct alone, and widening it to
   `i in Campaign.campaignIssue` turns Q14 SAT. Its two neighbours are pinned
   too: dropping the disjunct reddens `Q11`, dropping `i not in
   Campaign.memberIssues` reddens `Q4`. The guard's own bound, `i ==
   own_number`, is tested in check-campaign-claim-test.py.

   `i not in Campaign.memberIssues` is not decoration. Nothing in github/system
   forbids one campaign's ISSUE from being another campaign's SUB-ISSUE -- an
   overlap that cannot happen on the tracker, where a campaign issue carries
   the `campaign` label and a sub-issue is somebody's `--parent` -- and without
   the conjunct the carve-out reached it, which Q4 caught. Bounded here rather
   than by a new fact, because the fact is github/system's to add. */
/* THE BRIEF IS THE SECOND READING, and it is about the CONTEXT rather than the
   session: `some s.role` asks whether the session has a role at all, `s in
   Briefed` asks whether the context it is acting from still states it. A
   compaction clears the second and leaves the first alone, which is the whole
   reason `campaign-role-brief.py` runs on SessionStart. NO SCRIPT ENFORCES
   THIS ROW -- the guard reads the name, not the brief -- so Q12 measures a rule
   the hook is the only reader of, and says so rather than implying a refusal
   nobody makes.

   THE STAMP IS THE THIRD, and NO SCRIPT REFUSES ITS ROW EITHER. A role is
   found by joining the caller's session id to `herdr agent list`'s
   `agent_session`, so a pane that lost its stamp names no session -- and the
   guard reads that as could-not-look, not as a session with no name: `role_of`
   returns no role, and check-campaign-claim.py falls back to the claim reading
   alone on purpose, so an unstamped worker holding a claim still writes. What
   the stamp buys is that the role is read at all; `herdr-session-link.py` is
   the only thing that keeps it, restoring it on the next prompt, which Q13b
   pins. Q13 measures that discipline, and says so rather than implying a
   refusal nobody makes. */
pred mayAct[s: Session, e: Event, i: lone Issue] {
  some s.role
  s in Briefed
  s in Stamped
  s.role = Planner implies (planeOf[e] = CampaignPlane
                            and (e = Release implies no claimedIssues.i))
  s.role = Worker implies (
    (planeOf[e] = CampaignPlane implies (e not in plannerOnlyEvents
                                         and ((i = s.worksOn.campaignIssue
                                               and i not in Campaign.memberIssues)
                                              or (i in s.worksOn.memberIssues
                                                  and (e != Claim implies i in s.claimedIssues)))))
    and (planeOf[e] = CodePlane implies i in s.claimedIssues))
}

/* Two readers, because a write reaches the model two ways. `Who.session` is the
   session that performed the event, which is every campaign-plane write. The
   code plane has `no Who.session` -- `work` and `push` are the AGENT's edges --
   so the second conjunct reads the session the agent IS. A delegate has no
   peer, and is unguarded here on purpose: the guard reads a session's own name,
   and a delegate has a session and a name of its own. */
pred permissionByRole {
  always (some Who.session and some planeOf[Now.event]
            implies mayAct[Who.session, Now.event, Now.issue])
  always (some Target.agent.peer and some planeOf[Now.event]
            implies mayAct[Target.agent.peer, Now.event, Now.issue])
}

/* The commit half of the same gate: scripts/check-commit-claim.py, a
   pre-commit hook refusing a commit on a base tree or under a campaign
   directory whose branch is not a claim. Keyed on `a.peer` for the same
   reason as `claimBeforeWork`: a delegate's launch was gated already. */
pred claimBeforeCommit {
  always (Now.event = CommitLocal and some Target.agent.peer
            implies Now.issue in Target.agent.peer.claimedIssues)
}

/* Where session/checks.als's R3 is answered: keyed on LIVENESS, which is
   what `herdr agent list` hands a deleting session directly, and not on a
   record, which would die with the very tree it is about to delete. */
pred noDeleteUnderLiveAgent {
  always (Now.event = DeleteDir implies
            no a: Agent | a in Live and a.host = Where.machine
                          and campaignOf[a.task] in (OnDisk - OnDisk').campaign)
}

/* Empty for a sub-issue a session did with its own hands, which is what makes
   `mergedOnCurrentReview`'s second conjunct vacuous there -- see A18/A18b. A
   planner atom on the issue is in it: `confirm` needs only `a not in
   LocalOnly`, which a planner always satisfies, so the discipline is reachable
   unweakened over the planner too. */
fun agentsOf[i: Issue]: set Agent { task.i }

/* A MERGE REQUIRES A CURRENT REVIEW, and the author may then merge as anyone
   else may: an identity rule would make the one-session landing unreachable
   and call it safety. CURRENT is encoded as `Reviewed` cleared by `push`,
   which pins the revision THE REVIEW WAS READ AT rather than the merged
   commit, so a squash merge of a reviewed head stays reviewed. The second
   conjunct is UNIVERSAL, not existential, and vacuous with no Agent. */
pred mergedOnCurrentReview {
  always (Now.event = MergePullRequest implies
            (Now.issue.pullRequest in Reviewed
             and (all a: agentsOf[Now.issue] | a in Confirmed)))
}

/* WHO MERGES: the planner of the campaign whose claim the pull request's
   head is, or the worker session holding that claim (rule-check#442). The
   three merge conditions still name no role; this is the other question,
   WHICH session, and scripts/check-campaign-claim.py reads it off the branch
   a `gh pr merge` names. `Now.issue in Claimed` is the head being a claim at
   all, so a head that is no claim is no session's to merge -- the owner's own
   pull request included, which the owner merges. The planner half is keyed
   on the campaign and not on who cut the claim, because a planner merges the
   pull request of a claim a worker took itself, and it is membership and not
   `campaignOf[Now.issue] = Who.session.worksOn`, which holds when both sides
   are empty: a planner of no campaign (M7). Before it, the guard took
   any claim it found as the licence: 29 of 56 planner merges in the guard
   logs were licensed by a claim that was not the pull request's own. */
pred mergedByPlannerOrHolder {
  always (Now.event = MergePullRequest implies
            (Now.issue in Claimed
             and ((Who.session.role = Planner and Now.issue in Who.session.worksOn.memberIssues)
                  or (Who.session.role = Worker and Now.issue in Who.session.claimedIssues))))
}

/* ---------------- discipline: an escalation answered in its turn ---------------- */

/* Live agents waiting on a BLOCKED whose sub-issue has a planner running. */
fun waitingOnPlanner: set Agent { { a: Waiting & Live | some livePlannersOn[a.task] } }

/* planner.md step 7: in the turn a BLOCKED reaches the planner, its first act
   is the DECISION -- its own, or the owner's answer to AskUserQuestion -- and
   nothing else runs first. "Reaches" covers a planner starting with one
   already standing, so it is read off the state and not off `Blocked`.
   WHAT IT COSTS: it holds back every event while a worker waits, not the
   planner's alone, so a death or a limit stop during the wait is excluded
   rather than examined. So is the one trace the review found where the
   planner cannot answer: a `RemoveMember` unlinking the sub-issue while its
   worker waits, which leaves `decide` with no taker. */
pred answerInTurn {
  always (some waitingOnPlanner implies (Now.event = Decide and Target.agent in waitingOnPlanner))
}

/* That the discipline is enough: no worker waits forever on a live planner. */
assert WaitingWorkerIsAnswered {
  answerInTurn implies
    (all a: Agent | always (a in waitingOnPlanner implies eventually a not in Waiting))
}

/* The escalation round runs under the discipline: a worker's BLOCKED, then
   the planner's DECISION. The owner's branch is this same trace, since their
   answer is the planner's DECISION. */
pred EscalationAnsweredInTurn {
  answerInTurn
  eventually (Now.event = Blocked and Target.agent.role = Worker
              and some livePlannersOn[Target.agent.task] and after Now.event = Decide)
}

/* Restates the planner guards on `blocked` and `decide`, so deleting either
   is loud: without the first a worker waits with nobody who could answer,
   without the second a worker's own session answers its own BLOCKED. */
assert EscalationGoesThroughAPlanner {
  always (Now.event = Blocked implies some livePlannersOn[Target.agent.task])
  always (Now.event = Decide implies Who.session in livePlannersOn[Target.agent.task].peer)
}

/* ---------------- witnesses ---------------- */

/* SAT means the disciplines forbid a counterexample rather than the protocol. */
pred Sanity {
  twoStepShutdown
  and eventually (some a: Agent | a in Retired)
  and eventually Now.event = Work
  and eventually Now.event = Push
}

/* A worker waits for as long as its planner does not answer; `answerInTurn`
   rules that out (WaitingWorkerIsAnswered). */
pred BlockedAgentDoesNotProceed {
  some a: Agent | a.role = Worker
    and eventually (a in Waiting and always (a in Waiting and Now.event != Work))
}

/* The repair is a repair and not a prohibition. */
pred SilentAgentStillRetired {
  resolveSilenceExternally
  and (some a: Agent | eventually a in Retired and always a not in Answered)
}

/* THE POLL INTO THE BANNER. A stopped agent is listed and idle, so a
   STATUS sent to it queues like any other -- and no answer can follow until
   the window resets, because `answer` guards on Stopped and only `limitReset`
   clears it. The first is the planner's cron firing into the banner; the
   second is the one prompt that lands, sent after the reset the banner names. */
pred L1_PollIntoTheBannerGetsNoAnswer {
  some a: Agent | eventually (limitStop[a] and after (status[a] and after answer[a]))
}
pred L1b_PromptAfterTheResetIsAnswered {
  some a: Agent | eventually (limitStop[a]
                   and eventually (limitReset and after (status[a] and after answer[a])))
}

/* THE HEARTBEAT RETIRES A DONE WORKER. A worker whose
   sub-issue was released, by any session, and which holds nothing is sent
   `/exit`; one holding a claim or a live agent, one with no sub-issue
   released, and a planner are not. The first is reachable; the second is
   UNSAT, and dropping any one of the four guards on `s` -- its role, its
   claims, a released sub-issue, its live agents -- makes it SAT
   (`no Target.agent` is a frame, and dropping it leaves this UNSAT). */
pred H1_HeartbeatRetiresADoneWorker {
  some s: Session | eventually (Now.event = Release and Who.session = s
                     and eventually (Now.event = SessionExit and Who.session = s))
}
pred H1b_HeartbeatRetiresNoHolder {
  some s: Session | eventually (Now.event = SessionExit and Who.session = s
    and (some s.claimedIssues or some heldBy[s] or s.role = Planner
         or no a: peer.s | once (Now.event = Release and Now.issue = a.task)))
}

/* THE WATCH READS A LEVEL. An open sub-issue nobody claimed is an
   `unclaimed` drift until a claim, and a claim on a closed sub-issue is a
   `settled` drift until its release; each stands on every state between, so
   the watch reprints what still stands rather than catching one edge. W1's
   `i not in Backlog` keeps the label from clearing the drift in the claim's
   place: `Backlog` is unconstrained, so without it W1 stays SAT with a claim
   that records nothing. */
pred W1_UnclaimedDriftClearsOnClaim {
  some c: Campaign, i: Issue | eventually (i in unclaimedDrift[c]
    and eventually (Now.event = Claim and Now.issue = i
                    and after (i not in unclaimedDrift[c] and i not in Backlog)))
}
pred W1b_SettledDriftClearsOnRelease {
  some c: Campaign, i: Issue | eventually (Now.event = CloseIssue and Now.issue = i
    and i in c.memberIssues & Claimed
    and after (i in settledDrift[c]
               and eventually (Now.event = Release and Now.issue = i
                               and after i not in settledDrift[c])))
}

/* Completion is a GitHub fact, so it survives the death and never undoes. */
pred S3_DelegateDiesAfterPushing {
  one c: Campaign | one a: Agent {
    a.task in c.memberIssues
    always Now.event not in AddMember + RemoveMember
    mergeClosed[c.memberIssues]
    eventually (Now.event = OpenPullRequest and Now.issue = a.task)
    eventually (Now.event = AgentDie and some a.task.pullRequest and a.task.pullRequest not in Merged)
    eventually complete[a.task]
    always (complete[a.task] implies always complete[a.task])
  }
}

/* The claim never becomes a GitHub fact on its own. */
pred S4_ReportWithoutPush {
  one c: Campaign | one a: Agent {
    a.task in c.memberIssues
    always Now.event not in AddMember + RemoveMember
    eventually (Now.event = Report and Now.issue = a.task)
    eventually (a in Reported and no a.task.pullRequest and a.task in Open)
    eventually always (not complete[a.task])
    always not closable[c]
  }
}

/* =================== a close during another session's work =================== */

/* =================== two sessions, one repository =================== */

/* R4c. Pinned to one step, so the switch is attributable to s2 and not to an
   earlier acquire by the launching session itself. */
pred R4c_CheckoutSwitchedUnderAgent {
  some c: Campaign, disj s1, s2: Session, a: Agent, r: Repo {
    r != Base
    s1.machine = s2.machine
    a.launcher = s1 and a.host = s1.machine and a.task.repo = r
    eventually (Now.event = Acquire and Who.session = s2 and Where.repo = r
                and a in Live and a not in PushedToRemote
                and campaignDirAt[c, a.host].checkedOut[r] = a.branch
                and after (campaignDirAt[c, a.host].checkedOut[r] != a.branch))
  }
}

/* R4e. The issue number separates two sub-issues and there is only ever one of
   it per sub-issue, so two sessions on the SAME sub-issue still share a branch.
   R4g, which holds it, is its witness. */
pred R4e_NumberedBranchStillShared {
  some disj a1, a2: Agent {
    a1.launcher != a2.launcher
    eventually (a1 in Live and a2 in Live
                and some campaignOf[a1.task] and sameBranch[a1, a2])
  }
}

/* R4f. The second session's claim fails before a second agent exists. */
pred R4f_ClaimClosesSameSubIssue {
  claimBeforeLaunch and claimAtomic
  R4e_NumberedBranchStillShared
}

/* R4g. CONTROL: the ritual without the refusal. */
pred R4g_ClaimWithoutAtomicityStillShared {
  claimBeforeLaunch
  some disj s1, s2: Session, i: Issue |
    eventually (i in s1.claimedIssues and i in s2.claimedIssues)
  R4e_NumberedBranchStillShared
}

/* A SETTLED SUB-ISSUE'S REF IS RESIDUE, NOT A CLAIM. `closeIssue` leaves
   `Claimed` alone, so a sub-issue stays claimed for ever after it is settled --
   and on GitHub the same thing is literally true, because
   `delete_branch_on_merge` is off on this tracker and a merged branch's ref
   stands until someone deletes it by hand.
   A sub-issue that has been settled can therefore never be re-worked, which is
   not a policy anyone chose.

   The claim ends where the work does. This is the same reading `release`
   already makes on the merged path -- a branch whose pull request merged is
   finished work and not a fresh claim -- stated once, here, so `take` and
   `release` cannot drift about when a ref stops meaning "somebody holds this".

   SPELLED ON `Claim` AND NOT ON `CloseIssue`. Written as "a close leaves the
   issue unclaimed", and with `closeIssue` framing `Claimed' = Claimed`, it
   reduces to "no sub-issue may close while it is claimed" -- which FORBIDS THE
   ORDINARY LANDING the code makes every time: the pull request merges, GitHub
   auto-closes the sub-issue with its ref still standing, and `release` deletes
   the ref afterwards.

   What the code actually reads is on the TAKE side: a second claim on an
   already-claimed sub-issue is admitted exactly when the first is residue of a
   merged pull request. That is `partition_refs`, and it is what makes
   reopen-then-take work.

   `some ... .pullRequest` IS LOAD-BEARING. `none in Merged`
   holds vacuously in Alloy, so without it the rule also admits a second claim
   on a sub-issue with NO pull request at all -- which `partition_refs` refuses,
   since a ref with no merged pull request is a live claim. R9e is the control
   for that branch; without the conjunct it goes SAT. */
pred settledLeavesNoClaim {
  always (Now.event = Claim and Now.issue in Claimed
            implies (some Now.issue.pullRequest
                     and Now.issue.pullRequest in Merged))
}

/* R8. THE DEFECT, in the smallest world that holds it: one
   sub-issue, and a claim cut on a repository that is not the one its work
   lands in. `claimAtomic` is asserted here, so this is NOT the same defect as
   R4g -- the one-claim-per-issue rule holds throughout and the wrong ref is cut
   anyway, which is the whole point: a discipline keyed on the issue cannot see
   a disagreement about where the issue lives. */
pred R8_ClaimCutOnAnotherRepo {
  claimAtomic
  some i: Issue | eventually (Now.event = Claim and Now.issue = i
                              and Now.repo != i.repo)
}

/* R8b. CONTROL: the same trace with the repair, which must be empty. If this
   ever comes back SAT, `claimOnTheIssuesRepo` has stopped constraining
   anything. */
pred R8b_RepairExcludesIt {
  claimOnTheIssuesRepo
  R8_ClaimCutOnAnotherRepo
}

/* R14. THE SCOPE DEFECT, without the rule: a sub-issue lands in a member
   repository the campaign issue's `## Repos` never listed, and its ref is cut
   anyway. `claimOnTheIssuesRepo` is asserted, so this is not R8 -- the taker
   and the sub-issue agree about the destination, and the destination is one
   the campaign was never for. */
pred R14_ClaimOnARepoOutsideTheScope {
  claimAtomic and claimOnTheIssuesRepo
  some c: Campaign, i: Issue |
    eventually (Now.event = Claim and Now.issue = i and i in c.memberIssues
                and i.repo != Base and i.repo not in c.reposInBody)
}

/* R14b. CONTROL: the repair excludes it. */
pred R14b_RepairExcludesIt {
  claimWithinScope
  R14_ClaimOnARepoOutsideTheScope
}

/* R14c. ...and it still admits the ordinary claim on a listed member, or the
   rule refuses the only thing a member repository is for. It holds
   `claimOnTheIssuesRepo` too, so it is R8b's control as well: that repair
   does not forbid every claim. */
pred R14c_ScopeAdmitsTheListedMember {
  claimWithinScope and claimAtomic and claimOnTheIssuesRepo
  some c: Campaign, i: Issue |
    eventually (Now.event = Claim and Now.issue = i and i in c.memberIssues
                and i.repo != Base and i.repo in c.reposInBody)
}

/* R14d. The campaign has a member repository,
   so `## Repos` is NOT empty -- which is what separates this from
   `R4_RepolessCampaign`, whose list is empty and which therefore passes a
   reader that admits the base only by way of `none`. The sub-issue lands in
   the base, the list does not hold the base, and the claim must still be cut.
   Expects 1 WITH the rule asserted: dropping the `Base` disjunct from
   `claimWithinScope` makes it UNSAT. */
/* R14e. WHOSE list, pinned. Every command above runs at `1 Campaign`, where
   `campaignOf[Now.issue].reposInBody` and `Campaign.reposInBody` are the same
   relation and the choice between them is free -- so the four of them together
   say nothing about which campaign's scope a claim is judged against. Two
   campaigns, and the sub-issue's OWN parent does not list its repository while
   the other campaign does. Replacing `campaignOf[Now.issue]` with `Campaign`
   in `claimWithinScope` makes this SAT and moves no other verdict, which is
   the only thing that tells the two readings apart. */
pred R14e_TheParentsListIsTheOneThatCounts {
  claimWithinScope and claimAtomic and claimOnTheIssuesRepo
  some c, other: Campaign, i: Issue |
    c != other and
    eventually (Now.event = Claim and Now.issue = i and i in c.memberIssues
                and i.repo != Base
                and i.repo not in c.reposInBody
                and i.repo in other.reposInBody)
}

pred R14d_ScopeAdmitsTheBaseWhateverTheListHolds {
  claimWithinScope and claimAtomic and claimOnTheIssuesRepo
  some c: Campaign, i: Issue, r: Repo |
    eventually (Now.event = Claim and Now.issue = i and i in c.memberIssues
                and i.repo = Base
                and r != Base and r in c.reposInBody
                and Base not in c.reposInBody)
}

/* R9. A settled sub-issue whose claim outlives it. `claimAtomic` is asserted,
   so this is not the atomicity hole either: the sub-issue is closed, nobody is
   working it, and its claim stands anyway. */
pred R9_SettledSubIssueStaysClaimed {
  some i: Issue | eventually (Now.event = Claim and Now.issue = i
                              and i in Claimed
                              and i.pullRequest not in Merged)
}

/* R9b. CONTROL: the repair excludes it. */
pred R9b_RepairExcludesIt {
  settledLeavesNoClaim
  R9_SettledSubIssueStaysClaimed
}

/* R9c. ...and the repair still admits a sub-issue being claimed and then
   settled, which is the ordinary life of every one of them. A rule that made
   the close unreachable would satisfy R9b just as well. */
pred R9c_RepairAdmitsClaimThenSettle {
  settledLeavesNoClaim
  some i: Issue | eventually (Now.event = Claim and Now.issue = i
                              and i in Claimed
                              and i.pullRequest in Merged)
}

/* R7e. CONTROL FOR THE `settled` DISJUNCT: a sub-issue DROPPED
   as not planned, whose claim nobody was ever launched on, must be releasable.
   GitHub already answers it: an issue closed as not planned says
   the work is over as plainly as a merged pull request does. Deleting
   `settled` from the rule -- or narrowing it back to `complete` -- turns this
   UNSAT, which is what makes the widening tested rather than merely made. */
pred R7e_WorkerRuleAdmitsTheDroppedSubIssue {
  releaseNeedsAWorker
  some i: Issue {
    always no a: Agent | a.task = i and a in Launched
    always not complete[i]                 -- dropped, never landed
    eventually (dropped[i] and Now.event = Release and Now.issue = i)
  }
}

/* R11. A HOLDER ATTRIBUTED THROUGH ANOTHER CAMPAIGN'S DIRECTORY. `holder`
   reaches a checkout through `campaignDirAt[campaignOf[i],
   host]`, and directory/system.als says that is the one way to reach a
   campaign's directory -- so a sub-issue's holder must stand in ITS OWN
   campaign's directory, never in a neighbour's on the same machine.

   Expect 0, and it goes SAT the moment `campaignDirAt` stops filtering by
   campaign. */
pred R11_HolderThroughAnotherCampaignsDir {
  some a: Agent, c: Campaign {
    c != campaignOf[a.task]
    eventually (a in holder[a.task]
                and no campaignDirAt[campaignOf[a.task], a.host].checkedOut
                and some campaignDirAt[c, a.host].checkedOut)
  }
}

/* WORK HAPPENS IN A CLONE `acquire-repo.sh` SET UP.
   Two readings of one set, `acquired` in directory/system.als. A delegate is
   launched into such a clone, because the clone it starts in is where it
   commits; and a commit on campaign work is made in one, because that is
   where the claim gate runs -- a member repository ships no installer.
   The commit's failure is not observable: an ungated commit looks like a
   gated one that passed.

   Delegates only for the launch: a session launching an in-process subagent,
   or working by its own hands, starts no process in a clone, and its commits
   are the commit half's.

   THE COMMIT HALF IS NARROWED TO A TASK THAT HAS A CAMPAIGN. Without it the
   rule forbids a commit whose task belongs to no campaign -- `campaignOf` is
   `lone` and `x in none` is false -- by vacuity rather than by anything it
   claims. The script reads the committing checkout's PATH, which this entity
   does not carry, so "no campaign" and "outside every base tree" are two
   readings the model cannot show coincide; R12h is this narrowing's witness.

   `workDir` is the one navigation both halves take; R12g pins its campaign
   filter, and R12e and R12i its host filter for each half.
   Those two spell the navigation out rather than call `workDir`: a witness
   reading the rule's own helper moves with any change to it and pins
   nothing. */
fun workDir[a: Agent]: lone CampaignDir { campaignDirAt[campaignOf[a.task], a.host] }

pred acquiredCloneOnly {
  always all a: Agent {
    (a not in Launched and a in Launched' and no a.peer)
      implies a.task.repo in workDir[a].acquired'
    (Now.event = CommitLocal and Target.agent = a and some campaignOf[a.task])
      implies a.task.repo in workDir[a].acquired
  }
}

/* A delegate launched, or a campaign commit made, outside an acquired clone. */
pred launchOutside[a: Agent] {
  no a.peer and a not in Launched and a in Launched' and a.task.repo not in workDir[a].acquired'
}
pred commitOutside[a: Agent] {
  Now.event = CommitLocal and Target.agent = a and some campaignOf[a.task]
  and a.task.repo not in workDir[a].acquired
}

/* R12. THE DEFECT, without the rule: a delegate launched into a clone carrying
   nothing, or a commit on campaign work in a clone that runs nothing.
   `claimBeforeCommit` holds throughout, so a reader can see what this is not:
   the claim rule holding over a tree that enforces it on nobody. */
pred R12_WorkOutsideAnAcquiredClone {
  claimBeforeCommit
  some a: Agent | eventually (launchOutside[a] or commitOutside[a])
}

/* R12b. CONTROL: the rule excludes both, so deleting either half turns it SAT. */
pred R12b_RepairExcludesIt {
  acquiredCloneOnly and R12_WorkOutsideAnAcquiredClone
}

/* R12c. ...and it still admits a launch and a commit in an acquired clone, or
   it would be a rule that forbids delegates, or committing, outright. */
pred R12c_RepairAdmitsTheAcquiredLaunchAndCommit {
  acquiredCloneOnly
  some a: Agent {
    no a.peer
    eventually (a not in Launched and a in Launched' and a.task.repo in workDir[a].acquired')
  }
  some a: Agent | eventually (Now.event = CommitLocal and Target.agent = a
                              and some campaignOf[a.task] and a.task.repo in workDir[a].acquired)
}

/* R12d. ACQUIRE IS WHAT SETS A CLONE UP, pinned. R12c is satisfied by an
   `acquired` that was simply true at time zero, so on its own it says nothing
   about where the set comes from. Starting from nothing acquired, a launch
   into an acquired clone is reachable only through an Acquire, so this goes
   UNSAT the moment `acquire` stops producing. */
pred R12d_AcquireIsWhatSetsACloneUp {
  no acquired
  some a: Agent {
    no a.peer
    eventually (a not in Launched and a in Launched' and a.task.repo in workDir[a].acquired')
  }
}

/* R12e. WHICH HOST, pinned. `campaignDirAt[c, m]` filters on two columns, and
   at `1 Machine` `workDir[a]` and `campaignDirsOf[campaignOf[a.task]]`
   are the same relation; one campaign directory per machine is exactly the
   shape that has two. Two machines, one campaign: the directory on the
   agent's own host lacks the repository and the other machine's holds it, and
   the rule must still refuse. Expect 0, and it goes SAT the moment `a.host`
   stops filtering.

   `some campaignOf[a.task]` is not a conjunct: the last one implies it. An
   expect-0 witness pays for every redundant conjunct, which can make it UNSAT
   for a reason that is not the one under test. */
pred R12e_TheAgentsOwnHostIsTheOneThatCounts {
  acquiredCloneOnly
  some a: Agent, m: Machine {
    no a.peer
    eventually (a not in Launched and a in Launched'
                and m != a.host
                and a.task.repo not in campaignDirAt[campaignOf[a.task], a.host].acquired'
                and a.task.repo in campaignDirAt[campaignOf[a.task], m].acquired')
  }
}

/* R12f. AND NOTHING BUT AN ACQUIRE SETS A CLONE UP. R12d says an acquired
   launch is REACHABLE from `no acquired`, which any producer satisfies -- so it
   rests on `acquired' = acquired` holding in `directoryFrame`. From nothing
   acquired, with no Acquire ever firing, an acquired launch is IMPOSSIBLE.
   Expect 0, and it goes SAT the moment the frame stops carrying `acquired`.
   The rule is not assumed: what is under test is what the transition system
   can produce. */
pred R12f_NothingButAnAcquireSetsACloneUp {
  no acquired
  always Now.event != Acquire
  some a: Agent {
    no a.peer
    eventually (a not in Launched and a in Launched' and a.task.repo in workDir[a].acquired')
  }
}

/* R12g. WHOSE directory, pinned: R11's campaign filter
   inside `campaignDirAt` taken up by this rule. At `1 Campaign`
   `workDir[a].acquired` and `CampaignDir.acquired` are the same relation. Two
   campaigns on one machine: the agent's own campaign's clone is not acquired
   and a neighbour's clone of the same repository is, and the rule must still
   refuse. Expect 0, and it goes SAT the moment the navigation is replaced by
   `CampaignDir.acquired`.

   EVERY conjunct sits inside the `eventually`: `memberIssues` is a var
   relation, and stated outside it they are read at time zero, so a trace that
   moves the sub-issue out of its campaign before the commit satisfies the
   witness while the rule's antecedent is false. */
pred R12g_TheAgentsOwnDirIsTheOneThatCounts {
  acquiredCloneOnly
  some a: Agent, c: Campaign |
    eventually (Now.event = CommitLocal and Target.agent = a
                and some campaignOf[a.task]
                and c != campaignOf[a.task]
                and a.task.repo not in campaignDirAt[campaignOf[a.task], a.host].acquired
                and a.task.repo in campaignDirAt[c, a.host].acquired)
}

/* R12i. WHICH HOST, for the commit half: R12e's pin on a commit rather than a
   launch. Expect 0, and it goes SAT when the commit
   half reads any machine's directory -- through `workDir` or around it. */
pred R12i_TheCommitsOwnHostIsTheOneThatCounts {
  acquiredCloneOnly
  some a: Agent, m: Machine |
    eventually (Now.event = CommitLocal and Target.agent = a
                and some campaignOf[a.task]
                and m != a.host
                and a.task.repo not in campaignDirAt[campaignOf[a.task], a.host].acquired
                and a.task.repo in campaignDirAt[campaignOf[a.task], m].acquired)
}

/* R12h. THE CASE THE COMMIT HALF DOES NOT COVER, stated rather than left to
   the reader of the conjunct: an agent committing on a task that belongs to
   no campaign is admitted with nothing acquired anywhere, as
   check-commit-claim.py admits a checkout outside every base tree, every
   campaign directory and every install a `## Repos` entry names. Expect 1, and it goes UNSAT if `some campaignOf[a.task]`
   is dropped from the rule. */
pred R12h_ACommitOnNoCampaignsWorkIsOutsideTheRule {
  acquiredCloneOnly
  no acquired
  some a: Agent | eventually (Now.event = CommitLocal and Target.agent = a
                              and no campaignOf[a.task])
}

/* R9d. THE ORDINARY LANDING: claim, merge, and the sub-issue closes
   with its ref still standing, because GitHub auto-closes on merge and
   `release` runs afterwards. Spelled on CloseIssue, the rule makes this UNSAT --
   the spec forbidding what the code does every time. A discipline needs a
   witness for the path it must NOT block, not only for the one it must. */
pred R9d_OrdinaryLandingStillAllowed {
  settledLeavesNoClaim
  some i: Issue | eventually (Now.event = Claim and Now.issue = i
                              and eventually (Now.event = CloseIssue
                                              and Now.issue = i
                                              and i in Claimed))
}

/* R9e. A second claim on a sub-issue
   that is claimed and has NO pull request at all. `none in Merged` is vacuously
   true -- R9's witness asks
   for `pullRequest not in Merged`, which is FALSE of an empty pullRequest, so
   R9 and R9b never reach this shape. The code refuses it: a ref with no
   merged pull request is a live claim, and `partition_refs` puts it in `held`.
   Expect 0, and it goes SAT the moment the `some` conjunct is dropped. */
pred R9e_SecondClaimOnAPullRequestLessSubIssue {
  settledLeavesNoClaim
  some i: Issue | eventually (Now.event = Claim and Now.issue = i
                              and i in Claimed and no i.pullRequest)
}

/* R4h. THE HOLE: a session works
   its own sub-issue and no claim of it ever exists, so every peer reading the
   records sees an open sub-issue indistinguishable from one nobody started. */
pred R4h_OwnHandsWorkWithoutClaim {
  some s: Session, a: Agent {
    a.peer = s
    eventually (Now.event = Work and Target.agent = a)
    always a.task not in s.claimedIssues
  }
}

/* R4i. The guard closes it. Q5 is its control: `permissionByRole` implies
   this guard (PermissionImpliesClaimGates), and claimed work still runs under
   it, so the guard does not forbid working at all. */
pred R4i_GuardClosesOwnHandsGap {
  claimBeforeWork
  R4h_OwnHandsWorkWithoutClaim
}

/* R15. THE GUARD THAT JUDGED AND WROTE NOTHING. Work happens and no verdict
   about it is on disk afterwards. */
pred R15_WorkLeavesNoVerdict {
  some i: Issue | eventually (Now.event = Work and Now.issue = i
                              and i not in Judged')
}

/* R15b. CONTROL: the rule excludes it. */
pred R15b_DurableExcludesIt {
  verdictIsDurable
  R15_WorkLeavesNoVerdict
}

/* R15c. ...and it still admits the work, or "log every verdict" would be
   satisfied by never working. The pairing R15b alone cannot make: an UNSAT
   there is the same shape whether the rule bounded the trace or emptied it. */
pred R15c_DurableStillAdmitsTheWork {
  verdictIsDurable
  some i: Issue | eventually (Now.event = Work and Now.issue = i
                              and i in Judged')
}

/* ============== permission by role, one witness per table cell ============== */

/* Q11. A worker writes its OWN campaign's issue, which is no
   sub-issue and which no claim can cover. SAT -- and it is the campaign issue
   that makes it so and not a claim: removing the disjunct from `mayAct` makes
   this command UNSAT against its `expect 1`, which is the whole of what it
   measures. WHICH campaign's issue is held elsewhere -- see `mayAct`. */
pred Q11_WorkerWritesItsOwnCampaignIssue {
  permissionByRole
  some s: Session | s.role = Worker and
    eventually (Now.event = CloseIssue and Who.session = s
                and Now.issue = s.worksOn.campaignIssue)
}

/* Q10. A planner cuts a claim for a delegate on a sub-issue of ANOTHER campaign
   held on the same machine (`machinesHolding`). SAT: the relaxation in
   `sessionClaim`.

   `c != s.worksOn` sits INSIDE the `eventually` in all three: `worksOn` is var,
   so a session that differs from `c` at time zero can adopt `c` before it
   claims, and the three would measure nothing. */
pred Q10_PlannerClaimsOnAnotherBoundCampaign {
  permissionByRole
  some s: Session, c: Campaign |
    s.role = Planner
    and eventually (Now.event = Claim and Who.session = s
                    and c != s.worksOn and Now.issue in c.memberIssues)
}

/* Q10b. The same claim by a worker. UNSAT, and TWO rules refuse it --
   `sessionClaim`'s pin and `mayAct`'s campaign-plane row. Q10c separates
   them. */
pred Q10b_WorkerClaimsOnAnotherBoundCampaign {
  permissionByRole
  some s: Session, c: Campaign |
    s.role = Worker
    and eventually (Now.event = Claim and Who.session = s
                    and c != s.worksOn and Now.issue in c.memberIssues)
}

/* Q10c. Q10b with the discipline dropped, and still UNSAT: `sessionClaim`
   alone holds the worker to its own campaign, so the relaxation was made for
   planners only and nothing else moved. */
pred Q10c_WorkerClaimsOnAnotherBoundCampaignUnguarded {
  some s: Session, c: Campaign |
    s.role = Worker
    and eventually (Now.event = Claim and Who.session = s
                    and c != s.worksOn and Now.issue in c.memberIssues)
}

/* Q1. A planner closes an issue no
   campaign of its own covers. */
pred Q1_PlannerClosesOtherCampaignsIssue {
  permissionByRole
  some s: Session | s.role = Planner and
    eventually (Now.event = CloseIssue and Who.session = s
                and some Now.issue and Now.issue not in s.worksOn.memberIssues)
}

/* Q2. A planner never commits. UNSAT. */
pred Q2_PlannerCommits {
  permissionByRole
  some s: Session | s.role = Planner and
    eventually (Now.event = Work and Target.agent.peer = s)
}

/* Q2c. CONTROL, and the point of running it: this is Q2 with the discipline
   DROPPED, and it is UNSAT too. So it is AgentInheritsSessionRole, not
   `permissionByRole`, that forbids a planner from working -- the discipline
   would forbid it as well, and the fact gets there first. Deleting that fact
   from AgentWellFormed is the mutation that reddens this one. */
pred Q2c_PlannerCommitsUnguarded {
  some s: Session | s.role = Planner and
    eventually (Now.event = Work and Target.agent.peer = s)
}

/* Q3. A worker closes the sub-issue it holds. */
pred Q3_WorkerClosesOwnClaim {
  permissionByRole
  some s: Session | s.role = Worker and
    eventually (Now.event = Claim and Who.session = s
                and eventually (Now.event = CloseIssue and Who.session = s
                                and Now.issue in s.claimedIssues))
}

/* Q4. A worker of one campaign closes ANOTHER campaign's issue. UNSAT.

   Says "belongs to campaign c, and c is not the session's" rather than "not in
   my memberIssues": the campaign issue of
   the session's OWN campaign is also outside `memberIssues`, so that
   spelling would match the one write the rule permits.

   `c != s.worksOn` sits INSIDE the `eventually`, as in Q10's trio: `worksOn`
   is var, so a session that differs from `c` at time zero can adopt `c` and
   then close its issue legitimately, and the command measures nothing. Several
   commands in this file need that placement; this comment is the one home for
   why, rather than a sentence repeated at each. */
pred Q4_WorkerClosesOtherCampaign {
  permissionByRole
  some s: Session, c: Campaign |
    s.role = Worker
    and eventually (Now.event = CloseIssue and Who.session = s
                    and c != s.worksOn
                    and Now.issue in c.memberIssues + c.campaignIssue)
}

/* Q14. A worker releases a claim ANOTHER session holds, on another campaign's
   issue: one that started as a sub-issue of the worker's campaign, was
   claimed there, and left it. The worker holds no claim on it, so only the
   carve-out could admit the write. UNSAT, and the command that pins the carve-out's
   `i = s.worksOn.campaignIssue`: widened to `i in Campaign.campaignIssue` it
   goes SAT. Q14c is the same trace with the rule dropped, SAT, so the UNSAT
   is the rule's and not the model's. */
pred releaseOfAnotherCampaignsIssue {
  Filed = Campaign
  some disj s, t: Session | s.role = Worker and some s.worksOn and
    eventually (Now.event = Release and Who.session = s
                and Now.issue in Campaign.campaignIssue - s.worksOn.campaignIssue
                and Now.issue in t.claimedIssues and Now.issue not in s.claimedIssues)
}
pred Q14_WorkerReleasesAnotherCampaignsIssue { permissionByRole and releaseOfAnotherCampaignsIssue }
pred Q14c_WorkerReleasesAnotherCampaignsIssueUnguarded { releaseOfAnotherCampaignsIssue }

/* Q4b. Its own campaign, a sibling sub-issue it never claimed. UNSAT, and the
   one that separates the two halves of the worker's campaign-plane row. */
pred Q4b_WorkerClosesUnclaimedSibling {
  permissionByRole
  some s: Session | s.role = Worker and
    eventually (Now.event = CloseIssue and Who.session = s
                and Now.issue in s.worksOn.memberIssues
                and Now.issue not in s.claimedIssues)
}

/* Q5. Claimed work still runs under the discipline. R4h under it needs no run
   of its own: `permissionByRole` implies `claimBeforeWork`, which R4i shows
   closes R4h. */
pred Q5_WorkerWorksClaimedCheckout {
  permissionByRole
  some s: Session, a: Agent {
    s.role = Worker and a.peer = s
    eventually (Now.event = Claim and Who.session = s and Now.issue = a.task
                and eventually (Now.event = Work and Target.agent = a))
  }
}

/* Q7. The table's last row: a session with no name, or a name of another shape,
   is refused on the campaign plane. UNSAT. */
pred Q7_UnnamedSessionRefused {
  permissionByRole
  some s: Session | no s.role and
    eventually (Now.event = CloseIssue and Who.session = s)
}

/* Q7c. CONTROL for Q7, and unlike Q2c it is SAT: without the discipline an
   unnamed session reaches the same close, so the refusal is the rule's and not
   the trace space's. */
pred Q7c_UnnamedSessionReachesTheEventUnguarded {
  some s: Session | no s.role and
    eventually (Now.event = CloseIssue and Who.session = s)
}

/* Q8. A worker writing the campaign issue body. UNSAT, and it is
   `plannerOnlyEvents` that refuses it: `writeBody` names no issue, so the
   worker's issue test is vacuous here and would let it through. Dropping
   `WriteBody` from `plannerOnlyEvents` reddens this one. */
pred Q8_WorkerWritesCampaignBody {
  permissionByRole
  some s: Session | s.role = Worker and
    eventually (Now.event = WriteBody and Who.session = s)
}

/* Q8c. CONTROL for Q8: SAT without the discipline. */
pred Q8c_WorkerWritesCampaignBodyUnguarded {
  some s: Session | s.role = Worker and eventually (Now.event = WriteBody and Who.session = s)
}

/* Q8b. The positive side of the same cell: a planner writes it. */
pred Q8b_PlannerWritesCampaignBody {
  permissionByRole
  some s: Session | s.role = Planner and
    eventually (Now.event = WriteBody and Who.session = s)
}

/* Q9. A worker filing a campaign issue -- opening a campaign. UNSAT.
   `FileCampaignIssue` names the campaign issue, which is in no campaign's
   `memberIssues`, so the issue test refuses it as well; both readings are
   wanted, and dropping `FileCampaignIssue` from `plannerOnlyEvents` leaves this
   one green, which is why Q8 and not this one is that fun's witness. */
pred Q9_WorkerFilesCampaignIssue {
  permissionByRole
  some s: Session | s.role = Worker and
    eventually (Now.event = FileCampaignIssue and Who.session = s)
}

/* Q9c. CONTROL for Q9. */
pred Q9c_WorkerFilesCampaignIssueUnguarded {
  some s: Session | s.role = Worker and
    eventually (Now.event = FileCampaignIssue and Who.session = s)
}

/* Q12. A session acting from a context it was never re-briefed in. UNSAT: the
   `s in Briefed` conjunct is the only thing that refuses it, and dropping that
   line reddens this one alone. */
pred Q12_UnbriefedSessionRefused {
  permissionByRole
  some s: Session |
    eventually (Now.event = ContextReset and Who.session = s)
    and eventually (Who.session = s and some planeOf[Now.event] and s not in Briefed)
}

/* Q12c. CONTROL for Q12, and SAT: without the discipline the same session
   reaches the same write after the same reset, so the refusal is the rule's
   and not the trace space's. */
pred Q12c_UnbriefedSessionReachesTheEventUnguarded {
  some s: Session |
    eventually (Now.event = ContextReset and Who.session = s)
    and eventually (Who.session = s and some planeOf[Now.event] and s not in Briefed)
}

/* Q12b. The positive side of the same cell, with the order pinned: the reset,
   then the hook's brief, then the write. SAT, which is what says the bit is a
   pause and not a wall -- a session compacted mid-sub-issue goes on working. */
pred Q12b_RebriefedSessionActs {
  permissionByRole
  some s: Session |
    eventually (Now.event = ContextReset and Who.session = s
                and after eventually (Now.event = Brief and Who.session = s
                                      and after eventually (Now.event = CloseIssue
                                                            and Who.session = s)))
}

/* Q13. A session acting while its pane record has lost its id. UNSAT: the
   `s in Stamped` conjunct is the only thing in the model that refuses it, and
   dropping that line reddens this one alone. No guard refuses it -- see
   `mayAct` -- so this is the hook's discipline, not a refusal. */
pred Q13_UnstampedSessionRefused {
  permissionByRole
  some s: Session |
    eventually (Now.event = Unstamp and Who.session = s)
    and eventually (Who.session = s and some planeOf[Now.event] and s not in Stamped)
}

/* Q13c. CONTROL for Q13, and SAT: without the discipline the same session
   reaches the same write after the same loss. */
pred Q13c_UnstampedSessionReachesTheEventUnguarded {
  some s: Session |
    eventually (Now.event = Unstamp and Who.session = s)
    and eventually (Who.session = s and some planeOf[Now.event] and s not in Stamped)
}

/* Q13b. The positive side, with the order pinned: the loss, then the hook's
   re-stamp, then the write. SAT, which is what says the UserPromptSubmit
   re-assert is a repair and not a formality. */
pred Q13b_RestampedSessionActs {
  permissionByRole
  some s: Session |
    eventually (Now.event = Unstamp and Who.session = s
                and after eventually (Now.event = Stamp and Who.session = s
                                      and after eventually (Now.event = CloseIssue
                                                            and Who.session = s)))
}

/* R4k. THE HOLE THE PRE-TOOL-USE HALF LEAVES OPEN, stated rather than hidden:
   under `claimBeforeWork` alone a session with no claim still reaches a
   commit, because a shell write is not read as `Work` at the moment it is
   made. Reachable on purpose -- this is the accepted cost of reading only
   bounded languages. */
pred R4k_UnclaimedShellWriteThenCommit {
  claimBeforeWork
  some s: Session, a: Agent {
    a.peer = s
    eventually (Now.event = CommitLocal and Target.agent = a)
    always a.task not in s.claimedIssues
  }
}

/* R4l. The commit gate closes it. */
pred R4l_CommitGateClosesIt {
  claimBeforeCommit
  R4k_UnclaimedShellWriteThenCommit
}

/* R4m. CONTROL for R4l: UNSAT there would mean the gate forbids committing at
   all rather than committing unclaimed. */
pred R4m_GateAdmitsClaimedCommit {
  claimBeforeCommit
  some s: Session, a: Agent {
    a.peer = s
    eventually (Now.event = Claim and Who.session = s and Now.issue = a.task
                and eventually (Now.event = CommitLocal and Target.agent = a))
  }
}

/* =================== retiring another session's delegate =================== */

/* R5c. Ownership is not the axis: a session that did not launch the agent
   stands it down. */
pred R5c_NonLauncherSameMachineIsFine {
  some disj s1, s2: Session, a: Agent {
    a.launcher = s1 and a.host = s1.machine and s2.machine = a.host
    eventually (Now.event = StandDown and Who.session = s2 and Target.agent = a)
  }
}

/* R6b. A dangling claim does not outlive its usefulness. */
pred R6b_ReclaimAfterDeath {
  some disj s1, s2: Session, a: Agent {
    a.launcher = s1
    eventually (a in Launched and a not in Live and a not in PushedToRemote
                and eventually (Now.event = Release
                and eventually (Now.event = Claim and Who.session = s2 and Now.issue = a.task)))
  }
}

/* R7a. THE HOLE: a sub-issue is claimed, no agent is ever launched on it, and
   the claim is released -- which on the remote is the ref deleted, so a second
   `take` succeeds and two workers reach one sub-issue. */
pred R7a_FreshClaimReleasedWithNoAgent {
  some i: Issue {
    /* NEVER LAUNCHED, not "no atom exists". An `Agent` atom on the sub-issue
       that was never started IS the fresh claim -- the delegate the branch was
       cut for, before `agent start` -- so this is both the truer witness and
       the one that pins the rule's `in Launched`: written as "no atom", the
       weakened rule still forbade the trace and the disjunct went untested. */
    always no a: Agent | a.task = i and a in Launched
    /* NOT SETTLED, and this conjunct is what makes the witness the fresh
       claim rather than hands-on work. Without it the trace closes the
       sub-issue and merges its pull request first, which is a landing nobody
       needed an Agent atom for and is releasable on purpose -- so R7b came
       back SAT over a legitimate trace and pinned nothing.

       Since `releaseNeedsAWorker` admits a settled sub-issue, excluding only
       `complete` lets the solver satisfy this witness by DROPPING the issue
       instead of merging it -- the same escape through a different door, and
       R7b goes SAT. An exclusion has to name the whole disjunct it is
       excluding. */
    always not settled[i]
    eventually (Now.event = Claim and Now.issue = i
                and after eventually (Now.event = Release and Now.issue = i))
  }
}

/* R7b. The discipline closes it. */
pred R7b_WorkerRuleClosesTheFreshClaim {
  releaseNeedsAWorker and R7a_FreshClaimReleasedWithNoAgent
}

/* R7d. CONTROL FOR THE `complete` DISJUNCT: hands-on work is no Agent at all
   (A18's shape), so a landed sub-issue nobody was launched on must still be
   releasable -- otherwise the rule strands every branch a session worked with
   its own hands. Deleting `complete` from the rule turns this UNSAT. */
pred R7d_WorkerRuleAdmitsTheAgentLessLanding {
  releaseNeedsAWorker
  no Agent
  some i: Issue |
    eventually (complete[i] and Now.event = Release and Now.issue = i)
}

/* =================== whose session is that =================== */

/* N1. A session named for ANOTHER campaign, live on the machine that holds
   this one, does not block this campaign's close. Machine-wide alone made the
   peer set identical for every campaign here, so closing one asked another's
   sessions to stand down. */
pred N1_ForeignNamedSessionDoesNotBlock {
  some disj c1, c2: Campaign, s: Session, a: Agent, m: Machine {
    a.peer = s and a.host = m and s.machine = m
    always s.campaignNamed = c2
    /* BOTH INSIDE THE `eventually`, and that is what makes this pin the
       exemption. `machinesHolding` is derived from `OnDisk`, which is var, so a
       membership stated outside is read at time zero and the witness can
       satisfy `not liveUnderLocally` at an instant when the directory is simply
       not on disk -- a trace the exemption plays no part in. Deleting the
       exemption then left this green. */
    eventually (a in Live and m in machinesHolding[c1]
                and a.task not in c1.memberIssues
                and not liveUnderLocally[c1, m])
  }
}

/* N2. A SESSION WHOSE NAME SAYS NOTHING DOES NOT BLOCK, even under the base
   tree: the tree is under every campaign here at once, so it
   ties the session to all of them. N7 is the control that the gate is not
   emptied by it. Restoring the cwd disjunct in `liveUnderLocally` makes this
   UNSAT. */
pred N2_UnnamedSessionDoesNotBlock {
  some c: Campaign, s: Session, a: Agent, m: Machine {
    a.peer = s and a.host = m and s.machine = m
    always no s.campaignNamed
    /* UNDER THE TREE, which is the case the old rule counted; outside it was
       never counted. */
    s in UnderBase
    /* `a.task not in c.memberIssues` is load-bearing: an agent on a sub-issue
       of this campaign blocks whatever it is called, through the first
       disjunct, and that is not what is exempted here. */
    eventually (a in Live and m in machinesHolding[c]
                and a.task not in c.memberIssues
                and not liveUnderLocally[c, m])
  }
}

/* N3. CONTROL for N1: an agent on a sub-issue OF THIS CAMPAIGN blocks whatever
   its session is called. The name exempts the machine-wide disjunct and
   nothing else -- otherwise a misnamed worker could close over its own work. */
pred N3_ForeignNameDoesNotExemptOwnSubIssue {
  some disj c1, c2: Campaign, s: Session, a: Agent, m: Machine {
    a.peer = s and a.host = m and s.machine = m
    a.task in c1.memberIssues
    always s.campaignNamed = c2
    eventually (a in Live and liveUnderLocally[c1, m])
  }
}

/* =================== the refs a close leaves behind =================== */

/* github's `closable` reads `settled` and the person's hold, and nothing
   about the refs, so a campaign whose sub-issues are all closed is closable
   with claim refs still standing on the remote. Most are harmless -- a merged
   pull request's head outlives it here, `delete_branch_on_merge` being off --
   and the rest are a claim nobody retired, which the next `take` on that
   sub-issue then refuses forever. */
pred noStrayClaims[c: Campaign] {
  all i: c.memberIssues | i in Claimed implies complete[i]
}

/* N7. CONTROL for N2: a session NAMED for this campaign still blocks with no
   sub-issue in hand -- a planner, or a worker between claims. With N2
   exempting the name that says nothing, this is what keeps the machine-wide
   disjunct from emptying; deleting that whole second disjunct from
   `liveUnderLocally`, or making `namedForThis` false, makes it UNSAT.
   Dropping only the conjunct `and namedForThis[a, c]` leaves it SAT and
   reddens N1 and N2 instead. */
pred N7_SessionNamedForThisBlocks {
  some c: Campaign, s: Session, a: Agent, m: Machine {
    a.peer = s and a.host = m and s.machine = m
    always s.campaignNamed = c
    eventually (a in Live and m in machinesHolding[c]
                and a.task not in c.memberIssues
                and liveUnderLocally[c, m])
  }
}

/* N4. THE STRAY: every sub-issue settled, one of them dropped rather than
   completed, and its ref still on the remote at the close. */
pred N4_DroppedSubIssueLeavesItsRef {
  some c: Campaign, i: Issue |
    /* MEMBERSHIP READ AT THE CLOSE, not at time zero. `memberIssues` is `var`,
       so a witness stated outside the `eventually` can satisfy this by having
       the sub-issue removed from the campaign before the close -- and then the
       rule, which ranges over members, never sees it. That trace is
       `RemoveMember`'s hole and not this one's. */
    eventually (Now.event = CloseIssue and Now.issue = c.campaignIssue
                and i in c.memberIssues
                and closable[c] and dropped[i] and i in Claimed)
}

/* N5. The rule closes it. */
pred N5_NoStrayClaimsClosesIt {
  (always all c: Campaign |
     (Now.event = CloseIssue and Now.issue = c.campaignIssue)
       implies noStrayClaims[c])
  and N4_DroppedSubIssueLeavesItsRef
}

/* N6. CONTROL: a ref left by a MERGED pull request is the ordinary residue and
   blocks nothing, so the rule must still admit a close over one. UNSAT here
   would mean it demanded every ref be deleted before any campaign could end. */
pred N6_NoStrayClaimsAdmitsAMergedResidue {
  (always all c: Campaign |
     (Now.event = CloseIssue and Now.issue = c.campaignIssue)
       implies noStrayClaims[c])
  some c: Campaign, i: Issue |
    eventually (Now.event = CloseIssue and Now.issue = c.campaignIssue
                and i in c.memberIssues
                and complete[i] and i in Claimed)
}

/* =================== attribution, derived =================== */

/* A1. WHO HOLDS THE CLAIM, read with no record anywhere: the agent is live
   and the checkout in its campaign directory is on the claim's branch. Two
   sessions, so `holder` is picking one of them out and not answering
   vacuously. */
pred A1_HolderReadFromTheCheckout {
  some c: Campaign, disj s1, s2: Session, a: Agent {
    a.peer = s2 and a.task in c.memberIssues
    s1.machine = s2.machine
    eventually (a in Live and a in holder[a.task]
                and Now.event = Status and Who.session = s1 and Target.agent = a)
  }
}

/* A3. Control for A1: the derived reading did not buy itself by making the
   agent unable to run. UNSAT here would mean the whole protocol went with the
   record. */
pred A3_HolderRunsTheWholeProtocol {
  twoStepShutdown
  some c: Campaign, disj s1, s2: Session, a: Agent {
    a.peer = s2 and a.task in c.memberIssues
    s1.machine = s2.machine
    eventually (Now.event = Status and Who.session = s1 and Target.agent = a)
    eventually a in Retired
  }
}

/* A13. Without it, a fresh agent briefed from a bad review lands new
   commits under the old review's bit. */
pred A13_PushAfterReviewUnReviews {
  some a: Agent |
    eventually (Now.event = Review and Now.issue = a.task
                and after eventually (Now.event = Push and Target.agent = a
                                      and after (a.task.pullRequest not in Reviewed)))
}

/* =================== who merges, and who reviews =================== */

/* A4. BUILT SO THAT ONLY ONE THING IS WRONG: the agent is confirmed and a
   REPORT preceded the merge, so A5 turns on the review conjunct alone.
   `always s2.worksOn = c` keeps the merger a campaign session. */
pred A4_AgentMergesItsOwnPullRequest {
  some c: Campaign, s2: Session, a: Agent {
    a.peer = s2 and a.task in c.memberIssues
    always s2.worksOn = c
    eventually (Now.event = Report and Target.agent = a)
    eventually (Now.event = MergePullRequest and Who.session = s2 and Now.issue = a.task
                and a in Confirmed and no a.task.pullRequest & Reviewed)
  }
}

/* A5. Dropping `Now.issue.pullRequest in Reviewed` from the rule turns this SAT. */
pred A5_ReviewRuleBlocksTheCollision {
  mergedOnCurrentReview and A4_AgentMergesItsOwnPullRequest
}

/* M3. The planner lands a pull request of its own campaign's claim, one it
   did not cut: the landing planner.md step 9 describes. Dropping the Planner
   disjunct turns it UNSAT. */
pred M3_PlannerLandsItsCampaignsClaim {
  mergedByPlannerOrHolder
  some c: Campaign, s: Session, i: Issue {
    s.role = Planner and always s.worksOn = c
    always i not in s.claimedIssues
    eventually (Now.event = MergePullRequest and Who.session = s and Now.issue = i
                and i in c.memberIssues)
  }
}

/* M3b. The worker holding the claim lands it: worker.md step 8's shape
   where no planner runs. Dropping the Worker disjunct turns it UNSAT. */
pred M3b_WorkerLandsItsOwnClaim {
  mergedByPlannerOrHolder
  some s: Session | s.role = Worker
    and eventually (Now.event = MergePullRequest and Who.session = s)
}

/* M4. A planner of ANOTHER campaign merges: the false allow of 2026-09-14,
   where any claim on the machine carried the merge. SAT without the rule.
   Membership is read AT the merge, since `memberIssues` moves: read at the
   first state, an issue moved into the planner's campaign satisfied it. */
pred M4_PlannerOfAnotherCampaignMerges {
  some disj c1, c2: Campaign, s: Session, i: Issue {
    s.role = Planner and always s.worksOn = c2
    eventually (Now.event = MergePullRequest and Who.session = s and Now.issue = i
                and i in c1.memberIssues)
  }
}

/* M4b. The rule refuses it. Dropping `campaignOf[Now.issue] = Who.session.worksOn`
   turns it SAT. */
pred M4b_TheRuleRefusesAnotherCampaignsPlanner {
  mergedByPlannerOrHolder and M4_PlannerOfAnotherCampaignMerges
}

/* M5. A worker holding ANOTHER claim merges: the unrelated claim the guard
   used to take as the licence. SAT without the rule. Two sessions, because
   the merged head must be somebody's claim: at one, `Claimed` on it puts it in
   the only session's `claimedIssues`. */
pred M5_WorkerMergesByAnotherClaim {
  some s: Session, disj i, j: Issue {
    s.role = Worker
    eventually (Now.event = MergePullRequest and Who.session = s and Now.issue = i
                and j in s.claimedIssues and i not in s.claimedIssues)
  }
}

/* M5b. The rule refuses it. Weakening the Worker disjunct to
   `some Who.session.claimedIssues` turns it SAT. */
pred M5b_TheRuleRefusesAnotherClaim {
  mergedByPlannerOrHolder and M5_WorkerMergesByAnotherClaim
}

/* M7. A planner of NO campaign merges a claim. SAT without the rule. */
pred M7_PlannerOfNoCampaignMerges {
  some s: Session {
    s.role = Planner and always no s.worksOn
    eventually (Now.event = MergePullRequest and Who.session = s
                and Now.issue in Claimed)
  }
}

/* M7b. The rule refuses it. Writing the planner half as
   `campaignOf[Now.issue] = Who.session.worksOn` turns it SAT: both sides are
   empty for an issue of no campaign and a planner of none. */
pred M7b_TheRuleRefusesAPlannerOfNoCampaign {
  mergedByPlannerOrHolder and M7_PlannerOfNoCampaignMerges
}

/* M6. A pull request whose head is no claim is merged. SAT without the rule. */
pred M6_MergeOfAHeadThatIsNoClaim {
  some i: Issue | eventually (Now.event = MergePullRequest and Now.issue = i
                              and i not in Claimed)
}

/* M6b. The rule refuses it, to the planner of the campaign too. Dropping
   `Now.issue in Claimed` turns it SAT. */
pred M6b_TheRuleRefusesAHeadThatIsNoClaim {
  mergedByPlannerOrHolder and M6_MergeOfAHeadThatIsNoClaim
}

/* =================== deleting a tree under an agent =================== */

/* A10. session/checks.als's R3 reached from here: a directory is deleted
   while a live agent on that machine still holds local-only work. */
pred A10_DeleteUnderLiveAgent {
  some c: Campaign, a: Agent {
    some a.peer                        -- a session working its own claim
    a.task in c.memberIssues
    eventually (a in Live and a in LocalOnly
                and Now.event = DeleteDir and Where.machine = a.host)
  }
}

/* A11. The liveness gate closes it. Keying the gate on `some a.peer` instead
   of on `a in Live` turns it SAT again, which is the reading that would let a
   delegate's tree go. */
pred A11_LiveGateBlocksTheDelete {
  noDeleteUnderLiveAgent and A10_DeleteUnderLiveAgent
}

/* A12. UNSAT here would mean the directory could never be deleted at all. */
pred A12_LiveGateAdmitsTheDelete {
  noDeleteUnderLiveAgent
  some a: Agent |
    eventually (a in Live and eventually (a not in Live and Now.event = DeleteDir
                                          and Where.machine = a.host))
}

/* A8. Control for A5: it is not green by forbidding merges. */
pred A8_ReviewRuleAdmitsTheLanding {
  mergedOnCurrentReview
  some c: Campaign, disj s1, s2: Session, a: Agent {
    a.peer = s2 and a.task in c.memberIssues
    s1.machine = s2.machine and always s1.worksOn = c
    eventually (Now.event = Report and Target.agent = a)
    eventually (Now.event = Confirm and Who.session = s1 and Target.agent = a)
    eventually (Now.event = Review and Who.session = s1 and Now.issue = a.task)
    eventually (Now.event = MergePullRequest and Who.session = s1 and Now.issue = a.task)
  }
}

/* A18. Hands-on work is no Agent at all. It matters because the confirm
   conjunct ranges over `agentsOf[Now.issue]`, empty here, so it is
   VACUOUSLY true and the review half holds the rule up alone -- which M2c,
   having an Agent, cannot see. */
pred A18_AgentLessLandingIsAdmitted {
  mergedOnCurrentReview
  no Agent
  some s: Session, i: Issue {
    eventually (Now.event = Review  and Who.session = s and Now.issue = i)
    eventually (Now.event = MergePullRequest and Who.session = s and Now.issue = i)
  }
}

/* A18b. The direction a vacuous conjunct could have swallowed: weaken the
   review half as the confirm half is vacated here and hands-on work lands
   unreviewed with every rule obeyed. */
pred A18b_AgentLessUnreviewedMergeIsBlocked {
  mergedOnCurrentReview
  no Agent
  always Now.event != Review
  some i: Issue | eventually (Now.event = MergePullRequest and Now.issue = i)
}

/* M2. THE TIGHTEST CASE OF THE CURRENCY HALF, which A13 does not have: A13
   stops at the bit being cleared. This is the single step -- a push, and a merge
   in the very next state. It is the REPORT that pinned the pre-push sha, asking
   for a review at a revision nobody is going to merge, and it is what
   scripts/check-merge-review.py refuses on the machine, at the REPORT's post
   through scripts/check-campaign-claim.py.

   The rule it exercises is `mergedOnCurrentReview` and nothing new. A READER
   of merge condition 1 is not a fact this vocabulary
   can hold: nothing here has a sha or a check run to hang one on. SAT without
   the rule, which is what makes M2b a measurement and not a vacuity. */
pred M2_MergeInTheStateAfterAPush {
  some a: Agent |
    eventually (Now.event = Push and Target.agent = a
                and after (Now.event = MergePullRequest and Now.issue = a.task))
}

/* M2b. CONTROL: `push` clears `Reviewed`, so in that state the rule has nothing
   to read and the merge cannot happen. */
pred M2b_TheRuleExcludesTheStalePush {
  mergedOnCurrentReview and M2_MergeInTheStateAfterAPush
}

/* M2c. ...and a review taken AFTER the push still lands, or M2b would be the
   rule that no pushed branch ever merges. Run at one Session, it is also the
   author landing its own reviewed work, which M2b refuses once the review
   is stale. On GitHub the `Review` step is a
   comment, which fires no `check` run; scripts/rerun-check.py, run by
   .github/workflows/review-rerun.yml, re-runs the head's red one so the merge
   this scenario reaches needs no hand step. */
pred M2c_AFreshReviewAfterThePushLands {
  mergedOnCurrentReview
  some s: Session, a: Agent {
    a.peer = s
    eventually (Now.event = Push and Target.agent = a
                and after eventually (Now.event = Review and Who.session = s
                                      and Now.issue = a.task
                                      and after eventually (Now.event = MergePullRequest
                                                            and Now.issue = a.task)))
  }
}

/* A17. THE RESIDUAL GAP OF THE DERIVED READING, and the only one: an agent
   is live and listed, and the checkout it was attributed by has moved off its
   branch, so `holder` no longer names it. R4c is how the checkout moves;
   AttributionIsSound is the same fact as a property. */
pred A17_LiveButNoLongerTheHolder {
  some c: Campaign, a: Agent {
    a.task in c.memberIssues
    eventually (a in Live and liveUnderLocally[c, a.host]
                and a not in holder[a.task])
  }
}
/* =================== the planner =================== */

/* P1. THE ONE-WORKER SHAPE: a request of one sub-issue is filed and worked by
   one session, and settles with no Planner atom anywhere. Requiring a planner
   of every launch, not only a delegate's, turns this UNSAT. */
pred P1_SimpleRequestSettlesWithoutPlanner {
  no plannerAgents
  some s: Session, a: Agent {
    a.peer = s
    eventually (Now.event = Work and Target.agent = a)
    eventually settled[a.task]
  }
}

/* P2. THE TWO-ROLE SHAPE, admitted: a planner launches a delegate onto a
   sub-issue and that delegate works it. Control for DelegateLaunchedByPlanner,
   whose UNSAT could otherwise mean delegates are forbidden altogether. */
pred P2_PlannerLaunchesDelegate {
  some p, a: Agent {
    p.role = Planner and no a.peer
    p.peer = a.launcher and p.task = a.task
    eventually (Now.event = Launch and Target.agent = a and p in Live)
    eventually (Now.event = Work and Target.agent = a)
  }
}

/* P3. `launch`'s checkout clause reads
   `campaignOf[a.task]`. Two campaigns, one machine: the launching session is
   bound to `c` and the sub-issue is a member of the other, and the checkout
   the launch must find sits in the TASK's own directory, not the launcher's --
   pinned by requiring `c`'s own directory hold something else for that repo.
   Reading `Who.session.worksOn` instead makes this UNSAT, the same shape
   R12g uses for `campaignDirAt` inside `commit`.

   `some a.peer` -- a session launching itself onto its own claim -- so
   nothing here also has to set up a live planner and a delegate's ref, which
   `launch` only asks of the peerless shape. */
pred P3_LaunchUsesTheTasksOwnCampaign {
  some a: Agent, c: Campaign |
    some a.peer and
    eventually (Now.event = Launch and Target.agent = a
                and some campaignOf[a.task]
                and c != campaignOf[a.task]
                and Who.session.worksOn = c
                and campaignDirAt[c, a.host].checkedOut[a.task.repo] != a.branch)
}

/* ---------------- commands ---------------- */

-- one sub-issue, one session, no planner
run P1_SimpleRequestSettlesWithoutPlanner for 3 Issue, 1 PullRequest, 1 Campaign, exactly 1 Session, exactly 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1
-- a planner's delegate does work
run P2_PlannerLaunchesDelegate           for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- the launch checkout comes from the task's own campaign, not the launcher's;
-- a second session sets up the OTHER campaign's directory, since a session's
-- own CreateDir is tied to its own worksOn
run P3_LaunchUsesTheTasksOwnCampaign     for 8 Issue, 2 PullRequest, 3 Campaign, 3 Session, 3 Agent, 2 Machine, 4 Repo, 2 Branch, 3 CampaignDir, 20 steps expect 1

-- the whole retirement procedure runs
run Sanity                          for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Session, exactly 1 Agent, exactly 1 Machine, exactly 2 Repo, exactly 1 Branch, 1 CampaignDir, 12 steps expect 1
-- BLOCKED stops the agent
run BlockedAgentDoesNotProceed      for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Session, exactly 2 Agent, exactly 1 Machine, exactly 2 Repo, exactly 1 Branch, 1 CampaignDir, 10 steps expect 1
-- a live planner answers every BLOCKED in its turn
check WaitingWorkerIsAnswered       for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 0
run EscalationAnsweredInTurn        for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
check EscalationGoesThroughAPlanner for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 0
-- rule 3's repair still retires it
run SilentAgentStillRetired         for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Session, exactly 1 Agent, exactly 1 Machine, exactly 2 Repo, exactly 1 Branch, 1 CampaignDir, 12 steps expect 1
-- the poll into the banner gets no answer: `answer` guards on Stopped and only the reset clears it
run L1_PollIntoTheBannerGetsNoAnswer         for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Session, exactly 1 Agent, exactly 1 Machine, exactly 2 Repo, exactly 1 Branch, 1 CampaignDir, 12 steps expect 0
-- the same prompt sent after the reset is answered
run L1b_PromptAfterTheResetIsAnswered         for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Session, exactly 1 Agent, exactly 1 Machine, exactly 2 Repo, exactly 1 Branch, 1 CampaignDir, 12 steps expect 1
run H1_HeartbeatRetiresADoneWorker      for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1
run H1b_HeartbeatRetiresNoHolder         for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run W1_UnclaimedDriftClearsOnClaim       for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 8 steps expect 1
run W1b_SettledDriftClearsOnRelease      for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 8 steps expect 1

run S3_DelegateDiesAfterPushing for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Session, exactly 1 Agent, exactly 1 Machine, exactly 2 Repo, exactly 1 Branch, 1 CampaignDir, 12 steps expect 1
run S4_ReportWithoutPush        for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Session, exactly 1 Agent, exactly 1 Machine, exactly 2 Repo, exactly 1 Branch, 1 CampaignDir, 12 steps expect 1

-- an acquire moves a live role's HEAD
run R4c_CheckoutSwitchedUnderAgent for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 3 Repo, 2 Branch, 1 CampaignDir, 12 steps expect 1
-- a session named for another campaign does not block this campaign's close
run N1_ForeignNamedSessionDoesNotBlock       for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run N2_UnnamedSessionDoesNotBlock            for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
-- control: a session named for this campaign still blocks
run N7_SessionNamedForThisBlocks             for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
-- control: the name exempts the machine-wide disjunct and nothing else
run N3_ForeignNameDoesNotExemptOwnSubIssue   for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1

-- a dropped sub-issue's ref outlives the close, and the next take refuses forever
run N4_DroppedSubIssueLeavesItsRef           for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- the rule closes it
run N5_NoStrayClaimsClosesIt                 for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
-- control: a merged pull request's leftover ref still admits the close
run N6_NoStrayClaimsAdmitsAMergedResidue     for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1

-- a claim nobody was ever launched on is released, and the ref goes with it
run R7a_FreshClaimReleasedWithNoAgent    for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- the discipline closes it
run R7b_WorkerRuleClosesTheFreshClaim    for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
-- ...and hands-on work still releases, through the `complete` one, at `0 Agent`
run R7d_WorkerRuleAdmitsTheAgentLessLanding for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 0 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1
-- the claim closes it
run R4f_ClaimClosesSameSubIssue    for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
-- control: the 422 is load-bearing
run R4g_ClaimWithoutAtomicityStillShared for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R8_ClaimCutOnAnotherRepo for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R8b_RepairExcludesIt for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
-- the scope half: a claim on a repository the campaign is not for
run R14_ClaimOnARepoOutsideTheScope for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R14b_RepairExcludesIt for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run R14c_ScopeAdmitsTheListedMember for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- ...judged against the sub-issue's OWN campaign, which needs two to see
run R14e_TheParentsListIsTheOneThatCounts for 4 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
-- ...and the base, whose absence from `## Repos` is the point
run R14d_ScopeAdmitsTheBaseWhateverTheListHolds for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R9_SettledSubIssueStaysClaimed for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R9b_RepairExcludesIt for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run R9c_RepairAdmitsClaimThenSettle for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R9d_OrdinaryLandingStillAllowed for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R9e_SecondClaimOnAPullRequestLessSubIssue for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run R7e_WorkerRuleAdmitsTheDroppedSubIssue for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R11_HolderThroughAnotherCampaignsDir for 4 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 2 Branch, 2 CampaignDir, 10 steps expect 0
run R12_WorkOutsideAnAcquiredClone for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R12b_RepairExcludesIt for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run R12c_RepairAdmitsTheAcquiredLaunchAndCommit for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R12d_AcquireIsWhatSetsACloneUp for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R12e_TheAgentsOwnHostIsTheOneThatCounts for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
run R12f_NothingButAnAcquireSetsACloneUp for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run R12g_TheAgentsOwnDirIsTheOneThatCounts for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
run R12h_ACommitOnNoCampaignsWorkIsOutsideTheRule for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R12i_TheCommitsOwnHostIsTheOneThatCounts for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
-- the own-hands hole and the guard that closes it; Q5 below is the control
run R4h_OwnHandsWorkWithoutClaim for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R4i_GuardClosesOwnHandsGap   for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
-- the gate leaves a record, and the record does not forbid the work
run R15_WorkLeavesNoVerdict      for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R15b_DurableExcludesIt       for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run R15c_DurableStillAdmitsTheWork for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- the shell hole the pre-tool-use half leaves, the commit gate that closes it, and the control
run R4k_UnclaimedShellWriteThenCommit for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R4l_CommitGateClosesIt           for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run R4m_GateAdmitsClaimedCommit      for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1

/* Q1-Q9: permission by role. Q1, Q4 and Q4b need a SECOND campaign or a second
   sub-issue to be about an issue the session does not cover, so they run at the
   wider scope; the rest run at R4h's line. Every UNSAT here has a control run
   beside it, and Q2c is the control that is UNSAT ON PURPOSE. */
-- a planner closes another campaign's issue
run Q1_PlannerClosesOtherCampaignsIssue   for 4 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
-- a planner never commits, and the CONTROL says which rule forbids it
run Q2_PlannerCommits                     for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run Q2c_PlannerCommitsUnguarded           for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
-- a worker on its own claim
run Q3_WorkerClosesOwnClaim             for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- and not on another campaign's, nor on an unclaimed sibling
run Q4_WorkerClosesOtherCampaign        for 4 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
run Q4b_WorkerClosesUnclaimedSibling    for 4 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
run Q14_WorkerReleasesAnotherCampaignsIssue for 4 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 8 steps expect 0
run Q14c_WorkerReleasesAnotherCampaignsIssueUnguarded for 4 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 8 steps expect 1
-- claimed work under the rule that subsumes claimBeforeWork
run Q5_WorkerWorksClaimedCheckout       for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- the unnamed session, refused, with its control
run Q7_UnnamedSessionRefused              for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run Q7c_UnnamedSessionReachesTheEventUnguarded for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- the campaign issue body: a worker may not, a planner may
run Q8_WorkerWritesCampaignBody         for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run Q8c_WorkerWritesCampaignBodyUnguarded for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run Q8b_PlannerWritesCampaignBody         for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- opening a campaign is planner work
run Q9_WorkerFilesCampaignIssue         for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run Q9c_WorkerFilesCampaignIssueUnguarded for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- a claim is a campaign-plane write: a planner may cut one on any campaign
-- bound HERE, a worker only on its own, and Q10c says which rule refuses
-- the carve-out is what makes this write reachable at all
run Q11_WorkerWritesItsOwnCampaignIssue    for 5 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
run Q10_PlannerClaimsOnAnotherBoundCampaign  for 5 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
run Q10b_WorkerClaimsOnAnotherBoundCampaign for 5 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
run Q10c_WorkerClaimsOnAnotherBoundCampaignUnguarded for 5 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
run Q12_UnbriefedSessionRefused                     for 5 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
run Q12c_UnbriefedSessionReachesTheEventUnguarded   for 5 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
run Q12b_RebriefedSessionActs                       for 5 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
run Q13_UnstampedSessionRefused                     for 5 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
run Q13c_UnstampedSessionReachesTheEventUnguarded  for 5 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
run Q13b_RestampedSessionActs                      for 5 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1

-- ownership is not the axis
run R5c_NonLauncherSameMachineIsFine for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- a dangling claim is reclaimable
run R6b_ReclaimAfterDeath        for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 14 steps expect 1

/* A1 and A3 run at two Sessions, so the derived reading is choosing between
   them. A10-A12 need a CampaignDir to delete mid-trace. A18 and A18b, and M2c
   below, run at ONE Session, because the absence of a second merger is
   their subject. */
-- the holder read off the checkout, with no record anywhere
run A1_HolderReadFromTheCheckout          for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- control: the whole run still happens
run A3_HolderRunsTheWholeProtocol         for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1
-- the live collision: a self-merge with NO review
run A4_AgentMergesItsOwnPullRequest                for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1
-- still caught
run A5_ReviewRuleBlocksTheCollision          for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 0
-- control: two-session landing runs
run A8_ReviewRuleAdmitsTheLanding            for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1

-- session/checks.als's R3, reached from here
run A10_DeleteUnderLiveAgent      for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- and closed by reading liveness
run A11_LiveGateBlocksTheDelete   for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
-- control
run A12_LiveGateAdmitsTheDelete   for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- a push retires a review
run A13_PushAfterReviewUnReviews             for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1
-- the derived reading's one residual gap: live, listed, checkout moved off
run A17_LiveButNoLongerTheHolder             for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- hands-on work, reviewed and merged by one session, at `0 Agent`
run A18_AgentLessLandingIsAdmitted           for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 0 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- and unreviewed it does not land. The pair matters because the confirm conjunct is VACUOUS at `0 Agent`, so the review half holds the rule up alone
run A18b_AgentLessUnreviewedMergeIsBlocked   for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 0 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0

/* The tightest case of the currency half. */
run M2_MergeInTheStateAfterAPush              for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run M2b_TheRuleExcludesTheStalePush           for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run M2c_AFreshReviewAfterThePushLands         for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1
run M3_PlannerLandsItsCampaignsClaim              for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run M3b_WorkerLandsItsOwnClaim                    for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run M4_PlannerOfAnotherCampaignMerges             for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run M4b_TheRuleRefusesAnotherCampaignsPlanner     for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run M5_WorkerMergesByAnotherClaim                 for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run M5b_TheRuleRefusesAnotherClaim                for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run M7_PlannerOfNoCampaignMerges                 for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run M7b_TheRuleRefusesAPlannerOfNoCampaign      for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run M6_MergeOfAHeadThatIsNoClaim                  for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run M6b_TheRuleRefusesAHeadThatIsNoClaim          for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0

/* ---------------- properties ---------------- */

/* The shutdown protocol keeps the work it is for. `Confirmed` cleared by any
   later `work` is what makes this green survive an agent that keeps working
   after being confirmed; dropping `Confirmed` from `twoStepShutdown` finds a
   counterexample, and dropping `Answered` does not. */
assert TwoStepShutdownSuffices { twoStepShutdown implies noWorkDestroyed }

/* Dropping the ANSWER is safe as long as the confirmation is kept. */
assert SilenceResolutionStaysSafe { resolveSilenceExternally implies noWorkDestroyed }

/* Nothing written in THIS file carries it, so it tests the composition idiom:
   dropping `githubFrame` from github/system's fall-through branch reddens it. */
assert NoLostWork {
  always all i: Issue |
    (complete[i] and Now.event in AgentDie + DeleteDir) implies after complete[i]
}

/* The three claims the Role docstring makes, one command each, since a fact
   or a guard deleted is invisible to the snapshot. Dropping `a.role = Worker`
   from `work` reddens the first, from `report` the second; deleting the
   `some a.peer` fact in AgentWellFormed reddens the third. */
assert PlannerNeverLocalOnly { always no plannerAgents & LocalOnly }
assert PlannerNeverReports   { always no plannerAgents & Reported }
assert PlannerIsASession     { all a: plannerAgents | some a.peer }

/* The two planes do not overlap, which is what makes `planeOf` `lone` rather
   than a coincidence of the current event lists. Moving an event into both
   lists reddens it. */
assert DisjointPlanes { no campaignPlaneEvents & codePlaneEvents }

/* The role rule subsumes the claim rule: a session permitted to work an
   issue holds a claim on it, so `claimBeforeWork` needs no separate statement
   once `permissionByRole` holds. Dropping `i in s.claimedIssues` from
   `mayAct`'s code-plane row reddens it. Q5 is the control that the
   subsumption is not by forbidding work altogether. */
assert PermissionImpliesClaimGates { permissionByRole implies claimBeforeWork }

/* ATTRIBUTION, AND WHAT DERIVING IT COSTS. `holder` reads the claim's owner
   off the checkout, so a live agent is its own task's holder exactly while the
   checkout stays on its branch. `Acquire` is what moves one, and nothing
   forbids moving it under a live agent -- R4c is that trace and A17 is the
   state it leaves. Stated as a property rather than a fact because the fact
   would forbid R4c and call the silence safety. */
assert AttributionIsSound { always all a: Live | a in holder[a.task] }

/* Every delegate was launched by its planner: the launching session holds a
   Planner atom on the delegate's sub-issue. Dropping the planner conjunct from
   `launch` reddens it; P2 above is the control that delegates still
   launch. */
assert DelegateLaunchedByPlanner {
  always all a: Launched | no a.peer implies
    (some p: plannerAgents | p.peer = a.launcher and p.task = a.task)
}

/* A SESSION NEVER TAKES TWO SUB-ISSUES WITHOUT A COMPACTION BETWEEN THEM, and
   it is DERIVED rather than assumed: `launch` spends the bit, only
   `agentRelease` returns it, and `launch` requires it.

   Deleting either of
   `launch`'s two clauses reddens THIS command, UNSAT -> SAT. Deleting the
   release's `Compacted' = Compacted + (Who.session & (Session <: role).Worker)`
   does NOT: with nothing to
   return the bit, a session's second launch becomes unreachable and this
   assert stays green over an empty set. So that clause is pinned by P8 below
   and by nothing here, which is the whole reason P8 exists -- a green assert
   is a rule only while its subject is reachable.

   It is the whole rule, read at its two ends: `campaign-claim.py
   release` compacting its own pane, and `scripts/campaign-assign.py` refusing
   a pane that has not. */
assert SessionCompactsBetweenSubIssues {
  always all a1, a2: Agent |
    (some a1.peer and a1.peer = a2.peer and a1 != a2
     and Now.event = Launch and Target.agent = a2 and a1 in Launched)
    /* BETWEEN, not merely BEFORE. The nested `once` is what says "after a1 was
       launched": some past instant held a release by this session, and at that
       instant a1 had already been launched. A single `once (Release ...)`
       says only that the session released
       at SOME point, which is a weaker claim than the comment above makes and
       true for a release that happened before a1 ever started. It held only
       because nothing else in the model returns the bit; a later event that
       did would leave it green and the comment false. */
    /* `a1 in Launched` at the release, and not a nested `once` of a1's
       `Launch`: an agent also starts by `handoff`, which is no
       `Launch`, and the nested form read a successor's heir as never started
       -- so a successor's release could never come after it and the assert
       went false for a trace doing exactly what it asks -- at
       3 Agent, the predecessor, its heir and the successor's next, which is
       why the command below runs at 3. `Launched` only grows, so being in it
       at the release says the release came after. */
    implies once (Now.event = Release and Who.session = a1.peer and a1 in Launched)
}

/* THE HANDOFF, four claims, each reddened by deleting one clause of
   `handoff` or `sessionHandoff`, named beside it. */

/* After it, the predecessor never again holds anything live, and the
   successor holds each of its sub-issues exactly once. Dropping `+ olds.h`
   from `Live'` reddens it, and so does dropping `no Who.session & Exited`,
   since the predecessor could then launch again. Dropping `- olds` does not, and Cov_Handoff is what goes red instead:
   the old atom is then both Live and Retired, which AgentWellFormed forbids,
   so no handoff moving work is reachable and this check holds vacuously. */
assert HandoffLeavesOneHolder {
  always all p, t: Session, a: Agent |
    (Now.event = Handoff and Who.predecessor = p and Who.session = t and a in heldBy[p])
    implies after ((always no heldBy[p]) and one (heldBy[t] & task.(a.task)))
}

/* The successor performs it, every agent the predecessor held is retired by
   it, and the predecessor performs nothing afterwards. Dropping `t != p`
   reddens it, and so does dropping `Retired'` or `no Who.session & Exited`. */
assert HandoffClosedBySuccessor {
  always all p, t: Session |
    (Now.event = Handoff and Who.predecessor = p and Who.session = t)
    implies (p != t and (all a: heldBy[p] | after a in Retired)
             and after always Who.session != p)
}

/* Every claim the predecessor held becomes the successor's; the work on the
   checkout and a pending BLOCKED move to the heir. The ref itself is framed
   by github/system.als, so it is not asserted here. Dropping the
   `t->(p.claimedIssues)` term reddens it, and so does dropping either
   `(olds & ...).h` term it reads. */
assert HandoffLosesNoClaim {
  always all p, t: Session |
    (Now.event = Handoff and Who.predecessor = p and Who.session = t)
    implies ((all i: p.claimedIssues | after i in t.claimedIssues)
             and (all a: heldBy[p] & LocalOnly | after some (heldBy[t] & LocalOnly & task.(a.task)))
             and (all a: heldBy[p] & Waiting   | after some (heldBy[t] & Waiting   & task.(a.task))))
}

/* A stood-down or limit-stopped agent is never handed off. It restates
   `handoff`'s guard, so deleting that guard is loud: nothing else reads it. */
assert HandoffTakesNoStoppedWork {
  always (Now.event = Handoff implies no heldBy[Who.predecessor] & (StandDownTaken + Stopped))
}

/* A successor named for another campaign, or for none, never takes the work
   over. Dropping `t.campaignNamed = p.worksOn` reddens it. It restates that
   guard, and is here so deleting the guard is loud. */
assert SuccessorNamedForAnotherRefused {
  always (Now.event = Handoff implies Who.session.campaignNamed = Who.predecessor.worksOn)
}

/* ---------------- reachability floor ----------------
   Each is the witness of an event a check above names. Cov_Acquire witnesses
   an event only `run`s name (R4c, R12d, R12f) and no `assert` does, so
   alloy-check does not require it; it shows the event fires at all. */

pred Cov_LaunchAgent      { eventually (Now.event = Launch and some Target.agent) }
pred Cov_Work             { eventually Now.event = Work }
pred Cov_Push             { eventually Now.event = Push }
pred Cov_AgentDie         { eventually Now.event = AgentDie }
pred Cov_GuardedRelease   { eventually Now.event = Release }
pred Cov_DeleteDirInOrchestration        { eventually Now.event = DeleteDir }
pred Cov_Claim            { eventually Now.event = Claim }
pred Cov_FileCampaignIssue    { eventually Now.event = FileCampaignIssue }
pred Cov_CloseIssueInOrchestration           { eventually Now.event = CloseIssue }
pred Cov_WriteBody            { eventually Now.event = WriteBody }
pred Cov_OpenPullRequestInOrchestration      { eventually Now.event = OpenPullRequest }
pred Cov_CommitLocal          { eventually Now.event = CommitLocal }
pred Cov_StandDown        { eventually Now.event = StandDown }
pred Cov_Retire           { eventually Now.event = Retire }
pred Cov_Blocked          { eventually Now.event = Blocked }
pred Cov_Decide           { eventually Now.event = Decide }
pred Cov_RemoveMemberInOrchestration     { eventually Now.event = RemoveMember }
pred Cov_Acquire          { eventually Now.event = Acquire }
pred Cov_AddMemberInOrchestration            { eventually Now.event = AddMember }
pred Cov_CreateDir            { eventually Now.event = CreateDir }
/* A handoff that moves work, so the four checks above are not green over a
   handoff of an empty session. */
pred Cov_Handoff          { eventually (Now.event = Handoff and some heldBy[Who.predecessor]) }

/* THE CONTROL THAT THE CLAIM MOVE IS LOAD-BEARING: under the role rule, the
   heir works the sub-issue it was handed, with no claim cut in between.
   Dropping `t->(p.claimedIssues)` from `sessionHandoff` makes this UNSAT,
   since `mayAct` then refuses the heir the code plane. The `until` is the
   whole discriminator: without it the successor claims the sub-issue again
   after the handoff and the run is SAT either way. */
pred P10_HeirWorksAfterHandoff {
  permissionByRole
  some t: Session, b: Agent | b.peer = t
    and eventually (Now.event = Handoff and Who.session = t
                    and after ((Now.event != Claim)
                               until (Now.event = Work and Target.agent = b)))
}
/* THE CONTROL FOR THE ASSERT ABOVE. Without it, deleting the release's
   `Compacted' = Compacted + (Who.session & (Session <: role).Worker)` makes a
   session's second launch unreachable and the assert stays green on a vacuity nobody would read. This
   says two launches by one session do happen, so a green assert is a rule and
   not an empty set. */
/* THE CONTROL FOR THE GUARD'S SCOPE, and P8 cannot be it. P8's two launches
   both have `some peer`, so it is satisfied whether the guard binds on every
   launch or only on a session taking its own claim -- the
   unconditional form leaves P8 SAT.

   This one separates them: a session works a sub-issue itself and LATER
   launches a delegate. Unconditional, the delegate launch would need the
   planner compacted, which only a release gives back, so a planner could
   launch at most one delegate between releases -- and that is a precondition
   nothing on the machine reads, since `campaign-assign.py` reads the
   transcript of the session being ASSIGNED and a delegate has none until its
   launch makes one. So this run going UNSAT is the signal that the model has drifted back
   to demanding what no reader checks. */
pred P9_DelegateAfterOwnSubIssue {
  some s: Session | some disj own, deleg: Agent |
    own.peer = s and no deleg.peer and deleg.launcher = s
    /* WITH NO RELEASE IN BETWEEN, and that clause is the whole discriminator:
       without it the session simply releases between the two launches and the
       run is satisfiable either way. Unconditional, the delegate launch needs
       the bit a release alone returns, so forbidding the release makes the
       trace impossible. */
    and eventually (Now.event = Launch and Target.agent = own
                    and after ((not (Now.event = Release and Who.session = s))
                               until (Now.event = Launch
                                      and Target.agent = deleg)))
}
pred P8_TwoSubIssuesOneSession {
  some s: Session | some disj a1, a2: Agent |
    a1.peer = s and a2.peer = s
    and eventually (Now.event = Launch and Target.agent = a1
                    and eventually (Now.event = Launch and Target.agent = a2))
}

/* ---------------- commands ---------------- */

-- a death or a delete never un-completes
-- the shutdown protocol, and rule 3's repair, destroy no work
check TwoStepShutdownSuffices    for 2 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 0
check SilenceResolutionStaysSafe for 2 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 0
check NoLostWork        for 3 Issue, 2 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 0

-- what a planner does not share: the work bit, the REPORT, and being a delegate
check PlannerNeverLocalOnly for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 0
check PlannerNeverReports   for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 0
check PlannerIsASession     for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 0
check DisjointPlanes for 1 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 1 Repo, 1 Branch, 1 CampaignDir, 1 steps expect 0
check PermissionImpliesClaimGates for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 0
-- every delegate has a planner behind its launch
check DelegateLaunchedByPlanner       for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 0

-- the derived attribution is NOT sound on its own: an acquire moves the checkout out from under a live agent
check AttributionIsSound              for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 3 Repo, 2 Branch, 1 CampaignDir, 10 steps expect 1

-- the floor: every event a check above names fires in some trace, so none holds by vacuity
run Cov_LaunchAgent      for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_Work             for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_Push             for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_AgentDie         for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_GuardedRelease   for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_DeleteDirInOrchestration        for 3 Issue, 2 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_Claim            for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run Cov_FileCampaignIssue    for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run Cov_CloseIssueInOrchestration           for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run Cov_WriteBody            for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run Cov_OpenPullRequestInOrchestration      for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run Cov_CommitLocal          for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run Cov_StandDown        for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_Retire           for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_Blocked          for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_Decide           for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_RemoveMemberInOrchestration     for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_Acquire          for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 3 Repo, 2 Branch, 1 CampaignDir, 10 steps expect 1
run Cov_AddMemberInOrchestration            for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run Cov_CreateDir            for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1

-- a release compacts, a launch spends it, so two sub-issues need a release between them
check SessionCompactsBetweenSubIssues for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 3 Agent, 1 Machine, 3 Repo, 2 Branch, 2 CampaignDir, 12 steps expect 0
-- and two sub-issues on one session do happen, so the check above is not vacuous
run P8_TwoSubIssuesOneSession        for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 2 Branch, 2 CampaignDir, 12 steps expect 1
-- the handoff: one holder after, closed by the successor, no claim lost, the wrong name refused
check HandoffLeavesOneHolder          for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 3 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 0
check HandoffClosedBySuccessor        for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 3 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 0
check HandoffLosesNoClaim             for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 3 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 0
check HandoffTakesNoStoppedWork       for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 3 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 0
check SuccessorNamedForAnotherRefused for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 0
-- and each is about a handoff that moved work, which the heir then works
run Cov_Handoff                       for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run P10_HeirWorksAfterHandoff         for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
-- and a delegate launch is NOT guarded, so one session can work a sub-issue and then launch one
run P9_DelegateAfterOwnSubIssue      for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 3 Agent, 1 Machine, 3 Repo, 3 Branch, 2 CampaignDir, 12 steps expect 1
