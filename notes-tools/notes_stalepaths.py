#!/usr/bin/env python3
"""Find STALE path mentions in the notes: path-looking tokens that no longer resolve.

Why this exists: `check_links.py` only validates `[text](target)` links. A path written as
plain text or as a bare back-ticked token (`` `20-design/perf/foo.md` ``) is invisible to it,
so a rename silently leaves a 404 in a document -- exactly the failure that hid behind a
"all OK" report.

What it checks, for every .md under notes/ (excluding 90-archive/ by default, which is
append-only historical text):
  * back-ticked tokens that look like a path (`a/b.md`, `foo.txt`, `../x/y.md`) that do not
    resolve relative to the file's directory;
  * `《name.md》`-style prose mentions that do not resolve;
  * `--loose` additionally reports bare `xxx.md`/`xxx.txt` words in prose (noisier).

A token counts as a path if it ends in .md/.txt (or contains a '/' and has a known docs
extension) and is not a URL. Suggestions are printed when a same-basename file exists
elsewhere under notes/, so the fix is a one-liner.

Usage: notes_stalepaths.py [--loose] [--include-archive] [notes_root]
Exit code 1 if any stale path is found (so it can gate a doc commit).
"""
import os
import re
import sys

NOTES = None  # set in main


def token_is_path(tok):
    if tok.startswith(("http://", "https://", "#", "/")):
        return tok.startswith("/") and tok.endswith((".md", ".txt"))
    return tok.endswith((".md", ".txt"))


def main():
    global NOTES
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    loose = "--loose" in sys.argv
    with_archive = "--include-archive" in sys.argv
    root = args[0] if args else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    NOTES = os.path.abspath(root)

    # index of every doc basename -> relpath, for suggestions
    basenames = {}
    for r, _d, fs in os.walk(NOTES):
        if "/.git" in r:
            continue
        for f in fs:
            if f.endswith((".md", ".txt")):
                basenames.setdefault(f, []).append(os.path.relpath(os.path.join(r, f), NOTES))

    tick = re.compile(r"`([^`\n|]+?)`")
    angle = re.compile(r"《([^》\n]{2,120}?\.(?:md|txt))》")
    bare = re.compile(r"(?<![`\w/.\-])([\w.\-]+/[\w.\-/]+?\.(?:md|txt))(?![`\w])")

    total = 0
    for r, _d, fs in os.walk(NOTES):
        if "/.git" in r or (not with_archive and "/90-archive" in r):
            continue
        for f in sorted(fs):
            if not f.endswith(".md"):
                continue
            path = os.path.join(r, f)
            rel = os.path.relpath(path, NOTES)
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
            found = []
            for i, line in enumerate(lines, 1):
                # spans of every markdown link's DISPLAY text: a path mentioned there is a
                # label, not a path -- check_links.py owns the real target
                disp = [m.span(1) for m in re.finditer(r"\[([^\]]*)\]\([^)]*\)", line)]
                cands = list(tick.findall(line)) + list(angle.findall(line))
                if loose:
                    cands += bare.findall(line)
                for tok in cands:
                    tok = tok.strip()
                    if not token_is_path(tok) or "://" in tok:
                        continue
                    # skip when the token is a link target `](tok)` or sits inside a link's
                    # display text `[ ... tok ... ](target)`
                    if re.search(r"\]\(" + re.escape(tok) + r"\)", line):
                        continue
                    if any(line.find(tok, a, b) >= 0 for a, b in disp):
                        continue
                    # paths into the sibling app repo / surrounding workspace are
                    # intentionally not resolvable from inside the notes repo
                    # (`src/`, `./src/` = source paths inside the sibling app repo)
                    if re.match(r"^(tools|stuffs|ref|libs|src|\./src|Harmomeow-Craft-Launcher|"
                                r"\.\./\.\./Harmomeow-Craft-Launcher)/", tok):
                        continue
                    # globs and placeholders are not real paths
                    if any(ch in tok for ch in "{}*<>"):
                        continue
                    if os.path.exists(os.path.normpath(os.path.join(r, tok))):
                        continue
                    # a bare doc name (`现状基线.md` §5) is a shorthand citation, not a
                    # path: fine as long as a file with that name exists somewhere in notes
                    if "/" not in tok and os.path.basename(tok) in basenames:
                        continue
                    # a bare non-.md token (options.txt, manifest.txt, ...) is usually a
                    # game/tool file, not a notes doc -- report only if we can suggest one
                    if "/" not in tok and not tok.endswith(".md") \
                            and os.path.basename(tok) not in basenames:
                        continue
                    found.append((i, tok))
            if found:
                print("== " + rel)
                for i, tok in found:
                    total += 1
                    sug = ""
                    base = os.path.basename(tok)
                    if base in basenames:
                        sug = "   -> did you mean: " + " | ".join(sorted(basenames[base]))
                    print("  :%-5d %s%s" % (i, tok, sug))
    print("\nstale path mentions: %d" % total)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
