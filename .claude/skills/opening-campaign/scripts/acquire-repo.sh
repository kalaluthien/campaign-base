#!/usr/bin/env bash
# acquire-repo — leave a ready checkout of <owner/repo> at <dest-path>.
#
#   .claude/skills/opening-campaign/scripts/acquire-repo.sh \
#       <owner/repo> <dest-path> [--branch <branch>]
#
# The one interface through which a campaign gets a repository. A caller asks
# for a repository, at a path, on a branch; how it got there is not its
# business.
#
# It lives under the skill because opening-campaign is its only caller: a
# repository is acquired when a campaign is opened or joined, and at no other
# moment. scripts/campaign-primitives.py walks .claude/skills/*/scripts/ as a
# second root so a script parked here is still announced.
#
# Bash, not Python: every step is already a `git` or `gh` invocation, so a
# shell function *is* a strategy with nothing between it and the command a
# person would type by hand.

set -euo pipefail

usage() {
	cat >&2 <<'EOF'
usage: acquire-repo <owner/repo> <dest-path> [--branch <branch>]

Leaves a ready checkout of <owner/repo> at <dest-path>, with <branch> checked
out (created from the default branch if it exists nowhere yet). Safe to re-run:
a second call over the same destination converges instead of failing.
EOF
	exit 2
}

log() { printf 'acquire-repo: %s\n' "$*" >&2; }
die() { printf 'acquire-repo: %s\n' "$*" >&2; exit 1; }

# LINE 2 OF EVERY PRE-COMMIT HOOK THIS SCRIPT WRITES, and the one thing that
# says the slot is this script's rather than somebody's. Two writers of one hook
# slot, the second refusing the first's output, is what left every delegate clone
# with no hook at all (#178), so scripts/install-hooks.sh adopts a slot holding
# this line -- `is_guard_shim` there is that reader, it holds the only other
# copy of this text, and changing the text here means changing it there. The
# reader below, in this file, uses this variable instead of a copy.
SHIM_MARKER='# Written by acquire-repo.sh. Re-run it after changing this file.'

# ---------------------------------------------------------------- arguments

repo=""
dest=""
branch=""

while [ $# -gt 0 ]; do
	case "$1" in
		--branch)
			[ $# -ge 2 ] || usage
			branch=$2
			shift 2
			;;
		--branch=*)
			branch=${1#--branch=}
			shift
			;;
		-h|--help) usage ;;
		-*) die "unknown option: $1" ;;
		*)
			if   [ -z "$repo" ]; then repo=$1
			elif [ -z "$dest" ]; then dest=$1
			else die "unexpected argument: $1"
			fi
			shift
			;;
	esac
done

