/*
 * The reachability floor for session/system: its own events, and every
 * refinement it adds to a lower entity's event. github/system.als is spec/'s
 * entry point.
 */
module session/checks

open session/scenarios

/* ---------------- reachability floor ----------------
 * The events this entity introduces, and every refinement it adds to a
 * lower entity's event. A refinement that cannot be satisfied would make its
 * event unreachable from here upward while the lower entity's own floor stayed
 * green. `Cov_Bound` pins `FileCampaignIssue` rather than reading `some
 * Binding.bound`, which `githubInit` alone satisfies at step 0.
 */
pred Cov_Survey            { eventually Now.event = Survey }
pred Cov_Adopt             { eventually Now.event = Adopt }
pred Cov_ReadBody          { eventually Now.event = ReadBody }
pred Cov_EditReadme        { eventually Now.event = EditReadme }
pred Cov_Brief             { eventually Now.event = Brief }
pred Cov_ContextReset      { eventually (Now.event = ContextReset and Who.session not in Briefed') }
/* Both pinned on the post-state, so each fails when its update is dropped. */
pred Cov_Stamp             { eventually (Now.event = Stamp and Who.session not in Stamped and Who.session in Stamped') }
pred Cov_Unstamp           { eventually (Now.event = Unstamp and Who.session in Stamped and Who.session not in Stamped') }
pred Cov_WriteBodyBySession              { eventually (Now.event = WriteBody and some Who.session) }
pred Cov_CloseCampaignIssue       { eventually (Now.event = CloseIssue and Now.issue in Campaign.campaignIssue) }
pred Cov_FiledBySession    { eventually (Now.event = FileCampaignIssue and some Who.session) }
pred Cov_MemberBySession   { eventually (Now.event = AddMember and some Who.session) }
pred Cov_DirBySession      { eventually (Now.event = CreateDir and some Who.session) }
pred Cov_DeleteBySession   { eventually (Now.event = DeleteDir and some Who.session) }
pred Cov_AcquireBySession  { eventually (Now.event = Acquire and some Who.session) }
pred Cov_ClaimBySession    { eventually (Now.event = Claim and some Who.session) }
pred Cov_ReleaseBySession  { eventually (Now.event = Release and some Who.session) }
pred Cov_LaunchBySession   { eventually (Now.event = Launch and some Who.session) }
pred Cov_MergeBySession    { eventually (Now.event = MergePullRequest and some Who.session) }
pred Cov_Bound             { eventually (Now.event = FileCampaignIssue and some Binding.bound') }

/* ---------------- commands ---------------- */

-- every own event and every refinement this entity adds fires in some trace
run Cov_Survey            for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_Adopt             for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_ReadBody          for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_EditReadme        for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_Brief             for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_ContextReset      for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_Stamp             for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_Unstamp           for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_WriteBodyBySession              for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_CloseCampaignIssue       for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_FiledBySession    for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_MemberBySession   for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_DirBySession      for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_DeleteBySession   for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_AcquireBySession  for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_ClaimBySession    for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_ReleaseBySession  for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_LaunchBySession   for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_MergeBySession    for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
run Cov_Bound             for 3 Issue, 1 PullRequest, 2 Campaign, 2 Session, 2 Machine, 3 Repo, 2 Branch, 4 CampaignDir, 12 steps expect 1
