#!/usr/bin/env sh
# Push a campaign branch the moment it has a commit, and say what happened.
#
# Moved out of the post-commit hook's heredoc so it can be linted, tested, and
# listed in the scripts inventory a session is shown at start-up.
set -u

branch=$(git symbolic-ref --quiet --short HEAD) || exit 0

# WHAT A CLAIM LOOKS LIKE IS NOT DECIDED HERE. It was, as `campaign-*/*`, and
# that glob was a second reader of `claim_match` -- so when #181 moved claims
# to `<slug>/<issue>-<topic>` the glob went on matching the retired form alone
# and every claim cut since committed without ever being pushed, silently,
# because the branch simply fell through to `exit 0`. Ask the owning script.
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 0
verdict=$("$HERE/check-commit-claim.py" --is-claim 2>&1)
status=$?

# THE WORD, NOT THE STATUS. Python exits 1 on an uncaught exception, so a bare
# status of 1 read as `answered no` would silently skip the push of a real
# claim on any bug in the reader. The word and the status must agree; when they
# do not, that is itself the unread question.
case "${verdict%% *}" in
claim) [ "$status" -eq 0 ] || status=9 ;;
no-claim) [ "$status" -eq 1 ] && exit 0; status=9 ;;
unknown) status=2 ;;
*) status=9 ;;
esac

case $status in
0) ;;                           # a claim: push it
*)
	# COULD NOT LOOK, so push anyway and say so. The cost of pushing a
	# branch that turns out not to be a claim is a branch on the remote;
	# the cost of not pushing one that is, is work that reads as landed to
	# nobody and dies with the machine.
	echo "push-campaign-branch: could not tell whether $branch is a claim." >&2
	echo "$verdict" | sed 's/^/  /' >&2
	echo "  Pushing anyway -- an unread question is not a no." >&2
	;;
esac

# mktemp, not /tmp/$$: /tmp is world-writable and a pid is guessable, so a
# pre-planted symlink there is truncated and overwritten by the redirect.
if ! err=$(mktemp); then
	echo "push-campaign-branch: mktemp failed; NOT pushing $branch." >&2
	echo "  The commit is local only. Push it yourself." >&2
	exit 0
fi
trap 'rm -f "$err"' EXIT INT TERM

# THE PULL REQUEST GOES UP AT THE FIRST COMMIT, not when the work is ready
# (AGENTS.md § Execution mode): the branch is already pushed by the time this
# runs, so a late pull request only keeps published work out of sight, and an
# open one is where a review writes its findings. Nothing here opens one -- the
# title and the body are the session's to write -- so this ANNOUNCES the line
# and refuses nothing.
#
# THE QUESTION IS "DOES ONE NAME THIS HEAD", AND NOTHING ELSE. It was also
# gated on the branch being one commit ahead of `origin/main`, so the line
# would be said once; that reading was SILENTLY WRONG, because `campaign-claim
# take` cuts the ref from the remote's main sha and never moves the local
# `origin/main`, so in a worktree lagging k commits a genuine first commit
# counts k+1 and nothing was said at all (rule-check#461, pr#487 review). The
# count is gone rather than repaired: a fetch to make it honest is a second
# unbounded network call, and the cost of the two failure modes is not
# symmetric. Saying it again at the next commit costs a session one glance and
# is TRUE every time it prints; missing the first commit is the defect this was
# written to close.
# OVERRIDABLE so a case can reach the give-up branch without waiting the
# whole bound out, and so a machine on a slow link can widen it. The
# defaults are the bound; nothing here reads them for anything else.
GH_TRIES=${GH_TRIES:-40}
GH_SLEEP=${GH_SLEEP:-0.25}