[ -n "$repo" ] && [ -n "$dest" ] || usage
case "$repo" in
	*/*/*|/*|*/) die "expected <owner/repo>, got: $repo" ;;
	*/*) ;;
	*) die "expected <owner/repo>, got: $repo" ;;
esac

command -v git >/dev/null 2>&1 || die "git is not installed"

# ------------------------------------------------------------- building it
#
# `clone_into()` builds a checkout that does not exist yet; `acquire()` owns
# everything that is the same however the checkout arrived -- the
# already-acquired test, the wrong-repository refusal, convergence on a re-run,
# and installing the commit guard. So `clone_into()` only ever runs against a
# destination that is absent or empty, and never implements idempotency itself.
#
# `checkout_branch()` and `install_commit_guard()` are shared but *not*
# universal, and another way of producing a checkout would have to face them
# rather than assume them: `checkout_branch()` selects a branch with `git
# switch`, which fails inside a linked worktree when that branch is checked out
# elsewhere. `install_commit_guard()` resolves the hooks directory, which for a
# linked worktree is the *common* directory back in the source checkout, and
# refuses when that path falls outside the destination rather than silently
# guard another campaign's tree.

clone_into() {
	local repo=$1 dest=$2 branch=$3

	mkdir -p "$(dirname "$dest")"
	log "cloning $repo into $dest"
	if command -v gh >/dev/null 2>&1; then
		gh repo clone "$repo" "$dest" -- --quiet
	else
		git clone --quiet "https://github.com/$repo.git" "$dest"
	fi
	checkout_branch "$dest" "$branch"
}

# ------------------------------------------------------------ shared helpers

# Print the owner/repo an existing checkout's origin points at. Reads the last
# two path segments, so ssh, https, and a non-GitHub host all parse, rather than
# only a URL containing the literal "github.com".
remote_slug() {
	local url name rest
	url=$(git -C "$1" remote get-url origin 2>/dev/null) || return 1
	url=${url%.git}
	url=${url%/}
	name=${url##*/}
	rest=${url%/*}
	printf '%s/%s\n' "${rest##*[:/]}" "$name"
}

dir_is_empty() { [ -z "$(ls -A "$1" 2>/dev/null)" ]; }

checkout_branch() {
	local dest=$1 branch=$2
	if [ -z "$branch" ]; then
		log "on branch $(git -C "$dest" branch --show-current)"
		return 0
	fi
	if [ "$(git -C "$dest" branch --show-current)" = "$branch" ]; then
		log "already on branch $branch"
	elif git -C "$dest" show-ref --verify --quiet "refs/heads/$branch"; then
		git -C "$dest" switch --quiet "$branch"
		log "switched to local branch $branch"
	elif git -C "$dest" ls-remote --exit-code --heads origin "$branch" >/dev/null 2>&1; then
		git -C "$dest" fetch --quiet origin "$branch"
		git -C "$dest" switch --quiet --track "origin/$branch"
		log "checked out remote branch $branch"
	else
		git -C "$dest" switch --quiet -c "$branch"
		log "created branch $branch"
	fi
}

# IS THIS PRE-COMMIT ONE THIS SCRIPT WROTE? The one reader of that question on
# this side, and true of both shapes: the pre-#190 two-liner, matched whole
# because it carries nothing to name itself by, and the current one, matched on
# three things -- the shebang, the marker on line 2, and the guard CALL as a
# whole line. The marker is read from SHIM_MARKER rather than spelled again, so
# this file holds one copy of that text and not two.
#
# UNTIL #214 THIS WAS `grep -q 'no-main-commits' "$hook"`, a substring test over
# the whole file, so a foreign hook naming the guard in a COMMENT read as ours
# and was silently OVERWRITTEN. That is the same defect #190 round two fixed one
# file over, in scripts/install-hooks.sh's `is_guard_shim`; the two were fixed
# apart because only one was in that round's diff, and this is the direction
# that destroys rather than merely mislabels.
#
# TWO READERS, AND THE HONEST REASON. Not that a shared one is unreachable: a
# review of #214 showed it is. This function could source a
# `$base/scripts/is-guard-shim.sh` the same way `$gate` is resolved, and
# scripts/install-hooks.sh in practice only ever runs from a tree that ships
# one. The reason is one-sided: THAT script is written to work inside whatever
# repository ships it, depending on no sibling of its own, and a sourced reader
# would spend exactly that. This one can reach the base; that one is the half
# that cannot be made to depend on anything. A judgement, not a constraint.
#
# What keeps them from drifting is not this comment: both are pinned against
# the bytes the printf below actually writes -- the convergence case in
# scripts/acquire-repo-test.py here, case 5d in scripts/install-hooks-test.py
# there. That covers the guard CALL, which both read out of the shim. It does
# not cover the marker: this file reads SHIM_MARKER, so the marker cannot drift
# on this side by construction, and the copy in install-hooks.sh is pinned by
# its own fixtures alone.
#
# CALL IT IN A CONDITION. Under `set -e` a function whose last command is false
# returns non-zero, so calling this outside an `if`/`&&` would exit the script
# rather than take the false branch. One call site, and it is guarded.
#
# It establishes exactly what the reader there establishes and no more: that the
# slot opens with the shebang, carries the marker on line 2, and holds SOMEWHERE
# a whole line shaped like the guard call. Not that the line runs, and not that
# the hook is unmodified acquire output.
is_guard_shim() {
	if [ "$(wc -l <"$1" | tr -d ' ')" = 2 ]; then
		[ "$(sed -n 1p "$1")" = "#!/usr/bin/env sh" ] &&
			sed -n 2p "$1" | grep -qE '^exec "[^"]*/\.claude/git-hooks/no-main-commits" "\$@"$'
		return
	fi
	[ "$(sed -n 1p "$1")" = "#!/usr/bin/env sh" ] &&
		sed -n 2p "$1" | grep -qF "$SHIM_MARKER" &&
		grep -qE '^"[^"]*/\.claude/git-hooks/no-main-commits" "\$@" \|\| exit 1$' "$1"
}

