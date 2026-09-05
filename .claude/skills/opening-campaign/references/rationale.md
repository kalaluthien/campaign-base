# Why the open is shaped this way

One section per step of `SKILL.md`. Read a section when a guard there looks
arbitrary, or when you are about to change it.

## Finished when — reading the `## Repos` list

`scripts/campaign-repos.py` is the one reader of that list, and its refusals are
enumerated in its own header. The bare `grep '<'` that `SKILL.md`
forbids fails because a correct `## Done when` section quotes things like
`issues/<N>/sub_issues`, so it reports hits on a clean README — which is why the
check is a reader scoped to the one section.

## The gate — deciding new or follow-up

The survey itself is `AGENTS.md` § Routing an arriving request; this is why
its two readings are shaped the way they are.

**Read an unplaced issue for shape.** Which shape means which kind, and that the
third kind is left alone rather than surveyed, joined, or edited, is `AGENTS.md`
§ The base as its own member. What that section leaves
implicit for this step: every campaign issue is in the no-parent listing whether or not
it was labelled, which is what makes the two readings cross-check each other.

**Testing is a follow-up, and it is decided here.** The deliverable is not
finished until it is shown to work, and the fixes land on the artifacts that
campaign already owns. Scope is written in artifacts and cannot separate "build
X" from "validate X", so this one cannot be read off the body.

## Step 3 — filing the campaign issue

**The re-survey narrows the window, it does not close it.** The read and the
create are two calls and nothing makes them one, so two sessions can still
interleave between them. What the re-read buys is that the window is seconds
instead of however long steps 2 and 3 took.

**Why the label is read back.** `--label campaign` is what makes the campaign issue
findable at all, and a campaign issue filed without it is invisible to every later
survey, so the next session opens a second campaign over the same scope and
nothing reports it (probed: an unlabelled parent issue does not appear in step
1's labelled listing).

**Why the template is the one copy of the shape.** Step 4 copies it into the
campaign directory as the placeholder `README.md` and then replaces it with what
step 3 wrote, and a later survey classifies by the shape left behind.

## Step 4 — scaffolding

**Write to `.tmp` and `mv` on success, so a failure leaves no file at all.**
Redirecting straight to `runtime/repos` truncates it before the reader runs, so a
refusal leaves a zero-length file — and a zero-length `runtime/repos` is exactly
what a campaign with no member repository leaves. Step 5 would then loop zero
times, acquire nothing, and the failed read would be indistinguishable from a
deliberate `- none`. Absent, the file makes step 5's redirection fail loudly
instead.

**And that is why step 5 reads a file rather than a pipe.** A file that exists
only after a successful read is what makes a failed read loud; piping the reader
straight into `while read` would swallow its exit status and run the loop zero
times, which is what a legitimate `- none` also does.

**`runtime/campaign-issue-body-derived.md`'s lifetime.** It is scratch, like everything
else under `runtime/`, and dies with the directory — the right lifetime, because
it is only ever compared against by a session working in this tree.

## Step 5 — acquiring

**`${REPO##*/}` and the collision.** Every entry becomes a checkout at
`repos/<name>/`, so `a/web` beside `b/Web` is one directory on this filesystem
and the second acquire overwrites the first without a word. The reader refuses
that pair, so the collision is caught where the list is read rather than worked
around here, and the layout stays `repos/<name>/`, which is what `AGENTS.md` and
every reader of a campaign tree expect.

**Why no `--branch`.** One checkout serves every session of the campaign, so
`--branch` here would make a re-run of this step switch it onto another branch
under a delegate already working in it. Without it,
`acquire-repo` re-runs as a fetch and touches no branch.

## Filing a sub-issue

**The branch name's parts** — what each of `campaign-<N>/<issue>-<topic>` keeps
apart, and why the branch's existence is the claim — are the Branch bullet of
`AGENTS.md` § ID, directory, branch.

**Why the addition syncs immediately** is `AGENTS.md` § The campaign issue body:
adding a repository is a scope change, and holding it back to the close loses
exactly what the delay was meant to protect. What that leaves implicit here: the
session that opens the campaign on another machine clones the `## Repos` list and
would have no checkout for the sub-issue just filed.
