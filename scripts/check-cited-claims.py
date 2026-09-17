#!/usr/bin/env python3
"""Print where prose's claim about a spec pred reads contradicted, and refuse nothing.

THE READINGS `docstring-claims` and `reference-claims` in
scripts/jev/readings.json, asked through scripts/campaign-jev.py at
`pre-commit` beside check-sdlc-tie.py. They share one claim cut, one
`pred.text` builder and one report; they differ only in where a paragraph comes
from. Each entry holds its question, criteria, state fields and how they are
cut, prefilter, thresholds and tier; this reads them and writes none of them.
How to ask Jev well in general is the `asking-jev` skill's `references/`, not
this file's.

WHAT IT READS, from the INDEX (`git diff --cached` and `git cat-file`), so what
is judged is what the commit holds:

  sources    docstring-claims: each blank-line paragraph of a Python docstring
             in a scripts/ directory (check-tree-shape.py's R6 membership,
             imported). reference-claims: each paragraph, list item or table
             row -- the row under its header -- of AGENTS.md or a
             .claude/skills/*/references/*.md, fenced code left out
  cited      a pred, fun or assert name in backticks, declared once under
             spec/; a name the entry's `prefilter.plain_name` matches counts
             only in a sentence its `prefilter.anchored_by` matches or holding
             another cited name that is not plain
  touched    a staged hunk overlapping a pred, fun or assert under spec/ --
             its comment included -- or a source paragraph citing one
  asked      every touched paragraph, and every source paragraph citing a
             touched pred: one state per paragraph and name, one question per
             claim cut from it, all in one call
  skipped    a name declared twice under spec/, counted and named; a commit
             touching neither asks nothing and says so

THE BRANCH is the caller's, on each entry's two edges over P(contradicts):
`yes` contradicted, `no` clear, `uncertain` between the edges and `unknown`
where the reading failed. Each entry's
tier decides what is printed: at `advise` each contradicted or unknown claim
with its value or reason; at `shadow` the counts alone. Every call is logged by
the caller, and the log line's fate is printed. THE EXIT STATUS IS 0 on every
path, a failure of this script included: a judgment here never refuses a
commit.

THE CASES are scripts/jev/corpus/<reading>.jsonl, each with the values it was
seen at. Where a reading is known to be wrong, as seen at jev-1.13.0 over three
runs on 2026-09-17, highest P(contradicts) per paragraph:

  docstring-claims
  false flag  check-commit-claim.py, claimBeforeCommit, 0.40-0.55
  false flag  campaign-claim.py, AttributionIsSound, 0.61-0.66
  missed      a flipped claim whose words the cut leaves apart from the name:
              everyCodeHasScenario 0.13-0.17, modelSwitch 0.14-0.15
  in the gap  a before/after swap, tieDiscipline, 0.46-0.51

  reference-claims
  false flag  landing-a-change.md, removeDiscipline, 0.51-0.62: the claim
              holds `commitCheck`'s half of the sentence too
  false flag  reviewing.md, review, 0.50-0.51
  false flag  landing-a-change.md:47, criterion, 0.68-0.75: reuse is "held,
              not skipped", so "cannot waive its scenario" is true
  in the gap  landing-a-change.md, S4c_TestRenameBreak 0.38-0.44; criterion
              in the table rows and at line 32, 0.25-0.33
  missed      flips: commitCheck 0.32-0.35; agentRelease 0.41-0.50 and
              FeaturelessKeeps 0.48-0.50, both on the edge of the gap

Usage: scripts/check-cited-claims.py --staged
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
READINGS = ("docstring-claims", "reference-claims")
REGISTRY = HERE / "jev" / "readings.json"
READER = "check-cited-claims.py --staged"
REFERENCE = re.compile(r"AGENTS\.md|\.claude/skills/[^/]+/references/.+\.md")

DECL = re.compile(r"^\s*(?:private\s+)?(pred|fun|assert)\s+(\w+)")
SIG = re.compile(r"^\s*(?:(?:abstract|one|lone|some|private|var)\s+)*sig\s")
FIELDS = re.compile(r"(?:^|,)\s*(?:var\s+)?(\w+(?:\s*,\s*\w+)*)\s*:(?!:)")
WORD = re.compile(r"\b\w+\b")
BACKTICKED = re.compile(r"`(\w+)`")
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z`(\"'])")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def load_sibling(name):
    """A sibling script as a module, by path: these are scripts, not a package."""
    src = HERE / name
    key = name.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_loader(
        key, importlib.machinery.SourceFileLoader(key, str(src)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def code_lines(lines):
    """Each line with its Alloy comments blanked, the line count kept."""
    out, block = [], False
    for line in lines:
        code, i = "", 0
        while i < len(line):
            if block:
                end = line.find("*/", i)
                if end < 0:
                    i = len(line)
                else:
                    block, i = False, end + 2
            elif line.startswith("/*", i):
                block, i = True, i + 2
            elif line.startswith("--", i) or line.startswith("//", i):
                i = len(line)
            else:
                code += line[i]
                i += 1
        out.append(code)
    return out


def block_end(code, start):
    """The line a brace block opened at or after `start` closes on."""
    depth, opened = 0, False
    for k in range(start, len(code)):
        for ch in code[k]:
            if ch == "{":
                depth, opened = depth + 1, True
            elif ch == "}":
                depth -= 1
        if opened and depth <= 0:
            return k
    return len(code) - 1


def comment_above(lines, i):
    """The first line of the comment sitting directly above line `i`."""
    j = i
    if j > 0 and lines[j - 1].rstrip().endswith("*/"):
        # THE OPENER STARTS ITS LINE: a `/*` inside the text, as a glob like
        # `scripts/*-test.*` carries, is not where the comment began.
        while j > 0 and not lines[j - 1].lstrip().startswith("/*"):
            j -= 1
        return max(j - 1, 0)
    while j > 0 and lines[j - 1].lstrip().startswith(("--", "//")):
        j -= 1
    return j


def declarations(texts):
    """({name: [(path, first, last)]} of every pred, fun and assert, comment
    included; {field: [text]} of every sig field, its comment and its line)."""
    decls, fields = {}, {}
    for path, text in texts.items():
        lines = text.split("\n")
        code = code_lines(lines)
        for i, line in enumerate(code):
            m = DECL.match(line)
            if m:
                decls.setdefault(m.group(2), []).append(
                    (path, comment_above(lines, i), block_end(code, i)))
            if not SIG.match(line) or "{" not in line:
                continue
            end, depth = block_end(code, i), 0
            for k in range(i, end + 1):
                inner = code[k].split("{", 1)[1] if k == i else code[k]
                names = [n.strip() for m in FIELDS.finditer(inner)
                         for n in m.group(1).split(",")]
                if (k == i or depth == 1) and names:
                    first = comment_above(lines, k) if k > i else k
                    body = "\n".join(lines[first:k + 1]).strip()
                    for n in names:
                        fields.setdefault(n, []).append(body)
                depth += code[k].count("{") - code[k].count("}")
    return decls, fields


def pred_text(name, parts, decls, fields, texts):
    """The state's `pred.text`: the parts the entry names, in its order."""
    def whole(entry):
        path, first, last = entry
        return "\n".join(texts[path].split("\n")[first:last + 1])

    own = decls[name][0]
    body = "\n".join(code_lines(whole(own).split("\n")))
    words = list(dict.fromkeys(WORD.findall(body)))
    out = []
    if "comment" in parts or "declaration" in parts:
        out.append(whole(own))
    callees = [whole(decls[w][0]) for w in words
               if w != name and len(decls.get(w, [])) == 1]
    if "callees" in parts and callees:
        out.append("-- what it names:\n" + "\n\n".join(callees))
    read = list(dict.fromkeys(t for w in words if w not in decls
                              for t in fields.get(w, [])))
    if "fields" in parts and read:
        out.append("-- the fields it reads:\n" + "\n\n".join(read))
    return "\n\n".join(out)


