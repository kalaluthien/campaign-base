# Close gotchas, in full

The evidence behind the one-line gotchas in `SKILL.md`. Each is a failure that
raises no error.

## Step 2's silent failures live in the script

A squash merge making a landed branch read unmerged forever, `git status
--porcelain` never listing an ignored file, an unreadable `repos/` that reads as
a campaign with no member repository, and a checkout whose `.git` is a file
dropping out of the verdict entirely: each could report nothing while testing
nothing. Step 2 is one call to `scripts/campaign-local-work.py` now, so they are
the script's to get right and its docstring states each with its evidence.
Nothing of them is restated here — two copies of a probe is how one goes stale.

## An unmatched `repos/*/` glob fails two different ways

Kept here rather than in the script, because the script enumerates with
`os.scandir` and never globs — this is a fact about any *shell* line a skill
might grow back, and the skill is run by hand in whatever shell the person is in
(all three probed):

| shell | what an unmatched `repos/*/` does |
| --- | --- |
| bash, sh | leaves the glob literal, so the loop runs once on `.../repos/*/` and every git command fails against a path that does not exist — output that reads as an unresolvable repository blocking the close |
| zsh | `no matches found`, and the whole `for` never runs — a gate that reported nothing because it tested nothing, and an abort outright under `set -e` |

Neither `nullglob` nor a zsh `(N)` qualifier fixes it: each fixes one shell and
breaks the other.

## `dropped` covers four closes

`not planned`, `duplicate`, `completed, no merged pull request`, and `closed, no
reason recorded`. All four are settled — settled is "the issue is closed" — and
only the first is abandonment, so quote the note, not the word.

## `state_reason` case differs by command

Lowercase from `gh api`, uppercase from `gh issue list --json stateReason`. A
comparison against the wrong one matches nothing and reads every sub-issue as
unsettled — half of why the reading lives in one script rather than in prose.

## `set -- $var` does not word-split in zsh

And this skill is made of gates. Unquoted parameters stay unsplit, so `for pair
in a:1 b:2; do set -- $pair` leaves `$2` empty. Here it failed loudly — `gh`
answered `invalid issue format: ""` — but the same construct inside a check whose
empty result reads as "nothing to report" passes having tested nothing.

## `diff` is shadowed in a Claude Code shell on this machine

By a zsh autoload stub with no file behind it, so a plain `diff` dies with
`(eval):1: diff: function definition file not found` — which reads like a missing
input file, not a shadowed name. Write `command diff`; `cmp`, `sed`, `grep` and
`cp` are unaffected.


## `git/matching-refs` does not paginate, and is documented that way

`campaign-claim` lists every `<slug>/` ref with a bare `gh api`. That looks like the
truncation hazard this base guards everywhere else — a paged endpoint read
without `--paginate`, where a truncated list reads exactly like a complete one.
It is not. Measured against a repository with 241 matching refs:

<!-- unguarded: campaign-claim -- a probe of the endpoint's paging on a foreign repository, listing no claim -->
```
gh api "repos/cli/cli/git/matching-refs/heads/" --jq 'length'                 -> 241
gh api --paginate "repos/cli/cli/git/matching-refs/heads/" --jq 'length'      -> 241
gh api "repos/cli/cli/git/matching-refs/heads/?per_page=30" --jq 'length'     -> 241
gh api "repos/cli/cli/git/matching-refs/heads/?per_page=1&page=2" --jq 'length' -> 241
gh api -i "repos/cli/cli/git/matching-refs/heads/" | grep -i '^link'          -> nothing
```

`per_page` and `page` are both ignored and no `Link` header is sent. **The
control is what makes this decisive**, ruling out `gh` following pages by
itself:

```
gh api "repos/cli/cli/branches" --jq 'length'                                -> 30
gh api -i "repos/cli/cli/branches" | grep -ic '^link'                        -> 1
```

Same client, same invocation shape, no `--paginate`: `branches` stops at thirty
*and says so in a `Link` header*. So the difference is the endpoint, not the
client. And the size is not a ceiling near 241 — `tensorflow/tensorflow` returns
**2093** refs in one response.

**Why the flag is not added anyway.** A `--paginate` on a call that does not
page is a false statement about the endpoint, and this campaign has spent itself
removing those. The comment at the call site is the cheaper true thing.

**The documentation agrees, which is the second independent reason not to add
the flag.** The endpoint's own page lists no pagination parameters at all, and
the absence is meaningful rather than an omission — the control page renders
them where they exist:

```
curl -s https://docs.github.com/en/rest/git/refs          | grep -c per_page -> 0
curl -s https://docs.github.com/en/rest/branches/branches | grep -c per_page -> 2
```

**The rule is not "always paginate" — it is measure, then decide.** Adding
`--limit` fits a call that pages; declining `--paginate` fits one that does not.
Measure a new `gh api` call the same way rather than reading a list of the ones
already judged, which goes stale the next time a call site moves.
