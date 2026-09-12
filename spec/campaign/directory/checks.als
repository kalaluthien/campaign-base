/*
 * What a campaign directory's presence and absence buy, and how far behind
 * origin a machine's two base checkouts fall: the witnesses over
 * directory/system, what must hold of it, and the floor for its own events.
 * github/system.als is spec/'s entry point.
 */
module directory/checks

open directory/system

/* ---------------- witnesses ---------------- */

/* Two machines hold the campaign; one deletes its own tree while work
   continues, and the sub-issue still completes. */
pred S7_TwoMachinesOneDeletes {
  one c: Campaign | some i: c.memberIssues {
    #machinesHolding[c] = 2
    mergeClosed[c.memberIssues]
    some m: Machine | eventually (Now.event = DeleteDir and Where.machine = m and m in machinesHolding[c])
    eventually complete[i]
  }
}

/* The reconstitution claim exercised rather than asserted: a whole campaign
   runs with no local directory on any machine. */
pred S15_NoLocalDirectory {
  one c: Campaign {
    always no machinesHolding[c]
    #c.memberIssues = 2
    mergeClosed[c.memberIssues]
    always Now.event not in AddMember + RemoveMember
    eventually (all i: c.memberIssues | complete[i])
    closeDiscipline[c]
    eventually (closable[c] and campaignClosed[c])
  }
}

/* An installed repository is merged into, reached, and the campaign closes:
   the post-merge step exists and a close can follow it (#239). One machine,
   holding the campaign, with the sub-issue's repository installed. */
pred S16_MergeReachesInstall {
  one c: Campaign | one i: c.memberIssues | one m: Machine {
    always m in machinesHolding[c]
    i.repo in m.installed
    reachDiscipline[c]
    closeDiscipline[c]
    eventually (Now.event = MergePullRequest and Now.issue = i)
    eventually (Now.event = Reach and Where.machine = m and Where.repo = i.repo)
    eventually campaignClosed[c]
  }
}

/* ---------------- commands ---------------- */

run S16_MergeReachesInstall     for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Machine, exactly 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run S7_TwoMachinesOneDeletes    for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Machine, exactly 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run S15_NoLocalDirectory        for exactly 3 Issue, 2 PullRequest, exactly 1 Campaign, 1 Machine, exactly 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1


/* ---------------- reachability floor ---------------- */

pred Cov_CreateDir     { eventually Now.event = CreateDir }
pred Cov_DeleteDir     { eventually Now.event = DeleteDir }
pred Cov_Acquire       { eventually Now.event = Acquire }
pred Cov_Reach         { eventually Now.event = Reach }
/* Two github events MergeReachesInstall reaches through its discipline.
   github/checks.als has its own, which does not see this composition. */
pred Cov_MergePullRequest { eventually Now.event = MergePullRequest }
pred Cov_CloseIssue       { eventually Now.event = CloseIssue }

/* ---------------- the post-merge step ---------------- */

/* Under `reachDiscipline`, a merge into a repository installed on a machine
   holding the campaign is followed by a Reach on that machine before the
   campaign closes -- while the machine goes on holding it, which is the
   premise the rule is scoped to, and while the campaign is still open, because
   github/system.als lets a member be added to and merged under a campaign
   already closed, and a merged member to be removed from its campaign before
   the close, and neither trace is this rule's. `releases`, not `until`: the discipline
   forbids the close, it does not demand the Reach, and a trace that merges and
   then stutters forever is one it admits. Without the discipline the same shape has a
   counterexample, and `MergeReachesInstall_Bites` is that counterexample
   demanded rather than assumed: a check whose rule cannot be dropped tests
   nothing. */
pred mergeThenReachBeforeClose[c: Campaign] {
  always (all m: Machine, i: c.memberIssues |
    (Now.event = MergePullRequest and Now.issue = i and i.repo in m.installed
     and not campaignClosed[c] and always (m in machinesHolding[c] and i in c.memberIssues))
    implies ((Now.event = Reach and Where.machine = m and Where.repo = i.repo) releases (not campaignClosed[c])))
}
assert MergeReachesInstall {
  all c: Campaign | (reachDiscipline[c] and closeDiscipline[c]) implies mergeThenReachBeforeClose[c]
}
pred MergeReachesInstall_Bites {
  some c: Campaign | closeDiscipline[c] and not mergeThenReachBeforeClose[c]
}

/* ---------------- commands ---------------- */

-- every own event fires in some trace
run Cov_CreateDir     for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 8 steps expect 1
-- DeleteDir at MachineIndependence's scope, below, which names it
run Cov_DeleteDir     for 4 Issue, 3 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 6 steps expect 1
run Cov_Acquire       for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 8 steps expect 1
run Cov_Reach         for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 8 steps expect 1

-- the post-merge step: holds under the discipline, and has a counterexample without it
check MergeReachesInstall      for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 10 steps expect 0
run MergeReachesInstall_Bites  for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 10 steps expect 1
-- and the two lower events it names, at its scope
run Cov_MergePullRequest  for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 10 steps expect 1
run Cov_CloseIssue        for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 10 steps expect 1

/* ================ the two base checkouts ================ */

/* ---------------- witnesses ---------------- */

/* --- The base as a member of its own campaign --- */

