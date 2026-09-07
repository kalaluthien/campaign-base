/*
 * The reachability floor for directory/system's own events.
 * github/system.als is spec/'s entry point.
 */
module directory/checks

open directory/scenarios

/* ---------------- reachability floor ---------------- */

pred Cov_CreateDir     { eventually Now.event = CreateDir }
pred Cov_DeleteDir     { eventually Now.event = DeleteDir }
pred Cov_Acquire       { eventually Now.event = Acquire }
pred Cov_Reach         { eventually Now.event = Reach }

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
run Cov_DeleteDir     for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 8 steps expect 1
run Cov_Acquire       for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 8 steps expect 1
run Cov_Reach         for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 8 steps expect 1

-- the post-merge step: holds under the discipline, and has a counterexample without it
check MergeReachesInstall      for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 10 steps expect 0
run MergeReachesInstall_Bites  for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 10 steps expect 1
