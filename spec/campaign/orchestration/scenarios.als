/*
 * The disciplines a shutdown, a claim, a delete and a merge might follow, and
 * the witnesses that measure each. github/system.als is spec/'s entry point.
 */
module orchestration/scenarios

open orchestration/system

/* ---------------- the property ---------------- */

/* The one thing the protocol is for. */
pred noWorkDestroyed {
  always (Now.event = Retire implies Target.agent not in LocalOnly)
}

/* ---------------- disciplines: the shutdown, three ways ---------------- */

/* The agent's own account as the basis for destroying its workspace. */
pred oneStepShutdown {
  always (Now.event in StandDown + Retire implies Target.agent in Reported)
}

/* Both conjuncts are load-bearing: the answer names work only the agent
   can see, the confirmation is the session looking for itself. */
pred twoStepShutdown {
  always (Now.event in StandDown + Retire implies
            (Target.agent in Answered and Target.agent in Confirmed))
}

/* Narrowing this to `StandDown + Retire` reddens TwoStepCoLocatedSuffices: a
   remote session can then run the confirmation a local one acts on. */
pred coLocatedShutdown {
  always (Now.event in Confirm + ConfirmElsewhere + StandDown + Retire
            implies coLocated[Who.session, Target.agent])
}

/* Rule 3: an agent that is gone may be stood down on the confirmation
   alone, and only on it. */
pred resolveSilenceExternally {
  always (Now.event in StandDown + Retire implies
            (Target.agent in Confirmed
             and (Target.agent in Answered or Target.agent not in Live)))
}

/* The rule it replaces: wait for the answer. */
pred waitForAnswer {
  always (Now.event in StandDown + Retire implies Target.agent in Answered)
}