def paragraphs(text):
    """[(first line, last line, text)] of every docstring paragraph, 1-based."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    lines, out = text.split("\n"), []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)) or not node.body:
            continue
        first = node.body[0]
        if not (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            continue
        c = first.value
        chunk = lines[c.lineno - 1:c.end_lineno]
        chunk[0] = re.sub(r"^\s*[rRuU]?(\"\"\"|'''|\"|')", "", chunk[0], count=1)
        chunk[-1] = re.sub(r"(\"\"\"|'''|\"|')\s*$", "", chunk[-1], count=1)
        start = None
        for k, line in enumerate(chunk + [""]):
            if line.strip() and start is None:
                start = k
            elif not line.strip() and start is not None:
                out.append((c.lineno + start, c.lineno + k - 1,
                            "\n".join(chunk[start:k])))
                start = None
    return out


def units(text):
    """[(first line, last line, text)] of every markdown paragraph, list item
    and table row, 1-based; a row carries its header line above it, and fenced
    code and headings are no unit."""
    lines, out = text.split("\n"), []
    fence, start, header = False, None, None

    def close(k):
        nonlocal start
        if start is not None:
            body = "\n".join(lines[start:k])
            if header is not None and lines[start].lstrip().startswith("|"):
                body = f"{header}\n{body}"
            out.append((start + 1, k, body))
        start = None
    for k, line in enumerate(lines + [""]):
        s = line.strip()
        if s.startswith("```"):
            close(k)
            fence = not fence
        elif fence:
            continue
        elif not s or s.startswith("#"):
            close(k)
            header = None
        elif s.startswith("|"):
            close(k)
            if header is None:
                header = line
            elif not re.fullmatch(r"\|[\s:|-]+\|", s):
                start = k
        elif re.match(r"([-*]|\d+\.)\s", s):
            close(k)
            start = k
        elif start is None:
            start = k
    return out


def cited(paragraph, decls, prefilter):
    """The names `paragraph` cites: backticked, declared under spec/, and a
    plain name only in a sentence the entry's prefilter anchors."""
    names = [n for n in dict.fromkeys(BACKTICKED.findall(paragraph)) if n in decls]
    plain = prefilter.get("plain_name")
    if not plain:
        return names
    sentences = SENTENCE.split(" ".join(paragraph.split()))

    def anchored(name):
        return any(re.search(prefilter["anchored_by"], s)
                   or any(t != name and t in decls and not re.fullmatch(plain, t)
                          for t in BACKTICKED.findall(s))
                   for s in sentences if f"`{name}`" in s)
    return [n for n in names if not re.fullmatch(plain, n) or anchored(n)]