# Git hooks do not clone, so the guard that blocks direct commits to main has to
# be installed into every checkout, whatever strategy produced it. A failure
# here is fatal: a caller reading success over an unguarded checkout is exactly
# the silent case the guard exists to prevent.
#
# One writer per hook slot. A repository that ships scripts/install-hooks.sh
# owns its own hooks, and that installer already chains the guard; so it is run
# here, with --git-only because the harness half is the base checkout's and a
# clone must not repoint it. The shim below is written only into a checkout with
# no installer, and the installer adopts that shim on a re-run -- which is what
# lets this function converge over a checkout it already guarded either way.
# Before #178 the shim was written unconditionally and the installer refused
# over it, so no delegate clone ever held the repository's hooks.
#
# THE SHIM CARRIES THE CLAIM GATE, and until #190 it did not. A member
# repository ships no scripts/install-hooks.sh, so every member clone took the
# branch below and got the no-main-commits guard and nothing else -- while
# check-campaign-claim.py went on calling that clone campaign work whose shell
# writes are "allowed unread; they land at the commit". They landed nowhere.
# check-commit-claim.py's docstring said a delegate's clone had held this hook
# since #178, which was true only of a clone that ships an installer, and the
# only such repository is this base. The model gap is `commitGateInstalled` in
# spec/campaign/orchestration/scenarios.als.
# Leave the campaign's principles where a delegate in this clone will read
# them: `CLAUDE.local.md` in its own cwd, excluded from the clone's index.
# Since rule-check#314 that file is the campaign's own additions only -- a
# default SDLC profile line and the three role sections; a sub-issue's kind
# reference reaches the delegate through the brief hook on its assignment
# prompt, not through this copy.
#
# #176 replaced `--append-system-prompt-file` with this file and wrote the
# instruction as prose; #187 question 5 is that no command anywhere wrote one,
# so a delegate launched by the documented procedure got no principles and
# NOTHING RECORDED THAT -- the failure mode the flag was abandoned for, back in
# a new shape. The prose is now here, where a caller cannot skip it.
#
# Excluded in `.git/info/exclude` and not `.gitignore`: the latter is tracked,
# so excluding a per-launch file there is a commit on the member repository for
# this campaign's convenience.
#
# A campaign with no `AGENTS.md` is a real answer and not a failure -- not every
# campaign adds principles -- but it is SAID, because a silent skip here is
# indistinguishable from the defect this closes.
install_principles() {
	local dest=$1
	local campaign src exclude
	campaign=$(cd "$dest/../.." 2>/dev/null && pwd -P) || {
		log "no campaign directory above $dest, so no principles were written"
		return 0
	}
	src="$campaign/AGENTS.md"
	if [ ! -f "$src" ]; then
		log "no $src, so this campaign adds no principles for $dest"
		return 0
	fi
	cp "$src" "$dest/CLAUDE.local.md" ||
		die "could not write $dest/CLAUDE.local.md from $src"
	exclude=$(git -C "$dest" rev-parse --path-format=absolute --git-path info/exclude) ||
		die "could not resolve $dest's info/exclude"
	mkdir -p "$(dirname "$exclude")" || die "could not create $(dirname "$exclude")"
	if ! grep -qxF "CLAUDE.local.md" "$exclude" 2>/dev/null; then
		printf 'CLAUDE.local.md\n' >>"$exclude" ||
			die "could not append to $exclude"
	fi
	log "principles: $src -> $dest/CLAUDE.local.md, excluded in $exclude"
}