announce_pull_request() {
	b=$1
	# A BOUND, because this runs inside `post-commit` and an unbounded
	# network call hangs every commit on this machine. Neither `timeout`
	# nor `gtimeout` is on PATH here, so the watchdog is by hand.
	if ! out=$(mktemp); then
		echo "push-campaign-branch: mktemp failed, so whether a pull request names $b is unread." >&2
		echo "  Open one if none does." >&2
		return 0
	fi
	# THE TRAP COVERS THIS FILE TOO: the wait below runs for seconds, and an
	# interrupt inside it would otherwise leave the temp behind.
	trap 'rm -f "$err" "$out"' EXIT INT TERM

	# `gh` ITSELF IN THE BACKGROUND, not a subshell around it, so `$!` is
	# gh's own pid: a kill of a wrapper reaps the wrapper and leaves gh
	# reparented to pid 1 and still running, one leak per hung commit.
	# `wait` hands back its status, so nothing has to carry it in a file.
	# Its stdout and stderr go to that file and never to this hook's, which
	# a caller capturing `git commit` would otherwise wait on -- the same
	# hazard the `nohup` above is shaped around.
	gh pr list --head "$b" --state open --json number --jq '.[].number' \
		</dev/null >"$out" 2>&1 &
	job=$!
	n=0
	while [ "$n" -lt "$GH_TRIES" ] && kill -0 "$job" 2>/dev/null; do
		sleep "$GH_SLEEP"
		n=$((n + 1))
	done
	if kill -0 "$job" 2>/dev/null; then
		kill "$job" 2>/dev/null
		wait "$job" 2>/dev/null
		# WHAT IT HAD WRITTEN BY THEN IS NOT AN ANSWER: a killed gh can
		# leave a half-written file, and an empty one would read as
		# "no pull request names this". Not read at all.
		echo "push-campaign-branch: gh did not answer in ${GH_TRIES} tries of ${GH_SLEEP}s, so whether a pull request names $b is unread." >&2
		echo "  Open one if none does." >&2
		return 0
	fi
	wait "$job"
	gh_status=$?
	said=$(cat "$out" 2>/dev/null)

	# AN UNREAD QUESTION IS NOT A YES. A gh that will not run leaves it
	# unknown and says so; it is never read as "one already names this".
	if [ "$gh_status" != 0 ]; then
		echo "push-campaign-branch: could not tell whether a pull request names $b." >&2
		echo "$said" | sed 's/^/  /' >&2
		echo "  Open one if none does." >&2
		return 0
	fi
	[ -z "$said" ] || return 0
	echo "push-campaign-branch: no open pull request names $b."
	echo "  AGENTS.md § Execution mode: open it on the first commit, not when the work is ready."
	echo "  gh pr create --base main --head $b --title <verb-first> --body <Closes ...>"
}

# No force flag and no --no-verify: a rejected push is news, not something to
# overrule. An amend or a rebase lands here too, and the right answer for those
# is to be told, not to have the remote rewritten.
if git push --quiet origin "$branch" 2>"$err"; then
	echo "push-campaign-branch: pushed $branch"
	# THE READERS A PUSH STARTS read the pushed commit, in the background and
	# unwaited, since each asks a model; `campaign-jev.py run --on push` runs
	# every one the registry's `owner` names, and what each reads is its
	# docstring's. A GitHub remote only: their later fact is a REVIEW
	# on a pull request there, and a fixture's local remote is not one.
	case $(git remote get-url origin 2>/dev/null) in
	*github.com[:/]*)
		# ONE COMMAND IN THE BACKGROUND, not an `a && b &` list: a list is
		# a subshell holding this hook's stdout open, so a caller capturing
		# `git commit`'s output waited for every Jev call.
		sha=$(git rev-parse HEAD) || exit 0
		nohup "$HERE/campaign-jev.py" run --on push "$sha" "$branch" \
			</dev/null >/dev/null 2>&1 &

		announce_pull_request "$branch"
		;;
	esac
else
	echo "push-campaign-branch: could NOT push $branch -- the commit is local only." >&2
	sed 's/^/  /' "$err" >&2
	echo "  Push it yourself before anything reads this branch as landed." >&2
fi
exit 0