def claims(paragraph, name, cut):
    """The claims about `name`: its sentences, split at the entry's
    separators, a definition following the name keeping the name before it."""
    tick = f"`{name}`"
    split = lambda s, seps: re.split("|".join(map(re.escape, seps)), s)  # noqa: E731
    out = []
    for sentence in SENTENCE.split(" ".join(paragraph.split())):
        for clause in split(sentence, cut["split_at"]):
            if tick not in clause:
                continue
            kept = False
            for piece in split(clause, cut["definition_at"]):
                piece = piece.strip()
                if tick in piece:
                    out.append(piece)
                    kept = True
                elif kept and piece:
                    out.append(f"{tick}: {piece}")
    return list(dict.fromkeys(out))


def overlaps(ranges, first, last):
    return any(a <= last and first <= b for a, b in ranges)


def staged_hunks(diff):
    """{path: [(first, last)]} of the new side of every staged hunk, from a
    diff taken with `--no-prefix`; a pure deletion `+N,0` sat between lines N
    and N+1, and touches both."""
    out, path = {}, None
    for line in diff.split("\n"):
        if line.startswith("+++ "):
            path = None if line == "+++ /dev/null" else line[4:]
        elif path and (m := HUNK.match(line)):
            first = int(m.group(1))
            count = int(m.group(2)) if m.group(2) is not None else 1
            last = first + count - 1 if count else first + 1
            out.setdefault(path, []).append((first, last))
    return out


def targets(hunks, texts, decls, cut, prefilter):
    """The (path, first line, paragraph, name) states to ask, the pred names
    touched, and the cited names skipped as declared twice; `cut` gives a
    source path's paragraphs, or None for a path that is not a source."""
    touched = {n for n, where in decls.items() if len(where) == 1
               for path, first, last in where
               if overlaps(hunks.get(path, []), first + 1, last + 1)}
    asked, skipped = {}, set()
    for path, text in texts.items():
        if not (paragraphs_of := cut(path)):
            continue
        for first, last, para in paragraphs_of(text):
            mine = overlaps(hunks.get(path, []), first, last)
            for name in cited(para, decls, prefilter):
                if not (mine or name in touched):
                    continue
                if len(decls[name]) > 1:
                    skipped.add(name)
                    continue
                asked[path, first, name] = para
    return ([(p, f, para, n) for (p, f, n), para in asked.items()],
            touched, skipped)


def questions(entry, found):
    q = entry["question"]
    spec = {k: v for k, v in q.items() if k in ("type", "criteria")}
    spec.update(entry["thresholds"])
    return {f"c{i}": dict(spec, instructions={"question": q["instructions"],
                                              "claim": c})
            for i, c in enumerate(found)}


def ask_all(entry, states, jev, env=None):
    """[(label, claims, Reading)] for every state, asked six at a time."""
    parts, cut = entry["state"]["pred"]["text"], entry["state"]["claims"]

    def one(target):
        label, paragraph, name, text = target
        found = claims(paragraph, name, cut)
        state = {"paragraph": paragraph, "pred": {"name": name, "text": text}}
        return label, found, jev.ask(READER, label, state,
                                     questions(entry, found), env=env)
    with ThreadPoolExecutor(6) as pool:
        return list(pool.map(one, states))


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          check=True).stdout