/* What only a session on the agent's own machine can check. */
pred localCheckedShutdown { always (Now.event = StandDown implies Target.agent not in LocalOnly) }

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
   because no atom here carries a person's word; R7c is the ordinary release
   that must stay reachable without it.

   R7c IS WIDER THAN THE SCRIPT, and #187 owns the gap. `Launched` is a fact
   about an agent, and the script has no reader for it: on GitHub R7c's state
   -- launched, dead, nothing pushed -- is a ref 0 ahead of the base whose
   branch was never a merged pull request's head, which is the one shape
   `cmd_release` refuses without `--confirmed-absent WHO`. And that is the SECOND
   refusal that state hits, not the first: `launch` checks the branch out and
   neither `agentDie` nor `retire` undoes it, so the dead delegate's clone still
   holds the branch and the occupant check refuses before the merge question is
   ever asked -- a refusal `--confirmed-absent` does not lift, since removing a
   worktree is not something a person's word stands in for. So the model's
   "ordinary release" is, at this sha, a worktree removal and then a release
   that asks a person. What
   would close the gap is a durable fact saying a holder was launched at all,
   which is what #187 is deciding. */
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
   (`Issue.repo`, read from its `Repository:` line) that no taker supplies. */
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
   `baseIssuesAreCampaignIssues` in github/system.als already says a sub-issue
   may land in the base; `R4_RepolessCampaign` already claims one with
   `always no c.reposInBody`. What neither covers is a NON-EMPTY list that does
   not hold the base -- the shape every campaign with a member repository has --
   and campaign-claim.py refused exactly that shape from #187 until #203, so
   every sub-issue of such a campaign was unclaimable. R14d is that world, and
   it goes UNSAT the moment this disjunct is dropped.

   THE READER HAS COME UP TO THIS, and the rule did not move to meet it.
   `campaignOf[Now.issue]` is the sub-issue's ACTUAL parent. campaign-claim.py
   used to read the `## Repos` of whatever campaign number the caller typed and
   never ask GitHub for the parent, so the two agreed exactly when the caller
   typed the right one; since kalaluthien/campaign-base#206 its `take` reads
   the parent and refuses a sub-issue whose parent is a campaign other than the
   one named. Two outcomes it does NOT refuse, and each prints apart: a parent
   that could not be read (not a parent that disagrees), and an issue with no
   parent at all, which #1 sitting at GitHub's 100-sub-issue cap keeps
   producing. `release` and `live` stay keyed on the typed number on purpose --
   they read refs already cut, so a parentage check there would refuse to reach
   exactly the mis-cut ref this closes.

   `campaignOf` is NEVER EMPTY at a Claim, so no vacuous branch hides in the
   second disjunct: `claim` in github/system.als already requires
   `i in Campaign.memberIssues`. That is why the membership conjunct in R14 and
   R14c is a statement of the world rather than a constraint, and why removing
   it moves no verdict.
   Separately, the base's absence from `## Repos` was assumed by R14d's witness
   and enforced by no reader and no fact until kalaluthien/campaign-base#205.
   It is now `WellFormed`'s last conjunct in github/system.als, pinned by
   `S20_TheBaseIsNeverListed`, and refused by `campaign-repos.py`. R14d's own
   `Base not in c.reposInBody` is therefore a statement of the world rather
   than a constraint, and removing it moves no verdict -- it is kept because
   the command's comment argues from it.

   A RULE WITH ONE READER IS A RULE WITH ONE ROUTE, and there was a second
   (kalaluthien/campaign-base#213). `campaign-claim take` is the reader of this
   rule; `gh issue develop --name campaign-<N>/<issue>-<topic>` cuts the same
   ref and reads none of it -- not this scope, not the parent `campaignOf`
   names, not the binding. Nothing in the model separates the two, and nothing
   can: a `Claim` is a `Claim` whichever command made it, which is the point.
   So the separation is the guard's, and `PLANNER_GH_EXCEPT` in
   check-campaign-claim.py is where it is written: the one `gh issue` verb a
   planner's campaign-plane licence does not carry, kept out for the route it
   is and not for the plane it is on -- `Claim` is in `campaignPlaneEvents` in
   system.als, so a plane reading admits it.

   WHAT IS ENFORCED IS THE PLANNER'S ROUTE AND ONLY IT, and the first cut of
   this paragraph claimed more than the code did. The guard REFUSES the verb in
   its planner branch; every other session still reaches it through the claim
   reading, so one already holding a claim on an issue may cut a second,
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
   not where the session sits: a change landing outside every base tree
   and every campaign directory is not work on a sub-issue and is no step of
   this relation. The guard reads the target over two bounded languages and
   no other: a file tool's path, and a `gh` command, which is one program with
   a stable grammar -- a write to the campaign plane through it has no
   filesystem target at all and is always `Work`, and a `gh` call the guard
   READS AS A CALL and cannot parse is refused, never guessed. The narrower
   verb is deliberate and was bought twice: a `gh` write can always be hidden
   from a bounded reader by a shell that is not read -- a here-string, a pipe
   into a shell, a script file, an interpreter that is not a shell -- so a
   sentence promising that no `gh` write escapes is one the code cannot make
   true, and it produced a CONTRADICTS on every audit that checked it. What
   the guard does promise: a `gh` TOKEN it can see and cannot resolve to a
   call is refused rather than guessed at. On the other side of that line the
   guard reads the `-c` string of the shells it NAMES, spelled alone or last in
   a cluster -- a named list, not the category, because there is no test for
   "is a shell" and a shell it does not name (`csh`, `tcsh`) is unread like any
   other interpreter. The line is drawn at a list rather than at a category on
   purpose: a category is a promise about programs this has never seen, and the
   two previous attempts at this sentence were false in opposite directions --
   one calling a shell's `-c` unreadable, the next calling every shell's read.

   A shell command is NOT read for a target: an arbitrary shell string is an
   unbounded language, and every reader of it was one more alternation for the
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

/* THE VERDICT IS DURABLE (kalaluthien/campaign-base#196). `claimBeforeWork`
   above is the gate; this is the rule that the gate leaves a record of what it
   decided. Without it a guard that judged every call and wrote nothing
   satisfied the whole model, which is the state `check-campaign-claim.py` was
   in until #209: its precision could only be reconstructed from the memory of
   whoever it refused.

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

/* ---------------- discipline: permission by role (#185) ---------------- */

/* The events a worker may not reach on the campaign plane whatever it holds.
   `WriteBody` because the campaign issue body changes only at a scope change or
   at the close, both a person's decision carried by a planner; and
   `FileCampaignIssue` because filing one is opening a campaign. Filing a
   SUB-ISSUE is not here: `addMember` in github/system.als has no actor
   precondition on purpose, and any session may file one. */
fun plannerOnlyEvents: set Event { WriteBody + FileCampaignIssue }

/* Whether a session may perform this event on this issue. The table in #185:

     planner    campaign plane, any campaign            code plane: never
     worker   campaign plane, its own campaign and
                only a sub-issue it holds a claim on    code plane: only a
                                                        sub-issue it has claimed
     no role    refused on both planes

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
   session/system.als agrees, and did not always: it pinned every claim to
   `s.worksOn`, which made AGENTS.md's cross-campaign delegate claim
   unreachable here for a reason that was NOT this rule. It now splits by role
   and bounds the planner's by the BINDING instead -- any campaign bound to the
   session's own machine -- and Q10/Q10b/Q10c are the three that say which of
   the two rules refuses a worker the same claim. */
/* WHAT THIS IS NOT. `s.role` is read from the session's own name, and a session
   can rename itself -- so this table bounds MISTAKES and not adversaries. It is
   not weaker than what it replaces: every session on a machine shares one `gh`
   account, so a session that renames itself a planner already holds the power
   the name would grant, and what the rule buys is that the role is explicit and
   the mistake is loud. Stated here because a permission table is the thing a
   reader is most likely to mistake for a security boundary. The sub-issue for
   tying the name to something the named session did not choose is #194. */
/* THE CAMPAIGN ISSUE IS NOT A SUB-ISSUE, and #207 is the row that follows from
   that. `memberIssues` excludes it (github/system.als), so `i in
   s.worksOn.memberIssues` refuses a worker every write to the issue of the
   campaign it works -- including a comment, which the model has no
   precondition on. The worker's campaign-plane row therefore admits the
   campaign issue of its OWN campaign, and `Q11` is the witness.

   Bounded by the EVENT and not by a claim: the guard admits only a comment
   there, because `WriteBody` is the charter and belongs to the close, and a
   claim on some other sub-issue makes an irreversible write no safer. The
   guard's own `OWN_CAMPAIGN_GH` is the verb list; this is the event.

   WHICH CAMPAIGN'S issue this rule DOES hold -- `i = s.worksOn.campaignIssue`
   is the session's own and no other -- but NO COMMAND HERE CAN SHOW IT, and
   that gap is the thing to know before touching the conjunct. Widening it to
   `i in Campaign.campaignIssue` leaves every command in this file green, so
   the conjunct is load-bearing and unpinned at once: delete it on the
   suite's word and nothing goes red. Its two neighbours are not like that --
   dropping the disjunct reddens `Q11`, dropping `i not in
   Campaign.memberIssues` reddens `Q4`.

   The reason no command can reach it: `sessionCloseIssue` in
   session/system.als already pins every campaign-issue close to the acting session's own campaign, for
   every role and independently of `mayAct` -- so a scenario asserting an
   worker cannot close ANOTHER campaign's issue comes out UNSAT whatever this
   predicate says, and one was written and deleted for exactly that reason: it
   survived widening the carve-out to every campaign issue, with the whole
   model still green. `Q11` is the honest half, and measures that the carve-out
   is what makes the write reachable AT ALL. The campaign bound itself is
   tested where it CAN fail, in check-campaign-claim-test.py: dropping
   `i == campaign` from the guard's carve-out fails two named cases there.

   `i not in Campaign.memberIssues` is not decoration. Nothing in github/system
   forbids one campaign's ISSUE from being another campaign's SUB-ISSUE -- an
   overlap that cannot happen on the tracker, where a campaign issue carries
   the `campaign` label and a sub-issue is somebody's `--parent` -- and without
   the conjunct the carve-out reached it, which Q4 caught. Bounded here rather
   than by a new fact, because the fact is github/system's to add and adding it
   would redden commands this branch is not about. */
pred mayAct[s: Session, e: Event, i: lone Issue] {
  some s.role
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

/* The rule as written, the honest local reading, and the reading a session
   can actually perform. */
/* The commit half of the same gate: scripts/check-commit-claim.py, a
   pre-commit hook refusing a commit on a base tree or under a campaign
   directory whose branch is not a claim. Keyed on `a.peer` for the same
   reason as `claimBeforeWork`: a delegate's launch was gated already. */
pred claimBeforeCommit {
  always (Now.event = CommitLocal and some Target.agent.peer
            implies Now.issue in Target.agent.peer.claimedIssues)
}

/* The rule as written, and the honest local reading a session can perform.
   There is no third: the close reads `herdr agent list`, which sees every
   live session on this machine, so what it can read and what it can attribute
   are now the same set. */
pred closeDisciplineFull[c: Campaign] {
  always ((Now.event = CloseIssue and Now.issue = c.campaignIssue) implies closableWithAgents[c])
}
pred closeDisciplineLocal[c: Campaign] {
  always ((Now.event = CloseIssue and Now.issue = c.campaignIssue) implies closableLocally[Who.session, c])
}

/* Where session/scenarios.als's R3 is answered: keyed on LIVENESS, which is
   what `herdr agent list` hands a deleting session directly. It used to be
   keyed on a record that died with the very tree it was about to delete. */
pred noDeleteUnderLiveAgent {
  always (Now.event = DeleteDir implies
            no a: Agent | a in Live and a.host = Where.machine
                          and campaignOf[a.task] in (OnDisk - OnDisk').campaign)
}

/* Empty for a sub-issue a session did with its own hands, which is what makes
   `mergedOnCurrentReview`'s second conjunct vacuous there -- see A18/A18b. A
   planner atom on the issue is in it: `confirm` needs only `a not in
   LocalOnly`, which a planner always satisfies, so the discipline is reachable
   unweakened and keeps its co-location conjunct over the planner too. */
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
             and (all a: agentsOf[Now.issue] |
                    a in Confirmed and coLocated[Who.session, a])))
}

/* ---------------- witnesses ---------------- */

/* SAT means the disciplines forbid a counterexample rather than the protocol. */
pred Sanity {
  coLocatedShutdown and twoStepShutdown
  and eventually (some a: Agent | a in Retired)
  and eventually Now.event = Work
  and eventually Now.event = Push
}

/* The claim leaves the local fact and the GitHub fact exactly as they were. A
   signal weaker than an explicit REPORT says even less. */
pred ReportIsNotEvidence {
  some a: Agent | eventually (Now.event = Report and Target.agent = a
    and a in LocalOnly and a in LocalOnly'
    and not complete[a.task] and after always not complete[a.task])
}

pred BlockedAgentDoesNotProceed {
  some a: Agent | eventually (a in Waiting and always (a in Waiting and Now.event != Work))
}

/* THE FAILURE RULE 3 FORBIDS: under wait-for-the-answer there is no such
   trace, so the session waits for a reply that cannot come. */
pred SilentAgentIsRetirableUnderWait {
  waitForAnswer
  and (some a: Agent |
         eventually (a in Asked and a not in Live and a in Retired)
         and always a not in Answered)
}

/* The repair is a repair and not a prohibition. */
pred SilentAgentStillRetired {
  resolveSilenceExternally and coLocatedShutdown
  and (some a: Agent | eventually a in Retired and always a not in Answered)
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

/* Live with nothing pushed is the only state where local-only work is
   actually destroyed. */
pred S9_OrphanedByLocalDelete {
  one c: Campaign | one a: Agent {
    a.task in c.memberIssues
    eventually (Now.event = DeleteDir and Where.machine = a.host and a in Live
                and a in LocalOnly and no a.task.pullRequest)
    eventually (a in Live and a.host not in machinesHolding[c])
  }
}

/* =================== a close during another session's work =================== */

/* R3b. The local gate reads closable; the campaign is not. */
pred R3b_CloseFromAnotherMachine {
  some c: Campaign, disj s1, s2: Session, a: Agent {
    s1.machine != s2.machine
    a.launcher = s1
    closeDisciplineLocal[c]
    eventually (Now.event = CloseIssue and Who.session = s2 and Now.issue = c.campaignIssue
                and a in Live and not closableWithAgents[c])
  }
}

/* R3c. The global rule, if it could be read, blocks it. The RemoveMember
   scope is a finding, not a convenience: `liveUnder` reads membership OR
   co-location, so moving the sub-issue out and deleting the tree turns the rule
   permissive while the agent still runs, and nothing guards that. */
pred R3c_GlobalCloseRuleBlocks {
  some c: Campaign, disj s1, s2: Session, a: Agent {
    s1.machine != s2.machine
    a.launcher = s1
    always Now.event != RemoveMember
    closeDisciplineFull[c]
    eventually (Now.event = CloseIssue and Now.issue = c.campaignIssue and Who.session = s2 and a in Live)
  }
}

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
   it per sub-issue, so two sessions on the SAME sub-issue still share a branch. */
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
   stands until someone deletes it by hand. Probed 2026-09-04: `take 1 154
   <topic>` exits 3 `already claimed` though #154 closed as completed via #162.
   A sub-issue that has been settled can therefore never be re-worked, which is
   not a policy anyone chose.

   The claim ends where the work does. This is the same reading `release`
   already makes on the merged path -- a branch whose pull request merged is
   finished work and not a fresh claim -- stated once, here, so `take` and
   `release` cannot drift about when a ref stops meaning "somebody holds this".

   SPELLED ON `Claim` AND NOT ON `CloseIssue`, and the first draft got that
   wrong in a way worth keeping written down. Written as "a close leaves the
   issue unclaimed", and with `closeIssue` framing `Claimed' = Claimed`, it
   reduced to "no sub-issue may close while it is claimed" -- which FORBIDS THE
   ORDINARY LANDING the code makes every time: the pull request merges, GitHub
   auto-closes the sub-issue with its ref still standing, and `release` deletes
   the ref afterwards. The spec said the code's happy path was illegal, and two
   comments in `campaign-claim.py` cited it as the statement they follow.

   What the code actually reads is on the TAKE side: a second claim on an
   already-claimed sub-issue is admitted exactly when the first is residue of a
   merged pull request. That is `partition_refs`, and it is what makes
   reopen-then-take work.

   `some ... .pullRequest` IS LOAD-BEARING and was missing. `none in Merged`
   holds vacuously in Alloy, so without it the rule also admitted a second claim
   on a sub-issue with NO pull request at all -- which `partition_refs` refuses,
   since a ref with no merged pull request is a live claim. The comment said
   "exactly when", and it was not exactly. R9e is the control for that branch;
   without the conjunct it goes SAT. */
pred settledLeavesNoClaim {
  always (Now.event = Claim and Now.issue in Claimed
            implies (some Now.issue.pullRequest
                     and Now.issue.pullRequest in Merged))
}

/* R8. THE DEFECT #187 FIXES, in the smallest world that holds it: one
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
   anything -- which is what happened the first time it was written, as a
   conjunct of `claim` itself, where no scenario could violate it. */
pred R8b_RepairExcludesIt {
  claimOnTheIssuesRepo
  R8_ClaimCutOnAnotherRepo
}

/* R8c. ...and the repair still admits the ordinary claim, or it would be a
   rule that forbids everything. */
pred R8c_RepairAdmitsTheOrdinaryClaim {
  claimOnTheIssuesRepo and claimAtomic
  some i: Issue | eventually (Now.event = Claim and Now.issue = i)
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
   rule refuses the only thing a member repository is for. */
pred R14c_ScopeAdmitsTheListedMember {
  claimWithinScope and claimAtomic and claimOnTheIssuesRepo
  some c: Campaign, i: Issue |
    eventually (Now.event = Claim and Now.issue = i and i in c.memberIssues
                and i.repo != Base and i.repo in c.reposInBody)
}

/* R14d. THE LIVE DEFECT #203 IS FOR, and the one command of these four that
   was missing when the reader shipped. The campaign has a member repository,
   so `## Repos` is NOT empty -- which is what separates this from
   `R4_RepolessCampaign`, whose list is empty and which therefore passes a
   reader that admits the base only by way of `none`. The sub-issue lands in
   the base, the list does not hold the base, and the claim must still be cut.
   Expects 1 WITH the rule asserted: dropping the `Base` disjunct from
   `claimWithinScope` makes it UNSAT, which is the shape campaign-claim.py was
   in between #187 and #203. */
/* R14e. WHOSE list, pinned. Every command above runs at `1 Campaign`, where
   `campaignOf[Now.issue].reposInBody` and `Campaign.reposInBody` are the same
   relation and the choice between them is free -- so the four of them together
   say nothing about which campaign's scope a claim is judged against. Two
   campaigns, and the sub-issue's OWN parent does not list its repository while
   the other campaign does. Replacing `campaignOf[Now.issue]` with `Campaign`
   in `claimWithinScope` makes this SAT and moves no other verdict, which is
   the only thing that tells the two readings apart.

   The reader makes exactly this mistake in the other direction -- it judges
   against the campaign the caller typed, not the parent -- which is
   kalaluthien/campaign-base#206 and not something this command can fix. */
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

/* R7e. CONTROL FOR THE `settled` DISJUNCT #187 Q2 added: a sub-issue DROPPED
   as not planned, whose claim nobody was ever launched on, must be releasable.
   This is the case `--confirmed-absent WHO` used to be the only door for, and
   it is the door GitHub already answers: an issue closed as not planned says
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

/* R11. A HOLDER ATTRIBUTED THROUGH ANOTHER CAMPAIGN'S DIRECTORY (#187
   question 4). `holder` reaches a checkout through `campaignDirAt[campaignOf[i],
   host]`, and directory/system.als says that is the one way to reach a
   campaign's directory -- so a sub-issue's holder must stand in ITS OWN
   campaign's directory, never in a neighbour's on the same machine.

   That statement was in the model and pinned by nothing: dropping the campaign
   filter from `campaignDirAt` left all 162 commands green. The script had
   drifted the same way for the same reason -- `campaign_clones` walked EVERY
   campaign directory at the base root, so one with an unreadable `repos/`
   denied `live` and `release` for every other campaign on the machine, and a
   clone belonging to a neighbour counted toward this campaign's sweep.

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

/* A DELEGATE IS LAUNCHED INTO A CLONE THAT CARRIES THE PRINCIPLES (#187
   question 5). A delegate has no session of its own to be named and reads no
   ancestor instruction file behind a dialog that defaults to declining, so the
   `CLAUDE.local.md` in its cwd is the whole channel. #176 wrote that channel
   down as prose and no command wrote the file, which is the shape of a rule
   that is remembered rather than enforced -- and one nothing observes, since a
   delegate that received nothing looks exactly like one that received
   everything and ignored it.

   Delegates only. A session launching an in-process subagent, or working by its
   own hands, already has the campaign's instructions loaded by its own harness. */
pred delegateLaunchIsPrincipled {
  always all a: Agent |
    (a not in Launched and a in Launched' and no a.peer)
      implies a.task.repo in campaignDirAt[campaignOf[a.task], a.host].principled'
}

/* R12. The defect: a delegate launched into a clone carrying nothing. */
pred R12_DelegateLaunchedWithoutPrinciples {
  some a: Agent {
    no a.peer
    eventually (a not in Launched and a in Launched'
                and a.task.repo not in
                    campaignDirAt[campaignOf[a.task], a.host].principled')
  }
}

/* R12b. CONTROL: the discipline excludes it. */
pred R12b_RepairExcludesIt {
  delegateLaunchIsPrincipled and R12_DelegateLaunchedWithoutPrinciples
}

/* R12c. ...and it still admits the launch that DID carry them, or the rule
   would be one that forbids every delegate. */
pred R12c_RepairAdmitsThePrincipledLaunch {
  delegateLaunchIsPrincipled
  some a: Agent {
    no a.peer
    eventually (a not in Launched and a in Launched'
                and a.task.repo in
                    campaignDirAt[campaignOf[a.task], a.host].principled')
  }
}

/* R12d. ACQUIRE IS WHAT PRINCIPLES A CLONE, pinned. R12c is satisfied by a
   `principled` that was simply true at time zero, so it says nothing about
   WHERE principles come from -- and while `acquire` did not write the field,
   nothing in the model did. Starting from nothing principled, a principled
   launch is reachable only through an Acquire. Goes UNSAT when `acquire` stops
   producing. */
pred R12d_AcquireIsWhatPrinciplesAClone {
  no principled
  some a: Agent {
    no a.peer
    eventually (a not in Launched and a in Launched'
                and a.task.repo in
                    campaignDirAt[campaignOf[a.task], a.host].principled')
  }
}

/* R12e. WHICH HOST, pinned. `campaignDirAt[c, m]` filters on two columns and
   R11 pins only the campaign, so at `1 Machine` -- which is every command
   above -- `campaignDirAt[campaignOf[a.task], a.host]` and
   `campaignDirsOf[campaignOf[a.task]]` are the same relation. Nothing said the
   principles have to be in the directory on the machine the delegate RUNS on,
   and one campaign directory per machine is exactly the shape that has two.
   Measured on the #190 branch at 1836881, by a reviewer and by the author:
   replacing the navigation with `campaignDirsOf[campaignOf[a.task]]` left all
   78 commands in this module green.

   Two machines, one campaign: the directory on the agent's own host does not
   carry the principles and the one on the other machine does, and the rule must
   still refuse. Expect 0, and it goes SAT the moment `a.host` stops filtering.
   R13g is this command one field over, for `gated`.

   `some campaignOf[a.task]` is deliberately NOT a conjunct: the last one
   implies it, since `campaignDirAt[none, m]` is empty and `x in none` is false.
   An expect-0 witness pays for every redundant conjunct, which can make it
   UNSAT for a reason that is not the one under test. */
pred R12e_TheAgentsOwnHostIsTheOneThatCounts {
  delegateLaunchIsPrincipled
  some a: Agent, m: Machine {
    no a.peer
    eventually (a not in Launched and a in Launched'
                and m != a.host
                and a.task.repo not in
                    campaignDirAt[campaignOf[a.task], a.host].principled'
                and a.task.repo in
                    campaignDirAt[campaignOf[a.task], m].principled')
  }
}

/* R12f. AND NOTHING BUT AN ACQUIRE PRINCIPLES A CLONE. R12d says a principled
   launch is REACHABLE from `no principled`, and reachability is satisfied by
   ANY producer -- so what R12d reads as "acquire is where principles come
   from" actually rests on `principled' = principled` holding in
   `directoryFrame`, which no command asked for. Measured the same way:
   deleting that line freed `principled` on every event outside the directory
   entity and left all 78 commands green.

   The other half, and the pair is what pins the field: from nothing
   principled, with no Acquire ever firing, a principled launch is IMPOSSIBLE.
   Expect 0, and it goes SAT the moment the frame stops carrying `principled`.
   R13h is this command one field over.

   The rule is NOT asserted here, as in R12d and R13h: what is under test is
   what the transition system can produce, and adding the rule would make the
   command UNSAT for the rule's reason as well as the frame's. */
pred R12f_NothingButAnAcquirePrinciplesAClone {
  no principled
  always Now.event != Acquire
  some a: Agent {
    no a.peer
    eventually (a not in Launched and a in Launched'
                and a.task.repo in
                    campaignDirAt[campaignOf[a.task], a.host].principled')
  }
}

/* ================= the gate is installed where the commit lands ============= */

/* A COMMIT IS ONLY REFUSABLE WHERE THE GATE IS INSTALLED (#190).
   `claimBeforeCommit` above says a commit on a sub-issue names a claim the
   committer holds. It is silent on whether anything in the checkout the commit
   is made in reads that -- and for a member repository nothing did.
   `acquire-repo.sh` ran a clone's own `scripts/install-hooks.sh` only
   `if [ -x "$installer" ]`, a member repository ships none, so a member clone
   got the machine-wide no-main-commits shim and NO claim gate, while
   check-campaign-claim.py went on calling that same clone campaign work. The
   rule held in the model and enforced nothing on the trees delegates do most of
   their committing in. That is the shape #187 question 5 hit with the
   principles channel: a mechanism that existed only as prose.

   NARROWED TO A TASK THAT HAS A CAMPAIGN, deliberately, and the reason is
   about this model and not about the script. Without the conjunct the rule
   forbids a commit whose task belongs to no campaign -- `campaignOf` is `lone`,
   `campaignDirAt[none, m]` is empty, and `x in none` is FALSE -- so it would
   refuse by vacuity rather than by anything it claims. A rule wider than what
   it can justify is false, not cautious.

   DO NOT justify this by check-commit-claim.py admitting such a commit: that
   was the first spelling of this comment and it is wrong. The script reads the
   committing checkout's PATH, and this entity carries none -- `CommitLocal`
   names an agent and an issue and no location, and `launch` reaches a checkout
   through `Who.session.worksOn` rather than through `campaignOf[a.task]`, so
   the two are free of one another here (R13e's witness rests on exactly that
   freedom). "The issue has no campaign" and "the checkout is outside every base
   tree" are two different readings, and the model cannot state that they
   coincide. What the script does with a commit it cannot place is its
   docstring's. R13f is this narrowing's witness. */
pred commitGateInstalled {
  always all a: Agent |
    (Now.event = CommitLocal and Target.agent = a and some campaignOf[a.task])
      implies a.task.repo in campaignDirAt[campaignOf[a.task], a.host].gated
}

/* R13. THE DEFECT, without the rule: a commit on campaign work in a clone that
   runs nothing. `claimBeforeCommit` is asserted throughout, so a reader can see
   what this is not -- the claim rule is holding perfectly, over a tree that
   enforces it on nobody. */
pred R13_CommitInAnUngatedClone {
  claimBeforeCommit
  some a: Agent | eventually (Now.event = CommitLocal and Target.agent = a
                              and some campaignOf[a.task]
                              and a.task.repo not in
                                  campaignDirAt[campaignOf[a.task], a.host].gated)
}

/* R13b. CONTROL: the discipline excludes it. */
pred R13b_RepairExcludesIt {
  commitGateInstalled and R13_CommitInAnUngatedClone
}

/* R13c. ...and it still admits the commit in a gated clone, or the rule would
   be one that forbids committing at all. */
pred R13c_RepairAdmitsTheGatedCommit {
  commitGateInstalled
  some a: Agent | eventually (Now.event = CommitLocal and Target.agent = a
                              and some campaignOf[a.task]
                              and a.task.repo in
                                  campaignDirAt[campaignOf[a.task], a.host].gated)
}

/* R13d. ACQUIRE IS WHAT GATES A CLONE, pinned -- R12d's lesson taken up front
   rather than after a review. R13c is satisfied by a `gated` that was simply
   true at time zero, so on its own it says nothing about where the gate comes
   from. Starting from nothing gated, a gated commit is reachable only through
   an Acquire, so this goes UNSAT the moment `acquire` stops producing. */
pred R13d_AcquireIsWhatGatesAClone {
  no gated
  commitGateInstalled
  some a: Agent | eventually (Now.event = CommitLocal and Target.agent = a
                              and some campaignOf[a.task]
                              and a.task.repo in
                                  campaignDirAt[campaignOf[a.task], a.host].gated)
}

/* R13e. WHOSE directory, pinned. Every command above runs at `1 Campaign` and
   `1 CampaignDir`, where `campaignDirAt[campaignOf[a.task], a.host].gated` and
   `CampaignDir.gated` are the same relation -- so together they say nothing
   about which directory the gate has to be in, and #203 is the round that cost
   was paid in. R11 pins the campaign filter inside `campaignDirAt`; this pins
   that THIS rule goes through it.

   Two campaigns on one machine: the agent's own campaign's clone is ungated
   and a neighbour's clone of the same repository is gated, and the rule must
   still refuse. Expect 0, and it goes SAT the moment the navigation is replaced
   by `CampaignDir.gated`.

   EVERY conjunct sits inside the `eventually`, including `some campaignOf` and
   `c != campaignOf[a.task]`. `memberIssues` is a var relation, so stated
   outside it they are read at time zero and a trace that moves the sub-issue
   out of its campaign before the commit satisfies the witness while the rule's
   antecedent is false -- which is exactly how the first spelling of this went
   SAT. */
pred R13e_TheAgentsOwnDirIsTheOneThatCounts {
  commitGateInstalled
  some a: Agent, c: Campaign |
    eventually (Now.event = CommitLocal and Target.agent = a
                and some campaignOf[a.task]
                and c != campaignOf[a.task]
                and a.task.repo not in
                    campaignDirAt[campaignOf[a.task], a.host].gated
                and a.task.repo in campaignDirAt[c, a.host].gated)
}

/* R13f. THE CASE THE RULE DOES NOT COVER, stated rather than left to the
   reader of the conjunct: an agent committing on a task that belongs to no
   campaign is admitted with nothing gated anywhere, because that is what
   check-commit-claim.py does with a checkout outside every base tree and every
   campaign directory. Without this the narrowing above reads as a silent loss.
   Expect 1, and it goes UNSAT if `some campaignOf[a.task]` is dropped from the
   rule. */
pred R13f_ACommitOnNoCampaignsWorkIsNotGated {
  commitGateInstalled
  no gated
  some a: Agent | eventually (Now.event = CommitLocal and Target.agent = a
                              and no campaignOf[a.task])
}

/* R13g. WHICH HOST, pinned -- #203's lesson one axis over, and the axis R13e
   did not reach. `campaignDirAt[c, m]` filters on two columns, and R11 and R13e
   between them pin only the campaign. Every command above runs at `1 Machine`,
   where `campaignDirAt[campaignOf[a.task], a.host]` and
   `campaignDirsOf[campaignOf[a.task]]` are the same relation, so nothing said
   the gate has to be installed on the machine the commit is MADE on -- and one
   campaign directory per machine is exactly the shape that has two of them.

   Two machines, one campaign: the directory on the agent's own host has the
   repository ungated and the one on the other machine has it gated, and the
   rule must still refuse. Expect 0, and it goes SAT the moment `a.host` stops
   filtering.

   `principled` had the same gap at `delegateLaunchIsPrincipled`, measured on
   the #190 branch and closed by R12e above (#212). */
pred R13g_TheAgentsOwnHostIsTheOneThatCounts {
  commitGateInstalled
  some a: Agent, m: Machine |
    eventually (Now.event = CommitLocal and Target.agent = a
                and some campaignOf[a.task]
                and m != a.host
                and a.task.repo not in
                    campaignDirAt[campaignOf[a.task], a.host].gated
                and a.task.repo in campaignDirAt[campaignOf[a.task], m].gated)
}

/* R13h. AND NOTHING BUT AN ACQUIRE GATES A CLONE. R13d says a gated commit is
   REACHABLE from `no gated`, which is satisfied by any producer at all -- so it
   rests on `gated' = gated` holding in `directoryFrame`, and deleting that line
   left R13 through R13g green while `gated` became free on every event outside
   this entity. This is the other half: from nothing gated, with no Acquire ever
   firing, a gated commit is IMPOSSIBLE. Expect 0, and it goes SAT the moment
   the frame stops carrying `gated`.

   `principled` was unframed in the same way and by the same measurement;
   R12f above is that half, added by #212 rather than by #190, because
   widening R12 was that command's business and not this one's. */
pred R13h_NothingButAnAcquireGatesAClone {
  no gated
  always Now.event != Acquire
  some a: Agent | eventually (Now.event = CommitLocal and Target.agent = a
                              and some campaignOf[a.task]
                              and a.task.repo in
                                  campaignDirAt[campaignOf[a.task], a.host].gated)
}

/* R9d. THE ORDINARY LANDING, and the case whose absence let the first spelling
   of `settledLeavesNoClaim` through: claim, merge, and the sub-issue closes
   with its ref still standing, because GitHub auto-closes on merge and
   `release` runs afterwards. Spelled on CloseIssue, the rule made this UNSAT --
   the spec forbidding what the code does every time, with two comments in
   `campaign-claim.py` citing it as what they follow. A discipline needs a
   witness for the path it must NOT block, not only for the one it must. */
pred R9d_OrdinaryLandingStillAllowed {
  settledLeavesNoClaim
  some i: Issue | eventually (Now.event = Claim and Now.issue = i
                              and eventually (Now.event = CloseIssue
                                              and Now.issue = i
                                              and i in Claimed))
}

/* R9e. THE BRANCH THE FIRST SPELLING LEFT OPEN: a second claim on a sub-issue
   that is claimed and has NO pull request at all. `none in Merged` is vacuously
   true, so the rule admitted it and no case said otherwise -- R9's witness asks
   for `pullRequest not in Merged`, which is FALSE of an empty pullRequest, so
   R9 and R9b never reached this shape. The code refuses it: a ref with no
   merged pull request is a live claim, and `partition_refs` puts it in `held`.
   Expect 0, and it goes SAT the moment the `some` conjunct is dropped. */
pred R9e_SecondClaimOnAPullRequestLessSubIssue {
  settledLeavesNoClaim
  some i: Issue | eventually (Now.event = Claim and Now.issue = i
                              and i in Claimed and no i.pullRequest)
}

/* R4h. THE HOLE, and the one this campaign actually fell into: a session works
   its own sub-issue and no claim of it ever exists, so every peer reading the
   records sees an open sub-issue indistinguishable from one nobody started. */
pred R4h_OwnHandsWorkWithoutClaim {
  some s: Session, a: Agent {
    a.peer = s
    eventually (Now.event = Work and Target.agent = a)
    always a.task not in s.claimedIssues
  }
}

/* R4i. The guard closes it. */
pred R4i_GuardClosesOwnHandsGap {
  claimBeforeWork
  R4h_OwnHandsWorkWithoutClaim
}

/* R4j. CONTROL for R4i: UNSAT there would mean the guard forbids the session
   from working at all rather than from working unclaimed. */
/* R15. THE GUARD THAT JUDGED AND WROTE NOTHING. Work happens and no verdict
   about it is on disk afterwards -- the state every one of this guard's false
   positives was found in. */
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

pred R4j_GuardAdmitsClaimedWork {
  claimBeforeWork
  some s: Session, a: Agent {
    a.peer = s
    eventually (Now.event = Claim and Who.session = s and Now.issue = a.task
                and eventually (Now.event = Work and Target.agent = a))
  }
}

/* ============== permission by role, one witness per table cell ============== */

/* Q11. #207: a worker writes its OWN campaign's issue, which is no
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
   bound to the same machine. SAT: the relaxation in `sessionClaim`.

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


/* Q1. THE CASE THAT PROMPTED #185: a planner of campaign #1 closes an issue no
   campaign of its own covers -- #116 and #160, closed by hand outside the
   harness on 2026-09-04 because the claim rule had no passing form for them. */
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
   my memberIssues", which is what it said until #207: the campaign issue of
   the session's OWN campaign is also outside `memberIssues`, so the old
   spelling started matching the one write the rule now permits and this
   command went SAT while measuring nothing it was named for.

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

/* Q4b. Its own campaign, a sibling sub-issue it never claimed. UNSAT, and the
   one that separates the two halves of the worker's campaign-plane row. */
pred Q4b_WorkerClosesUnclaimedSibling {
  permissionByRole
  some s: Session | s.role = Worker and
    eventually (Now.event = CloseIssue and Who.session = s
                and Now.issue in s.worksOn.memberIssues
                and Now.issue not in s.claimedIssues)
}

/* Q5. R4j under the discipline: claimed work still runs. */
pred Q5_WorkerWorksClaimedCheckout {
  permissionByRole
  some s: Session, a: Agent {
    s.role = Worker and a.peer = s
    eventually (Now.event = Claim and Who.session = s and Now.issue = a.task
                and eventually (Now.event = Work and Target.agent = a))
  }
}

/* Q6. R4h under the discipline. UNSAT: the same hole `claimBeforeWork` closes,
   closed again by the rule that subsumes it. */
pred Q6_WorkerWorksUnclaimed {
  permissionByRole
  some s: Session, a: Agent {
    s.role = Worker and a.peer = s
    eventually (Now.event = Work and Target.agent = a)
    always a.task not in s.claimedIssues
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

/* R5b. The gap TwoStepShutdownSuffices rests on is reachable at all. */
pred R5b_PushedButStillLocalOnly { some a: Agent | eventually (a in PushedToRemote and a in LocalOnly) }

/* R5c. Ownership is not the axis; co-location is. */
pred R5c_NonLauncherSameMachineIsFine {
  localCheckedShutdown
  some disj s1, s2: Session, a: Agent {
    a.launcher = s1 and a.host = s1.machine and s2.machine = a.host
    eventually (Now.event = StandDown and Who.session = s2 and Target.agent = a)
  }
}

/* R6. A live agent on another machine that has not pushed loses its claim
   under a rule correctly followed. */
pred R6_ReleaseUnderRemoteAgent {
  some s: Session, a: Agent {
    a.host != s.machine
    eventually (a in Live and a not in PushedToRemote
                and Now.event = Release and Who.session = s and Now.issue = a.task)
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

       WIDENED FROM `complete` TO `settled` BY #187 Q2, in step with the rule.
       The moment `releaseNeedsAWorker` admitted a settled sub-issue, the
       solver satisfied this witness by DROPPING the issue instead of merging
       it -- the same escape through a different door, and R7b went SAT again.
       An exclusion has to name the whole disjunct it is excluding, not the
       half that existed when it was written. */
    always not settled[i]
    eventually (Now.event = Claim and Now.issue = i
                and after eventually (Now.event = Release and Now.issue = i))
  }
}

/* R7b. The discipline closes it. */
pred R7b_WorkerRuleClosesTheFreshClaim {
  releaseNeedsAWorker and R7a_FreshClaimReleasedWithNoAgent
}

/* R7c. CONTROL FOR THE `Launched` DISJUNCT: an agent was launched on this
   sub-issue and is gone, which is the release the sweep actually makes.
   `always not complete` is load-bearing -- without it the solver satisfies
   this through the OTHER disjunct, and deleting `Launched` from the rule left
   both this and R7b green, pinning neither. */
pred R7c_WorkerRuleAdmitsTheOrdinaryRelease {
  releaseNeedsAWorker
  some a: Agent {
    always not settled[a.task]     -- widened with the rule; see R7a
    eventually (a in Launched and a not in Live and a not in PushedToRemote
                and Now.event = Release and Now.issue = a.task)
  }
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

/* N2. CONTROL, and the direction that must NOT be exempted: a session whose
   name says nothing is not evidence, so it still blocks. Making the absent
   name exempt too would empty the gate. */
pred N2_UnnamedSessionStillBlocks {
  some c: Campaign, s: Session, a: Agent, m: Machine {
    a.peer = s and a.host = m and s.machine = m
    always no s.campaignNamed
    /* ...AND UNDER THE BASE TREE, since #187 question 6. An absent name is not
       evidence either way, so the cwd is what ties the session to this machine's
       campaigns; N7 is the same session outside the tree, which does NOT block. */
    always s in UnderBase
    /* `a.task not in c.memberIssues` is load-bearing: without it the witness
       blocks through the FIRST disjunct -- an agent on a sub-issue of this
       campaign blocks whatever it is called -- and says nothing about whether
       an absent name exempts the machine-wide one. Making the absent name
       exempt then left this green. */
    eventually (a in Live and m in machinesHolding[c]
                and a.task not in c.memberIssues
                and liveUnderLocally[c, m])
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

/* github's `closable` reads `settled` and nothing else, so a campaign whose
   sub-issues are all closed is closable with claim refs still standing on the
   remote. Most are harmless -- a merged pull request's head outlives it here,
   `delete_branch_on_merge` being off -- and the rest are a claim nobody
   retired, which the next `take` on that sub-issue then refuses forever. */
pred noStrayClaims[c: Campaign] {
  all i: c.memberIssues | i in Claimed implies complete[i]
}

/* N7. THE RESIDUAL #187 QUESTION 6 LEAVES, stated rather than left as a gap in
   a comment. A live session of this campaign that renamed to nothing AND left
   the base tree does not block a close: nothing observable ties it here, and
   blocking on it would block on it for every campaign on the machine at once.
   It is a real hole -- that session is asked by nobody -- and this is the
   witness that makes it findable instead of surprising.

   Expect 1, and it is the pair of N2: the same unnamed session, in the tree and
   out of it, blocking and not. */
pred N7_UnnamedSessionOutsideTheTreeDoesNotBlock {
  some c: Campaign, s: Session, a: Agent, m: Machine {
    a.peer = s and a.host = m and s.machine = m
    always no s.campaignNamed
    always s not in UnderBase
    eventually (a in Live and m in machinesHolding[c]
                and a.task not in c.memberIssues
                and not liveUnderLocally[c, m])
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
  coLocatedShutdown and twoStepShutdown
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

/* =================== deleting a tree under an agent =================== */

/* A10. session/scenarios.als's R3 reached from here: a directory is deleted
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

/* A6. The other chair. A confirmation checks that the work EXISTS, never that
   it is right, so with A4 this pair says the rule's subject is the review. */
pred A6_UnreviewedMerge {
  some c: Campaign, s: Session, a: Agent {
    a.task in c.memberIssues
    s != a.peer
    always s.worksOn = c
    eventually (Now.event = MergePullRequest and Who.session = s and Now.issue = a.task
                and a in Confirmed and no a.task.pullRequest & Reviewed)
  }
}

pred A7_ReviewRuleBlocksUnreviewed { mergedOnCurrentReview and A6_UnreviewedMerge }

/* A8. Control for A5 and A7: neither is green by forbidding merges. */
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

/* A16. THE ONE-SESSION LANDING, admitted. Run at exactly one Session so the
   absence of a second merger is the scope and not an accident. */
pred A16_AuthorLandsOwnReviewedWork {
  mergedOnCurrentReview
  some s: Session, a: Agent {
    a.peer = s
    eventually (Now.event = Push and Target.agent = a)
    eventually (Now.event = Review and Who.session = s and Now.issue = a.task)
    eventually (Now.event = Confirm and Who.session = s and Target.agent = a)
    eventually (Now.event = MergePullRequest and Who.session = s and Now.issue = a.task)
  }
}

/* A16b. The author gets no special door. Letting `push` keep `Reviewed` turns
   this SAT, so the currency half of the rule is `push`'s clearing line. */
pred A16b_AuthorCannotMergeOnStaleReview {
  mergedOnCurrentReview
  some s: Session, a: Agent {
    a.peer = s
    eventually (Now.event = Review and Now.issue = a.task
                and after eventually (Now.event = Push and Target.agent = a
                                      and after ((always Now.event != Review)
                                                 and eventually (Now.event = MergePullRequest
                                                                 and Now.issue = a.task))))
  }
}

/* A18. Hands-on work is no Agent at all. It matters because the confirm
   conjunct ranges over `agentsOf[Now.issue]`, empty here, so it is
   VACUOUSLY true and the review half holds the rule up alone -- which A16,
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

/* ---------------- commands ---------------- */

-- one sub-issue, one session, no planner
run P1_SimpleRequestSettlesWithoutPlanner for 3 Issue, 1 PullRequest, 1 Campaign, exactly 1 Session, exactly 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1
-- a planner's delegate does work
run P2_PlannerLaunchesDelegate           for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1

-- the whole retirement procedure runs
run Sanity                          for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Session, exactly 1 Agent, exactly 1 Machine, exactly 2 Repo, exactly 1 Branch, 1 CampaignDir, 12 steps expect 1
-- a REPORT changes nothing durable
run ReportIsNotEvidence             for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Session, exactly 1 Agent, exactly 1 Machine, exactly 2 Repo, exactly 1 Branch, 1 CampaignDir, 10 steps expect 1
-- BLOCKED stops the agent
run BlockedAgentDoesNotProceed      for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Session, exactly 1 Agent, exactly 1 Machine, exactly 2 Repo, exactly 1 Branch, 1 CampaignDir, 10 steps expect 1
-- wait-for-the-answer strands a pane
run SilentAgentIsRetirableUnderWait for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Session, exactly 1 Agent, exactly 1 Machine, exactly 2 Repo, exactly 1 Branch, 1 CampaignDir, 12 steps expect 0
-- rule 3's repair still retires it
run SilentAgentStillRetired         for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Session, exactly 1 Agent, exactly 1 Machine, exactly 2 Repo, exactly 1 Branch, 1 CampaignDir, 12 steps expect 1

run S3_DelegateDiesAfterPushing for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Session, exactly 1 Agent, exactly 1 Machine, exactly 2 Repo, exactly 1 Branch, 1 CampaignDir, 12 steps expect 1
run S4_ReportWithoutPush        for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Session, exactly 1 Agent, exactly 1 Machine, exactly 2 Repo, exactly 1 Branch, 1 CampaignDir, 12 steps expect 1
run S9_OrphanedByLocalDelete    for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Session, exactly 1 Agent, exactly 1 Machine, exactly 2 Repo, exactly 1 Branch, 1 CampaignDir, 12 steps expect 1

-- a close over a delegate on M1
run R3b_CloseFromAnotherMachine  for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
-- the global rule would block it
run R3c_GlobalCloseRuleBlocks    for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0

-- an acquire moves a live role's HEAD
run R4c_CheckoutSwitchedUnderAgent for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 3 Repo, 2 Branch, 1 CampaignDir, 12 steps expect 1
-- what the numbered branch leaves
run R4e_NumberedBranchStillShared for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- a session named for another campaign does not block this campaign's close
run N1_ForeignNamedSessionDoesNotBlock       for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
-- control: a session whose name says nothing still blocks
run N2_UnnamedSessionStillBlocks             for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run N7_UnnamedSessionOutsideTheTreeDoesNotBlock for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
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
-- control: the ordinary release still happens, through the `Launched` disjunct
run R7c_WorkerRuleAdmitsTheOrdinaryRelease for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1
-- ...and hands-on work still releases, through the `complete` one, at `0 Agent`
run R7d_WorkerRuleAdmitsTheAgentLessLanding for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 0 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1
-- the claim closes it
run R4f_ClaimClosesSameSubIssue    for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
-- control: the 422 is load-bearing
run R4g_ClaimWithoutAtomicityStillShared for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R8_ClaimCutOnAnotherRepo for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R8b_RepairExcludesIt for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run R8c_RepairAdmitsTheOrdinaryClaim for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
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
run R12_DelegateLaunchedWithoutPrinciples for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run R12b_RepairExcludesIt for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 0
run R12c_RepairAdmitsThePrincipledLaunch for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run R12d_AcquireIsWhatPrinciplesAClone for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R12e_TheAgentsOwnHostIsTheOneThatCounts for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
run R12f_NothingButAnAcquirePrinciplesAClone for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run R13_CommitInAnUngatedClone for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R13b_RepairExcludesIt for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run R13c_RepairAdmitsTheGatedCommit for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R13d_AcquireIsWhatGatesAClone for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R13e_TheAgentsOwnDirIsTheOneThatCounts for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
run R13f_ACommitOnNoCampaignsWorkIsNotGated for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R13g_TheAgentsOwnHostIsTheOneThatCounts for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
run R13h_NothingButAnAcquireGatesAClone for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
-- the own-hands hole, the guard that closes it, and the control
run R4h_OwnHandsWorkWithoutClaim for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run R4i_GuardClosesOwnHandsGap   for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run R4j_GuardAdmitsClaimedWork   for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- #196: the gate leaves a record, and the record does not forbid the work
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
-- the case that prompted #185: a planner closes another campaign's issue
run Q1_PlannerClosesOtherCampaignsIssue   for 4 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
-- a planner never commits, and the CONTROL says which rule forbids it
run Q2_PlannerCommits                     for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
run Q2c_PlannerCommitsUnguarded           for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
-- a worker on its own claim
run Q3_WorkerClosesOwnClaim             for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- and not on another campaign's, nor on an unclaimed sibling
run Q4_WorkerClosesOtherCampaign        for 4 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
run Q4b_WorkerClosesUnclaimedSibling    for 4 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
-- R4j and R4h again, under the rule that subsumes claimBeforeWork
run Q5_WorkerWorksClaimedCheckout       for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
run Q6_WorkerWorksUnclaimed             for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
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
-- #207: the carve-out is what makes this write reachable at all
run Q11_WorkerWritesItsOwnCampaignIssue    for 5 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
run Q10_PlannerClaimsOnAnotherBoundCampaign  for 5 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
run Q10b_WorkerClaimsOnAnotherBoundCampaign for 5 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0
run Q10c_WorkerClaimsOnAnotherBoundCampaignUnguarded for 5 Issue, 1 PullRequest, 2 Campaign, 1 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 0

-- the gap TwoStepShutdownSuffices rests on
run R5b_PushedButStillLocalOnly         for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
-- co-location, not ownership, is the axis
run R5c_NonLauncherSameMachineIsFine for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- a local release under a remote agent
run R6_ReleaseUnderRemoteAgent   for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
-- a dangling claim is reclaimable
run R6b_ReclaimAfterDeath        for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 14 steps expect 1

/* A1 and A3 run at two Sessions, so the derived reading is choosing between
   them. A10-A12 need a CampaignDir to delete mid-trace. A16, A16b, A18 and
   A18b run at exactly ONE Session, because the absence of a second merger is
   their subject. */
-- the holder read off the checkout, with no record anywhere
run A1_HolderReadFromTheCheckout          for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- control: the whole run still happens
run A3_HolderRunsTheWholeProtocol         for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1
-- the live collision: a self-merge with NO review
run A4_AgentMergesItsOwnPullRequest                for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1
-- still caught, by what was missing
run A5_ReviewRuleBlocksTheCollision          for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 0
-- the same merge from the other chair
run A6_UnreviewedMerge                       for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- nobody merges unread
run A7_ReviewRuleBlocksUnreviewed            for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
-- control: two-session landing runs
run A8_ReviewRuleAdmitsTheLanding            for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1

-- session/scenarios.als's R3, reached from here
run A10_DeleteUnderLiveAgent      for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- and closed by reading liveness
run A11_LiveGateBlocksTheDelete   for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0
-- control
run A12_LiveGateAdmitsTheDelete   for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- a push retires a review
run A13_PushAfterReviewUnReviews             for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1
-- the one-session landing
run A16_AuthorLandsOwnReviewedWork           for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1
-- and a push retires that permission
run A16b_AuthorCannotMergeOnStaleReview      for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 0
-- the derived reading's one residual gap: live, listed, checkout moved off
run A17_LiveButNoLongerTheHolder             for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- hands-on work, reviewed and merged by one session, at `0 Agent`
run A18_AgentLessLandingIsAdmitted           for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 0 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- and unreviewed it does not land. The pair matters because the confirm conjunct is VACUOUS at `0 Agent`, so the review half holds the rule up alone
run A18b_AgentLessUnreviewedMergeIsBlocked   for 3 Issue, 1 PullRequest, 1 Campaign, 1 Session, 0 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 0

