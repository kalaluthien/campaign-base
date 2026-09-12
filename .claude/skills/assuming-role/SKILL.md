---
name: assuming-role
description: Briefs a session on the campaign role it holds, what that role may write, and the moments of its lifecycle. Use when a session takes or changes a role, when it resumes or is compacted, or when it needs to know whether it is a planner or a worker and what that permits. Not for deciding which role to take, which the request decides, and not for claiming a sub-issue, which is campaign-claim take.
---

# Assuming a role

A session of a campaign is a planner or a worker. The role decides which plane
it may write and which moments belong to it; it is carried by the session name
and read from herdr by session id.

## Reading the role

Run `scripts/campaign-role-brief.py --role` from this skill's directory. It
prints one line, and the three outcomes are different questions:

| what it prints | what it means | what to do |
| --- | --- | --- |
| `planner <campaign>` or `worker <campaign>` | the role, and the campaign bounding it | read that role's reference below |
| `no role read for <id>` | herdr holds no campaign name for this session | name the session before any campaign write: `scripts/campaign-name-session.py <pane> <slug>-<role>-<n>` |
| anything opening `could not` | the resolver itself failed -- no session id, no herdr, an unreadable rule | report it; do not assume either role |

A no-role reading is not a permission failure and not a role of its own. The
guard refuses a campaign-plane write from a session it cannot name, so the
repair is the name, never a retry.

`scripts/campaign-roles.py` prints what each role may write. It is the one
statement of that; anything restating it in prose has already drifted.

## Every session of a campaign

1. Name the session before its first campaign write.
2. Read the campaign issue's scope before filing anything under it.
3. Record a discovery on the issue it belongs to when you find it. A finding
   held in a session's memory dies with the pane.
4. Carry the kind on a comment's first line: `KIND <session name>: <one line>`.
5. Leave by fact, not by announcement: stop the pane.

## The two roles

| the session | its reference |
| --- | --- |
| files the sub-issues, distributes them, changes no code | [planner](references/planner.md) |
| takes one sub-issue, cuts its claim, lands its commits | [worker](references/worker.md) |

A session that turns out to be the other role renames itself and reads the
other reference. Nothing durable carries the old name: a claim is a ref and a
checkout, and a rename touches neither.

## The kind of a sub-issue

A sub-issue carries one `kind:<k>` label, read by
`scripts/campaign-tracker.py kind <N>`. The brief hook emits the kind's
reference on the prompt that assigns the sub-issue, and again after a
compaction; each holds only what no base rule or role reference states.

The words are `scripts/campaign-tracker.py`'s `WORK_KINDS`, and this table is
their one prose home.

| the sub-issue exists to | label | reference |
| --- | --- | --- |
| answer an open question, or measure or audit something that already runs | `kind:research` | [research](references/kind-research.md) |
| build something new under a specification, or find out whether an approach can work at all | `kind:development` | none: its rules are the base's own |
| keep a running system in order: change its form with its behaviour kept, tidy it, and file what is found wrong with it | `kind:maintenance` | [maintenance](references/kind-maintenance.md) |
