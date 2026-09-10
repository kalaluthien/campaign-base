/*
 * What must hold of orchestration/system, and the floor that says its events are
 * reachable at all. github/system.als is spec/'s entry point.
 */
module orchestration/checks

open orchestration/scenarios

/* ---------------- properties ---------------- */

/* Nothing written in THIS file carries it, so it tests the composition idiom:
   dropping `githubFrame` from github/system's fall-through branch reddens it. */
assert NoLostWork {
  always all i: Issue |
    (complete[i] and Now.event in AgentDie + DeleteDir) implies after complete[i]
}

/* The counterexample: two machines hold the campaign, the agent is live on
   one, the tree is deleted from the other. The rule is a local check blind to
   the other machine. */
pred noOrphanNow {
  all a: Agent | a in Live implies (some c: Campaign | a.task in c.memberIssues and a.host in machinesHolding[c])
}

assert NoOrphan { always noOrphanNow }

// Dropping the RemoveMember clause reddens it.
assert NoOrphanIfGuarded {
  ((always (Now.event = DeleteDir implies (no a: Agent | a in Live and a.host = Where.machine)))
   and (always (Now.event = RemoveMember implies (no a: Agent | a in Live and a.task = Now.issue))))
  implies (always noOrphanNow)
}

/* A REPORT says nothing about a change made after it. Its counterexample also
   refutes the unguarded protocol, which is why that has no command of its own. */
assert OneStepShutdownSuffices { oneStepShutdown implies noWorkDestroyed }

/* THE REMOTE HOLE: step 2 run from the wrong machine. R5b and R5c pin its
   axis. */
assert TwoStepShutdownSuffices { twoStepShutdown implies noWorkDestroyed }

/* `Confirmed` cleared by any later `work` is what makes this green survive an
   agent that keeps working after being confirmed. */
assert TwoStepCoLocatedSuffices {
  (twoStepShutdown and coLocatedShutdown) implies noWorkDestroyed
}

/* Dropping the ANSWER is safe as long as the confirmation is kept and read on
   the right machine. */