def index_texts(paths):
    """{path: text} of each path as the index holds it."""
    if not paths:
        return {}
    feed = "".join(f":{p}\n" for p in paths).encode()
    raw = subprocess.run(["git", "cat-file", "--batch"], input=feed,
                         capture_output=True, check=True).stdout
    out, pos = {}, 0
    for p in paths:
        header_end = raw.index(b"\n", pos)
        header = raw[pos:header_end].split()
        pos = header_end + 1
        if len(header) < 3 or header[1] != b"blob":
            continue
        size = int(header[2])
        out[p] = raw[pos:pos + size].decode("utf-8", "replace")
        pos += size + 1
    return out


def report(results, entry, out):
    # THE TIER DECIDES WHAT IS SHOWN, per rule-check#455's registry: `shadow`
    # logs every answer and prints only the counts; `advise` prints each claim
    # read contradicted or unknown.
    shown = entry["tier"] != "shadow"
    # THE GAP IS A COUNT OF ITS OWN. `branch` answers four words and the line
    # used to print three, so a reading whose claims mostly land between the
    # two edges -- `model-comment`'s do -- printed "0, 0, 0" over a call it had
    # made and answered.
    counts = {"yes": 0, "no": 0, "uncertain": 0, "unknown": 0}
    logged = set()
    for label, found, reading in results:
        logged.add(reading.logged)
        for i, claim in enumerate(found):
            a = reading.answers[f"c{i}"]
            counts[a.word] = counts.get(a.word, 0) + 1
            p = ((a.raw or {}).get("probabilities") or {}).get(
                entry["thresholds"]["option"])
            if not shown:
                continue
            if a.word == "yes":
                print(f"  contradicts {p:.2f}  {label}: {claim}", file=out)
            elif a.word == "unknown":
                print(f"  unknown  {label}: {claim} -- {a.why}", file=out)
    print(f"  {counts['yes']} claim(s) read as contradicted, {counts['no']} "
          f"clear, {counts['uncertain']} in the gap, {counts['unknown']} "
          f"unknown; tier `{entry['tier']}`, exit status unmoved", file=out)
    for line in sorted(logged):
        print(f"  answers {line}", file=out)


def main(argv, out=sys.stdout, env=None):
    if argv != ["--staged"]:
        print("Usage: scripts/check-cited-claims.py --staged", file=sys.stderr)
        return 2
    try:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        # `--no-prefix` PINNED: a user's `diff.noprefix` changes what `+++`
        # carries, and a parser reading `b/` found no file at all.
        hunks = staged_hunks(git("diff", "--cached", "-U0", "-M", "--no-color",
                                 "--no-ext-diff", "--no-prefix"))
        in_scripts_dir = load_sibling("check-tree-shape.py").in_scripts_dir
        sources = {
            "docstring-claims": lambda p: (
                paragraphs if p.endswith(".py") and in_scripts_dir(p) else None),
            "reference-claims": lambda p: (
                units if REFERENCE.fullmatch(p) else None),
        }
        is_spec = lambda p: p.startswith("spec/") and p.endswith(".als")  # noqa: E731
        wanted = lambda p: is_spec(p) or any(  # noqa: E731
            sources[r](p) for r in READINGS if r in registry)
        relevant = [p for p in hunks if wanted(p)]
        if not relevant:
            print(f"check-cited-claims: {len(hunks)} staged file(s), none a "
                  f"spec/ module or a source; nothing asked", file=out)
            return 0
        texts = index_texts([p for p in git("ls-files", "-z").split("\0")
                             if wanted(p)])
        spec = {p: t for p, t in texts.items() if is_spec(p)}
        decls, fields = declarations(spec)
        jev = None
        for reading in READINGS:
            if reading not in registry:
                print(f"check-cited-claims: no entry `{reading}` in the "
                      f"registry; not asked", file=out)
                continue
            entry = registry[reading]
            found, touched, skipped = targets(hunks, texts, decls,
                                              sources[reading],
                                              entry.get("prefilter", {}))
            parts = entry["state"]["pred"]["text"]
            states = [(f"{p}:{f} `{n}`", para, n,
                       pred_text(n, parts, decls, fields, spec))
                      for p, f, para, n in found]
            print(f"check-cited-claims `{reading}`: {len(relevant)} staged "
                  f"file(s) read; {len(touched)} pred(s) touched; "
                  f"{len(states)} paragraph citation(s) asked"
                  + (f"; skipped as declared twice: {', '.join(sorted(skipped))}"
                     if skipped else ""), file=out)
            if states:
                jev = jev or load_sibling("campaign-jev.py")
                report(ask_all(entry, states, jev, env), entry, out)
    except Exception as e:  # noqa: BLE001 -- a reading never refuses a commit
        print(f"check-cited-claims: could not read the commit "
              f"({e.__class__.__name__}: {e}); nothing asked, exit status "
              f"unmoved", file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