/* Hazard 1, and its remedy: a merged base pull request leaves every outer
   checkout behind origin/main, and only a pull clears it. */
pred S16b_BaseBehindAfterMerge {
  one c: Campaign | some i: c.memberIssues {
    i.repo = Base
    always Now.event not in AddMember + RemoveMember
    mergeClosed[c.memberIssues]
    eventually (Now.event = MergePullRequest and Now.issue = i)
    eventually Machine in BaseBehind
    eventually Now.event = PullBase
    eventually (no BaseBehind and complete[i])
  }
}

/* Hazard 1 left alone: nobody pulls, and nothing says so. */
pred S16c_BehindForever {
  one c: Campaign | some i: c.memberIssues {
    i.repo = Base
    always Now.event != PullBase
    eventually (Now.event = MergePullRequest and Now.issue = i)
    eventually always Machine in BaseBehind
  }
}

/* Hazard 2: the clone is cut while the outer base holds unpushed commits,
   so the delegate reads instructions the campaign session has superseded. */
pred S16d_CloneFromUnpushedBase {
  one c: Campaign | some m: Machine {
    m not in machinesHolding[c]
    eventually (Now.event = CommitLocal and Where.machine = m)
    eventually (m in BaseUnpushed and Now.event = CreateDir and Where.machine = m)
    eventually (m in machinesHolding[c] and m in BaseUnpushed)
  }
}

/* --- The clone that was current when cut and stale when launched --- */

/* The superseded rule: never clone while the outer base holds commits
   origin lacks. */
pred pushBeforeClone { always (Now.event = CreateDir implies no BaseUnpushed) }

/* The adopted rule: fetch and compare inside the clone, at launch. */
pred pullCloneAtLaunch { always (Now.event = Launch implies Where.machine not in CloneBehind) }

/* Ordered explicitly: written as three unordered `eventually`s this also reads
   SAT on a clone cut after the merge, which is not the finding. */
pred cloneThenMergeThenLaunch[c: Campaign, i: Issue, m: Machine] {
  i in c.memberIssues and i.repo = Base
  eventually (Now.event = CreateDir and Where.machine = m
    and after eventually (Now.event = MergePullRequest and Now.issue = i
      and after eventually (Now.event = Launch and Where.machine = m
                            and m in CloneBehind)))
}

/* The superseded rule, enforced for the whole trace, does not stop it: the
   base read clean immediately before the clone, and the remote moved
   between the clone and the launch. The rule is checked in the wrong place. */
pred S17b_OldCloneRuleInsufficient {
  pushBeforeClone
  one c: Campaign | some i: Issue, m: Machine | cloneThenMergeThenLaunch[c, i, m]
}

/* Control: the adopted rule is not vacuous. A base pull request still
   merges mid-flight and a delegate still launches, once the clone is pulled. */
pred S17c_PullBeforeLaunchAdmitsLaunch {
  pullCloneAtLaunch
  one c: Campaign | some i: Issue, m: Machine {
    i in c.memberIssues and i.repo = Base
    eventually (Now.event = CreateDir and Where.machine = m
      and after eventually (Now.event = MergePullRequest and Now.issue = i
        and after eventually (Now.event = PullClone and Where.machine = m
          and after eventually (Now.event = Launch and Where.machine = m))))
  }
}

/* ---------------- commands ---------------- */

run S16b_BaseBehindAfterMerge  for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Machine, exactly 2 Repo, 1 Branch, 2 CampaignDir, 12 steps expect 1
run S16c_BehindForever              for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Machine, exactly 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
run S16d_CloneFromUnpushedBase for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Machine, exactly 2 Repo, 1 Branch, 2 CampaignDir, 10 steps expect 1
-- the superseded rule does not stop it
run S17b_OldCloneRuleInsufficient   for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Machine, exactly 2 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- control: the adopted rule is not vacuous
run S17c_PullBeforeLaunchAdmitsLaunch for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Machine, exactly 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1


/* ---------------- properties ---------------- */

/* Deleting a local directory changes no fact another machine reads. This is
   what lets the directory be optional and lets two machines hold one campaign
   under directory names differing only in date.

   The `githubFrame` conjunct is inherited rather than proved here, and that
   makes this check the test of the composition idiom itself: dropping the
   fall-through branch of `githubStep` reddens it. */
assert MachineIndependence {
  always (Now.event = DeleteDir implies (
    githubFrame
    and Claimed' = Claimed
    and CloneBehind' = CloneBehind
    and (all t: CampaignDir | t.machine != Where.machine implies (t in OnDisk iff t in OnDisk'))))
}

/* ---------------- reachability floor ---------------- */

pred Cov_PullBase { eventually Now.event = PullBase }
pred Cov_PullClone     { eventually Now.event = PullClone }
pred Cov_CommitLocal   { eventually Now.event = CommitLocal }
pred Cov_Launch        { eventually Now.event = Launch }

/* ---------------- commands ---------------- */

-- a local delete changes no shared fact
check MachineIndependence for 4 Issue, 3 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 6 steps expect 0

-- every own event fires in some trace
run Cov_PullBase for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 8 steps expect 1
run Cov_PullClone     for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 8 steps expect 1
run Cov_CommitLocal   for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 8 steps expect 1
run Cov_Launch        for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 8 steps expect 1