assert SilenceResolutionStaysSafe {
  (resolveSilenceExternally and coLocatedShutdown) implies noWorkDestroyed
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

/* #185's rule subsumes #177's: a session permitted to work an issue holds a
   claim on it, so `claimBeforeWork` needs no separate statement once
   `permissionByRole` holds. Dropping `i in s.claimedIssues` from `mayAct`'s
   code-plane row reddens it. Q5 is the control that the subsumption is not by
   forbidding work altogether. */
assert PermissionImpliesClaimGates { permissionByRole implies claimBeforeWork }

/* ATTRIBUTION, AND WHAT DERIVING IT COSTS. `holder` reads the claim's owner
   off the checkout, so a live agent is its own task's holder exactly while the
   checkout stays on its branch. `Acquire` is what moves one, and nothing
   forbids moving it under a live agent -- R4c is that trace and A17 is the
   state it leaves. Stated as a property rather than a fact because the fact
   would forbid R4c and call the silence safety. */
assert AttributionIsSound { always all a: Live | a in holder[a.task] }

/* The repair, and THREE events have to be refused, each of which un-names the
   holder a different way. `Acquire` moves the checkout out from under the
   agent -- R4c. `DeleteDir` takes the checkout away with the tree -- A10, and
   `noDeleteUnderLiveAgent` is the gate A11 already measures. `RemoveMember`
   empties `campaignOf`, so there is no campaign directory left to read a
   checkout in and the holder set goes empty with the checkout untouched.
   Each conjunct was found by dropping it and reading the counterexample, and
   deleting any one of the three reddens the check below. */
pred holderStaysAttributed {
  always (Now.event = Acquire implies
            no a: Agent | a in Live and a.host = Where.machine
                          and a in holder[a.task] and a.task.repo = Where.repo)
  always (Now.event = RemoveMember implies
            no a: Agent | a in Live and a.task = Now.issue)
  noDeleteUnderLiveAgent
}
assert AttributionIsSoundIfCheckoutHeld {
  holderStaysAttributed implies (always all a: Live | a in holder[a.task])
}

/* Every delegate was launched by its planner: the launching session holds a
   Planner atom on the delegate's sub-issue. Dropping the planner conjunct from
   `launch` reddens it; P2 in scenarios is the control that delegates still
   launch. */
assert DelegateLaunchedByPlanner {
  always all a: Launched | no a.peer implies
    (some p: plannerAgents | p.peer = a.launcher and p.task = a.task)
}

/* A SESSION NEVER TAKES TWO SUB-ISSUES WITHOUT A COMPACTION BETWEEN THEM, and
   it is DERIVED rather than assumed: `launch` spends the bit, only
   `agentRelease` returns it, and `launch` requires it.

   MEASURED 2026-09-05, one clause deleted at a time. Deleting either of
   `launch`'s two clauses reddens THIS command, UNSAT -> SAT. Deleting the
   release's `Compacted' = Compacted + Who.session` does NOT: with nothing to
   return the bit, a session's second launch becomes unreachable and this
   assert stays green over an empty set. So that clause is pinned by P8 below
   and by nothing here, which is the whole reason P8 exists -- a green assert
   is a rule only while its subject is reachable.

   It is the whole rule #198 lands, read at its two ends: `campaign-claim.py
   release` compacting its own pane, and `scripts/campaign-assign.py` refusing
   a pane that has not. */
assert SessionCompactsBetweenSubIssues {
  always all a1, a2: Agent |
    (some a1.peer and a1.peer = a2.peer and a1 != a2
     and Now.event = Launch and Target.agent = a2 and a1 in Launched)
    /* BETWEEN, not merely BEFORE. The nested `once` is what says "after a1 was
       launched": some past instant held a release by this session, and at that
       instant a1 had already been launched. A single `once (Release ...)` --
       which is how this read at 114e71a -- says only that the session released
       at SOME point, which is a weaker claim than the comment above makes and
       true for a release that happened before a1 ever started. It held only
       because nothing else in the model returns the bit; a later event that
       did would leave it green and the comment false. Found by review. */
    /* `a1 in Launched` at the release, and not a nested `once` of a1's
       `Launch`: since #289 an agent also starts by `handoff`, which is no
       `Launch`, and the nested form read a successor's heir as never started
       -- so a successor's release could never come after it and the assert
       went false for a trace doing exactly what it asks -- measured SAT at
       3 Agent, the predecessor, its heir and the successor's next, which is
       why the command below runs at 3. `Launched` only grows, so being in it
       at the release says the release came after. */
    implies once (Now.event = Release and Who.session = a1.peer and a1 in Launched)
}

/* THE HANDOFF (#289), four claims, each reddened by deleting one clause of
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

/* ---------------- reachability floor ---------------- */

pred Cov_LaunchAgent      { eventually (Now.event = Launch and some Target.agent) }
pred Cov_LaunchDelegate   { eventually (Now.event = Launch and no Target.agent.peer) }
pred Cov_Work             { eventually Now.event = Work }
pred Cov_Push             { eventually Now.event = Push }
pred Cov_Status           { eventually Now.event = Status }
pred Cov_Answer           { eventually Now.event = Answer }
pred Cov_Report           { eventually Now.event = Report }
pred Cov_Blocked          { eventually Now.event = Blocked }
pred Cov_Decide           { eventually Now.event = Decide }
pred Cov_Confirm          { eventually Now.event = Confirm }
pred Cov_ConfirmElsewhere { eventually Now.event = ConfirmElsewhere }
pred Cov_Review           { eventually Now.event = Review }
pred Cov_StandDown        { eventually Now.event = StandDown }
pred Cov_Retire           { eventually Now.event = Retire }
pred Cov_AgentDie         { eventually Now.event = AgentDie }
pred Cov_GuardedRelease   { eventually Now.event = Release }
/* Lower entities' events the checks above name, directly or through a
   helper. Their own floor is in their own entity, which does not see what
   this one refines, so the witness has to fire in this composition too. */
pred Cov_DeleteDir        { eventually Now.event = DeleteDir }
pred Cov_RemoveMember     { eventually Now.event = RemoveMember }
pred Cov_Claim            { eventually Now.event = Claim }
pred Cov_Acquire          { eventually Now.event = Acquire }
/* The campaign- and code-plane events the role rule gates, which the plane
   lists behind DisjointPlanes and PermissionImpliesClaimGates name. */
pred Cov_FileCampaignIssue    { eventually Now.event = FileCampaignIssue }
pred Cov_AddMember            { eventually Now.event = AddMember }
pred Cov_CloseIssue           { eventually Now.event = CloseIssue }
pred Cov_WriteBody            { eventually Now.event = WriteBody }
pred Cov_CreateDir            { eventually Now.event = CreateDir }
pred Cov_OpenPullRequest      { eventually Now.event = OpenPullRequest }
pred Cov_CommitLocal          { eventually Now.event = CommitLocal }
/* A handoff that moves work, so the four checks above are not green over a
   handoff of an empty session. */
pred Cov_Handoff          { eventually (Now.event = Handoff and some heldBy[Who.predecessor]) }

/* THE CONTROL THAT THE CLAIM MOVE IS LOAD-BEARING: under the role rule, the
   heir works the sub-issue it was handed, with no claim cut in between.
   Dropping `t->(p.claimedIssues)` from `sessionHandoff` makes this UNSAT,
   since `mayAct` then refuses the heir the code plane. The `until` is the
   whole discriminator: without it the successor claims the sub-issue again
   after the handoff and the run is SAT either way -- measured. */
pred P10_HeirWorksAfterHandoff {
  permissionByRole
  some t: Session, b: Agent | b.peer = t
    and eventually (Now.event = Handoff and Who.session = t
                    and after ((Now.event != Claim)
                               until (Now.event = Work and Target.agent = b)))
}
/* THE CONTROL FOR THE ASSERT ABOVE. Without it, deleting the release's
   `Compacted' = Compacted + Who.session` makes a session's second launch
   unreachable and the assert stays green on a vacuity nobody would read. This
   says two launches by one session do happen, so a green assert is a rule and
   not an empty set. */
/* THE CONTROL FOR THE GUARD'S SCOPE, and P8 cannot be it. P8's two launches
   both have `some peer`, so it is satisfied whether the guard binds on every
   launch or only on a session taking its own claim -- measured, the
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
       run is satisfiable either way -- measured, and it is why the first cut
       of this control caught nothing. Unconditional, the delegate launch needs
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
check NoLostWork        for 3 Issue, 2 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 0
-- nothing enforces the retirement rule
check NoOrphan          for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
-- it does hold once enforced
check NoOrphanIfGuarded for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 0

-- the defect the design records
check OneStepShutdownSuffices    for 2 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
-- two steps run from the wrong machine
check TwoStepShutdownSuffices    for 2 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
-- the contract as AGENTS.md states it
check TwoStepCoLocatedSuffices   for 2 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 0
-- rule 3's repair reopens nothing
check SilenceResolutionStaysSafe for 2 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 0

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
-- and it is once the acquire is refused
check AttributionIsSoundIfCheckoutHeld for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 3 Repo, 2 Branch, 1 CampaignDir, 10 steps expect 0

-- every own event fires in some trace
run Cov_LaunchAgent      for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
-- a delegate launch needs the planner atom beside it, so this runs at 2 Agent
run Cov_LaunchDelegate   for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_Work             for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_Push             for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_Status           for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_Answer           for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_Report           for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_Blocked          for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_Decide           for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_Confirm          for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_ConfirmElsewhere for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_Review           for 3 Issue, 2 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
run Cov_StandDown        for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_Retire           for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_AgentDie         for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_GuardedRelease   for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 3 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
-- and the lower events NoLostWork and NoOrphanIfGuarded name: DeleteDir at the
-- first's scope, which is the wider, and RemoveMember at the second's
run Cov_DeleteDir        for 3 Issue, 2 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run Cov_RemoveMember     for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 2 Machine, 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
-- and the two PermissionImpliesClaimGates and AttributionIsSoundIfCheckoutHeld reach through helpers, at theirs
run Cov_Claim            for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run Cov_Acquire          for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 1 Agent, 1 Machine, 3 Repo, 2 Branch, 1 CampaignDir, 10 steps expect 1
-- and the events the plane lists name, at PermissionImpliesClaimGates' scope
run Cov_FileCampaignIssue    for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run Cov_AddMember            for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run Cov_CloseIssue           for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run Cov_WriteBody            for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run Cov_CreateDir            for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run Cov_OpenPullRequest      for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run Cov_CommitLocal          for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1

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
