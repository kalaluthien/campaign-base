/*
 * What a campaign directory's presence and absence buy, and how far behind
 * origin a machine's two base checkouts fall: the witnesses over
 * directory/system, what must hold of it, and the floor for its own events.
 * github/system.als is spec/'s entry point.
 */
module directory/checks

open directory/system

/* ---------------- witnesses ---------------- */

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
   the post-merge step exists and a close can follow it. One machine,
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

/* The adopted rule: fetch and compare inside the clone, at launch. */
pred pullCloneAtLaunch { always (Now.event = Launch implies Where.machine not in CloneBehind) }

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

/* ---------------- reachability floor ----------------
 * Every own event, and every lower event a check here names, fires in some
 * trace. CreateDir, Acquire, CommitLocal and Launch fire in
 * orchestration/checks.als, whose composition holds this one.
 */
pred Cov_DeleteDir     { eventually Now.event = DeleteDir }
pred Cov_MergePullRequestInDirectory { eventually Now.event = MergePullRequest }
pred Cov_CloseIssueInDirectory       { eventually Now.event = CloseIssue }
pred Cov_Reach         { eventually Now.event = Reach }
/* A push empties what a commit filled: BaseUnpushed can shrink. */
pred Cov_PushBase     { eventually (Now.event = PushBase and Where.machine in BaseUnpushed
                                    and after Where.machine not in BaseUnpushed) }

/* ---------------- commands ---------------- */

run S16_MergeReachesInstall     for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Machine, exactly 2 Repo, 1 Branch, 1 CampaignDir, 10 steps expect 1
run S15_NoLocalDirectory        for exactly 3 Issue, 2 PullRequest, exactly 1 Campaign, 1 Machine, exactly 3 Repo, 1 Branch, 1 CampaignDir, 12 steps expect 1
-- control: the adopted clone rule is not vacuous
run S17c_PullBeforeLaunchAdmitsLaunch for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Machine, exactly 2 Repo, 1 Branch, 1 CampaignDir, 14 steps expect 1

-- the post-merge step: holds under the discipline, and has a counterexample without it
check MergeReachesInstall      for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 10 steps expect 0
run MergeReachesInstall_Bites  for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 10 steps expect 1

-- the floor
run Cov_DeleteDir     for 4 Issue, 3 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 6 steps expect 1
run Cov_MergePullRequestInDirectory  for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 10 steps expect 1
run Cov_CloseIssueInDirectory        for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 10 steps expect 1
run Cov_Reach         for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 8 steps expect 1
run Cov_PushBase      for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 8 steps expect 1
