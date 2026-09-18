#!/usr/bin/env python3
"""Log whether each hunk a maintenance claim pushed changes behaviour its Intent did not ask for, and refuse nothing.

THE READING `form-behaviour` in scripts/jev/readings.json, asked through
scripts/campaign-jev.py. The entry holds the question, its four options, the
state's fields and the tier, and declares no cut; this reads it and writes none
of it.

WHO RUNS IT: scripts/push-campaign-branch.sh, the post-commit hook, in the
background beside check-diff-screen.py once it pushed a claim to a GitHub
remote. It asks only on a claim whose sub-issue carries `kind:maintenance`:
a tidy-up promises to change form, and a hunk that changes what something does
beyond what its `## Intent` asks is the one a reviewer must not read as form.
Any other claim, and a branch that is no claim, asks nothing and logs nothing.

WHAT IT READS: the sub-issue the branch names (`campaign-claim.py`'s
`issue_of_branch`), its labels and its `## Intent` from the tracker; the
commit's own files (check-diff-screen's `files`); each file's patch from the
merge-base with the remote's default branch to the commit, in check-diff-screen's
pinned form, cut into hunks at its `@@` lines.

  asked      one call a hunk: state `{intent, hunk: {path, text}}`, the key
             the repository, the sha, the path and the hunk's `@@` range, the
             `flag` P(unasked_behaviour)
  settled    `form_only` by code, the row's `flag` naming the rule: a hunk of
             a test suite (check-diff-screen's `TEST`), a hunk of a shell,
             YAML, TOML or JavaScript file whose every changed non-blank line
             is a comment in that language, and a hunk of a `.py` file whose
             AST, function and class docstrings blanked, is the same before
             and after that hunk alone
  passed     a merge commit asks nothing: `git diff-tree` lists no file for one
  skipped    what check-diff-screen skips -- an empty branch patch, a binary,
             a failed `git diff`, a patch over its ceiling, no merge-base --
             and a sub-issue that would not read, one with an empty or no
             `## Intent`, a commit that does not resolve, or a reading that
             raised, each log one `skipped` row naming why

THE TIER is `shadow`: every call is logged and nothing is printed, since the
hook's background start discards this process's output. Rows land in the
base's `runtime/jev.log`, found from this script's directory, for
check-diff-screen's reason. THE EXIT STATUS IS 0 on every path but a usage
error, which is 2.

WHERE THIS READING IS KNOWN TO BE WRONG is the entry's `bands.how`: it orders
hunks by whether the Intent names the change, and at jev-1.13.0 no cut flags
every made negative without flagging every positive.

Usage: scripts/check-form-behaviour.py [<commit> [<branch>]]
"""
import ast
import importlib.machinery
import importlib.util
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
READING = "form-behaviour"
REGISTRY = HERE / "jev" / "readings.json"
READER = "check-form-behaviour.py"
KIND = "maintenance"
FLAG = "unasked_behaviour"
GH_TIMEOUT = 30
WORKERS = 8
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", re.M)
# A COMMENT LINE, BY THE FILE'S LANGUAGE, and only where a comment says no
# rule. A marker read in every file settled `--squash` in a shell line and
# `*args` in Python (pr#503 F1). Python is not here: its AST rule already
# ignores comments. Alloy is not here either, nor is prose: a spec comment and
# a document line are the rule itself (F2). A shebang is no comment.
COMMENT = {
    ".sh": re.compile(r"^\s*#(?!!)"), ".bash": re.compile(r"^\s*#(?!!)"),
    ".zsh": re.compile(r"^\s*#(?!!)"), ".yml": re.compile(r"^\s*#"),
    ".yaml": re.compile(r"^\s*#"), ".toml": re.compile(r"^\s*#"),
    ".js": re.compile(r"^\s*(//|/\*|\*)"), ".ts": re.compile(r"^\s*(//|/\*|\*)"),
}


