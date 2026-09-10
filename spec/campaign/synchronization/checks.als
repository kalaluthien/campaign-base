/*
 * What must hold of synchronization/system, and the floor for its own events.
 * github/system.als is spec/'s entry point.
 */
module synchronization/checks

open synchronization/scenarios

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
/* directory/checks.als has its own, which does not see this composition. */
pred Cov_DeleteDir     { eventually Now.event = DeleteDir }

/* ---------------- commands ---------------- */

-- a local delete changes no shared fact
check MachineIndependence for 4 Issue, 3 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 6 steps expect 0

-- every own event fires in some trace
run Cov_PullBase for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 8 steps expect 1
run Cov_PullClone     for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 8 steps expect 1
run Cov_CommitLocal   for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 8 steps expect 1
run Cov_Launch        for 3 Issue, 2 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 8 steps expect 1
-- and the one lower event MachineIndependence names, at its scope
run Cov_DeleteDir     for 4 Issue, 3 PullRequest, 2 Campaign, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 6 steps expect 1