install_commit_guard() {
	local dest=$1
	local guard="$HOME/.claude/git-hooks/no-main-commits"
	local hooks hook dest_abs installer rc base gate

	# THE BASE IS RESOLVED FROM THIS FILE, never from $dest. A member clone is
	# not under the base and holds no copy of check-commit-claim.py, so a walk
	# up from the destination cannot find either -- install_principles's walk is
	# the wrong precedent here for exactly that reason: it wants the CAMPAIGN
	# directory, which is above $dest, where this wants the BASE, which is not.
	# This file sits at <base>/.claude/skills/opening-campaign/scripts/, so the
	# base is four directories up. BASH_SOURCE, not $0: $0 is the interpreter
	# when a caller sources or extracts a function from this file.
	base=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd -P) ||
		die "could not resolve the base above ${BASH_SOURCE[0]}"
	gate="$base/scripts/check-commit-claim.py"

	if [ ! -x "$guard" ]; then
		log "no executable guard at $guard, so $dest would be left unguarded."
		log "Restore it from the checkout that owns it:"
		log "  git -C \"\$HOME/.claude\" checkout -- git-hooks/no-main-commits"
		log "  chmod +x \"$guard\""
		die "refusing to leave $dest unguarded"
	fi

	# Checked here as well as in the hook, and the two are different readings:
	# this one says the base a caller is acquiring FROM has the gate, the one in
	# the hook says it is still there when a commit is made months later.
	if [ ! -x "$gate" ]; then
		log "no executable claim gate at $gate, resolved from ${BASH_SOURCE[0]}."
		log "A hook naming a gate that cannot run reads to every session like a"
		log "rule being enforced, so this refuses rather than installs it."
		die "refusing to leave $dest with a gate it cannot run"
	fi

	hooks=$(git -C "$dest" rev-parse --path-format=absolute --git-path hooks)
	dest_abs=$(cd "$dest" && pwd -P)
	case "$hooks" in
		"$dest_abs"/*) ;;
		*) die "hooks for $dest resolve to $hooks, outside the checkout; refusing to guard another tree" ;;
	esac

	installer="$dest/scripts/install-hooks.sh"
	# The execute bit alone must not pick the branch: an installer present but
	# not executable would fall through to the shim and silently restore the
	# state this function exists to end.
	if [ -f "$installer" ] && [ ! -x "$installer" ]; then
		die "$installer exists but is not executable; chmod +x it and re-run"
	fi
	if [ -x "$installer" ]; then
		log "running the repository's own installer: $installer --git-only"
		# Captured, not read from `$?` inside the branch: there it is the
		# status of the negated condition, which is 0 exactly when the branch
		# is taken.
		if (cd "$dest" && "$installer" --git-only); then rc=0; else rc=$?; fi
		[ "$rc" = 0 ] ||
			die "the repository's install-hooks.sh exited $rc -- read what it said above"
		# The invariant is verified, not trusted: the installer belongs to the
		# repository, and its hook has to chain the guard for success here to
		# mean the same thing it means on the shim path.
		#
		# A LINE THAT IS NOT WHOLLY A COMMENT, which is the whole of the change
		# #214 makes here. This was `grep -q 'no-main-commits'` over the file,
		# so a hook merely MENTIONING the guard in a comment passed as one
		# chaining it -- the same defect as the overwrite test above, read in
		# the milder direction.
		#
		# NOT a whole-line call pattern, which is what the first spelling of
		# this used and which refused three shapes the substring test accepted:
		# `guard="$HOME/.claude/git-hooks/no-main-commits"` with the call made
		# through the variable, and the `if [ -x ... ]` guard this repository's
		# OWN hook writes on the line above its call. The hook belongs to
		# another repository and its shell is arbitrary; no pattern can decide
		# that a line RUNS. So the discrimination is exactly the one the issue
		# asks for -- a mention in a comment is not evidence -- and nothing
		# tighter, because a false refusal here is fatal.
		#
		# Its ceiling, said rather than implied: a line of code with the path in
		# a TRAILING comment matches, and so does the path inside a string. What
		# it will not match is a line whose first non-blank character is `#`.
		grep -qE '^[[:space:]]*[^#[:space:]].*/\.claude/git-hooks/no-main-commits' \
			"$hooks/pre-commit" 2>/dev/null ||
			die "the installer left $hooks/pre-commit without the no-main-commits guard; refusing to call $dest guarded"
		log "installed the repository's git hooks, which chain the no-main-commits guard"
		return 0
	fi

	mkdir -p "$hooks"
	hook="$hooks/pre-commit"

	# The remediation is to re-run this script, not a printf to paste: since #190
	# the hook carries two absolute paths over several lines, and a hand-typed
	# copy of it is the hardcoded second reader this repository refuses
	# everywhere else. No line count is written down here or in install-hooks.sh:
	# three comments said "ten" while the hook was eleven.
	if [ -e "$hook" ] && ! is_guard_shim "$hook"; then
		log "$hook exists and is not one this script wrote. Read it, then either"
		log "chain the two lines below from it by hand, or move it aside and"
		log "re-run this script, which writes both:"
		log "  \"$guard\" \"\$@\" || exit 1"
		log "  \"$gate\" --staged"
		log "  mv '$hook' '$hook.bak' && <re-run acquire-repo.sh>"
		die "refusing to overwrite an existing pre-commit hook"
	fi

	# BOTH halves, and the claim gate by ABSOLUTE PATH: a member clone has no
	# scripts/ of its own to reach it through, so `git rev-parse --show-toplevel`
	# -- which is how this repository's own hook finds its guards -- resolves to
	# the clone and finds nothing. The path is baked in at acquire time, and the
	# hook re-reads it at every commit rather than trusting it: a base checkout
	# that moved or was deleted turns a silent pass into a named refusal.
	#
	# `|| exit 1` ON THE GUARD, spelled rather than left to `set -e`. Before
	# #190 the shim was `exec "$guard"`, so the guard's status WAS the hook's;
	# now something runs after it, and for one revision the only thing making
	# its refusal fatal was a `set -e` no case pinned. Measured on the deployed
	# path: with the shim's `set -e` deleted, a clone outside every base tree --
	# where the claim gate admits -- LANDED a commit on `main` that the guard
	# had just refused, with the refusal printed above the commit line.
	printf '%s\n' \
		'#!/usr/bin/env sh' \
		"$SHIM_MARKER" \
		"\"$guard\" \"\$@\" || exit 1" \
		"if [ ! -x \"$gate\" ]; then" \
		"	echo \"pre-commit: REFUSING -- $gate is missing or not executable.\" >&2" \
		'	echo "  acquire-repo.sh installed this hook, so the claim gate is" >&2' \
		'	echo "  expected to run. Re-run acquire-repo.sh from a base checkout" >&2' \
		'	echo "  that has it, or restore the one this hook names." >&2' \
		'	exit 1' \
		'fi' \
		"exec \"$gate\" --staged" > "$hook"
	chmod +x "$hook"
	log "installed the no-main-commits guard and the claim gate at $gate"
}

# ------------------------------------------------------------------- acquire

acquire() {
	local repo=$1 dest=$2 branch=$3 have

	if [ -e "$dest/.git" ]; then
		have=$(remote_slug "$dest") || die "$dest is not a usable git checkout"
		[ "$have" = "$repo" ] ||
			die "$dest already holds $have, not $repo — refusing to touch it"
		log "already present: $dest ($repo)"
		git -C "$dest" fetch --quiet origin
		checkout_branch "$dest" "$branch"
	else
		[ ! -e "$dest" ] || [ -d "$dest" ] ||
			die "$dest exists and is not a directory"
		[ ! -d "$dest" ] || dir_is_empty "$dest" ||
			die "$dest is a non-empty directory that is not a git checkout"

		clone_into "$repo" "$dest" "$branch"
	fi

	install_commit_guard "$dest"
	install_principles "$dest"
	log "ready: $dest"
}

acquire "$repo" "$dest" "$branch"