def load_sibling(name):
    """A sibling script as a module, by path: these are scripts, not a package."""
    key = name.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_loader(
        key, importlib.machinery.SourceFileLoader(key, str(HERE / name)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def hunks(patch):
    """[(header, text, old start, old count)] of one file's patch."""
    out = []
    parts = re.split(r"\n(?=@@ )", patch)
    for part in parts[1:] if not parts[0].startswith("@@ ") else parts:
        m = HUNK.match(part)
        if m:
            out.append((m.group(0), part.rstrip("\n"), int(m.group(1)),
                        int(m.group(2) or 1)))
    return out


def blanked(source):
    """The AST of `source` with every function and class docstring replaced by
    `pass`, dumped. THE MODULE'S IS KEPT: a script prints it as its usage
    through `__doc__`, so a change to it is a change of output (pr#503 F3)."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Module):
            continue
        body = getattr(node, "body", None)
        if (isinstance(body, list) and body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            body[0] = ast.Pass()
    return ast.dump(tree)


def same_ast(before, text, start, count):
    """Whether applying this one hunk to `before` leaves the blanked AST as it
    was; False where either side does not parse."""
    lines = before.split("\n")
    new = [line[1:] for line in text.split("\n")[1:] if line[:1] in " +"]
    at = start - 1 if count else start
    try:
        return blanked(before) == blanked(
            "\n".join(lines[:at] + new + lines[at + count:]))
    except SyntaxError:
        return False


def settled_by(path, text, start, count, before, test):
    """The prefilter rule that settles this hunk `form_only`, or None."""
    if test.search(path):
        return "a test suite"
    changed = [line[1:] for line in text.split("\n")[1:]
               if line[:1] in "+-" and line[1:].strip()]
    comment = COMMENT.get(Path(path).suffix)
    if comment and changed and all(comment.match(line) for line in changed):
        return "comment lines only"
    if path.endswith(".py") and before is not None and same_ast(
            before, text, start, count):
        return "the same AST, docstrings blanked"
    return None


def sub_issue(number, repo):
    """(labels, body) of the sub-issue, or raise naming why it did not read."""
    p = subprocess.run(["gh", "api", f"repos/{repo}/issues/{number}", "--jq",
                        "{labels: [.labels[].name], body: .body}"],
                       capture_output=True, text=True, timeout=GH_TIMEOUT)
    if p.returncode != 0:
        raise LookupError(f"gh exited {p.returncode}")
    got = json.loads(p.stdout)
    return got["labels"], got["body"] or ""


def main(argv, env=None):
    if len(argv) > 2:
        print("Usage: scripts/check-form-behaviour.py [<commit> [<branch>]]",
              file=sys.stderr)
        return 2
    subject = argv[0] if argv else "HEAD"
    try:
        screen = load_sibling("check-diff-screen.py")
        git = screen.git
        branch = argv[1] if len(argv) > 1 else (
            git("symbolic-ref", "--quiet", "--short", "HEAD") or "").strip()
        number = load_sibling("campaign-claim.py").issue_of_branch(
            branch, branch.split("/", 1)[0])
        if number is None:
            return 0
        jev = load_sibling("campaign-jev.py")
        repos = load_sibling("campaign-repos.py")
        commit = (git("rev-parse", "--verify", "-q", subject + "^{commit}")
                  or "").strip()
        label = f"{branch} {commit[:12] or subject}"
        try:
            names, body = sub_issue(number, repos.BASE_REPO)
        except Exception as e:  # noqa: BLE001 -- an unread issue is a skip
            jev.skip(READER, label, f"sub-issue {number} did not read "
                     f"({e.__class__.__name__})", env, cwd=HERE)
            return 0
        kind, _why = load_sibling("campaign-tracker.py").work_kind_of(names)
        if kind != KIND:
            return 0
        if not commit:
            jev.skip(READER, label, "the commit does not resolve", env, cwd=HERE)
            return 0
        intent = repos.section(body, "Intent")
        if not intent:
            jev.skip(READER, label, f"sub-issue {number} has no ## Intent",
                     env, cwd=HERE)
            return 0
        intent = "\n".join(intent)
        base = next((b.strip() for b in (git("merge-base", commit, ref)
                                             for ref in screen.DEFAULT_BRANCH)
                     if b), "")
        if not base:
            jev.skip(READER, label, "no merge-base with origin/HEAD or "
                     "origin/main", env, cwd=HERE)
            return 0
        entry = json.loads(REGISTRY.read_text(encoding="utf-8"))[READING]
        found, _tests = screen.files(commit, base)
        key = jev.commit_key()
        key = ({"repo": key["repo"], "commit": commit} if key.get("repo")
               else {})
        asks = []
        for path, why in found:
            patch = "" if why else git("diff", *screen.PATCH_FORM, base,
                                       commit, "--", path)
            if patch is None:
                why = "git diff failed"
            elif not why and len(patch) > screen.PATCH_CEILING:
                why = (f"a patch of {len(patch)} chars, over "
                       f"{screen.PATCH_CEILING}")
            if why:
                jev.skip(READER, f"{label} {path}", why, env, cwd=HERE)
                continue
            before = git("show", f"{base}:{path}") if path.endswith(".py") \
                else None
            for header, text, start, count in hunks(patch):
                asks.append((path, header, text, settled_by(
                    path, text, start, count, before, screen.TEST)))

        def flagged(_reading, raw):
            """P(unasked_behaviour), the one option the flag reads; no cut is
            declared on it, so the row keeps the number and not a word."""
            p = ((raw or {}).get("probabilities") or {}).get(FLAG)
            return {"code": p, "moved_by": FLAG} if p is not None else None

        def one(item):
            path, header, text, rule = item
            # ONE `judge` CALL A HUNK, or none where code settled it: the row
            # then carries `settled: form_only` and the rule in its `flag`.
            jev.judge(entry["group"],
                      {"intent": intent, "hunk": {"path": path, "text": text}},
                      read=f"{label} {path} {header}", reader=READER,
                      settled={READING: "form_only"} if rule else None,
                      flag={"code": "form_only", "moved_by": rule} if rule
                      else flagged,
                      key=dict(key, path=path, hunk=header) if key
                      else {"path": path, "hunk": header},
                      env=env, cwd=HERE)
        with ThreadPoolExecutor(WORKERS) as pool:
            list(pool.map(one, asks))
    except Exception as e:  # noqa: BLE001 -- a reading never refuses, and nobody reads this
        skipped(subject, e, env)
    return 0


def skipped(subject, e, env):
    """The skip row for a reading that raised, written if the log can be."""
    try:
        load_sibling("campaign-jev.py").skip(
            READER, subject, f"the reading raised {e.__class__.__name__}", env,
            cwd=HERE)
    except Exception:  # noqa: BLE001 -- campaign-jev itself would not load
        pass


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
