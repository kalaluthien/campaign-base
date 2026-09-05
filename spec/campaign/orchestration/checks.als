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
    implies once (Now.event = Release and Who.session = a1.peer
                  and once (Now.event = Launch and Target.agent = a1))
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
   nothing on the machine reads, since `campaign-assign.py` reads the pane of
   the session being ASSIGNED and a delegate has no pane until its launch makes
   one. So this run going UNSAT is the signal that the model has drifted back
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

-- a release compacts, a launch spends it, so two sub-issues need a release between them
check SessionCompactsBetweenSubIssues for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 2 Branch, 2 CampaignDir, 12 steps expect 0
-- and two sub-issues on one session do happen, so the check above is not vacuous
run P8_TwoSubIssuesOneSession        for 3 Issue, 1 PullRequest, 1 Campaign, 2 Session, 2 Agent, 1 Machine, 3 Repo, 2 Branch, 2 CampaignDir, 12 steps expect 1
-- and a delegate launch is NOT guarded, so one session can work a sub-issue and then launch one
run P9_DelegateAfterOwnSubIssue      for 4 Issue, 1 PullRequest, 1 Campaign, 2 Session, 3 Agent, 1 Machine, 3 Repo, 3 Branch, 2 CampaignDir, 12 steps expect 1
