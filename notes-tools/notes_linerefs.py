#!/usr/bin/env python3
"""List every `file:line` reference in the notes, so LINE DRIFT becomes visible.

Why this exists: the three mandatory notes checks all look at *other* failure modes --
  * check_links.py      validates `[text](target)` links,
  * notes_stalepaths.py catches path mentions that no longer resolve,
  * notes_statusdup.py  catches live-status words outside their single home.
NONE of them notices a `Foo.ets:472-511` reference whose LINE NUMBERS drifted after the
code moved. A stale `path:line` is the quietest authority rot in this repo: the link still
resolves, the path still exists, only the line is wrong -- and it reads as authoritative.

This is the FOURTH check, and it is deliberately INFORMATIONAL, not a gate: it does not
judge right/wrong, it just lists the `file:line` references a human should re-verify.
Exit code is 0 by default; pass --strict to make any hit fail (for a future upgrade).
The SYM bucket (function/symbol names) is the loosest: it can catch `key:value` field
noise such as `spec:0` / `format:1`, easy to dismiss by eye -- FILE and BARE are the
high-precision buckets.

Recognised reference shapes (back-ticked or in prose). Markdown link DISPLAY text is
ignored on purpose -- that is a label owned by check_links.py, not a reference here:
  * `common/data/JavaPolicy.ets:112-127`                    path + ':N' / ':N-M'   -> FILE
  * `ref/HMCL/.../JavaVersionConstraint.java:179-223`                              -> FILE
  * `Foo.java:123` / `Bar.cpp:456` / `A/B.ets:789`                                 -> FILE
  * `validatePaths:104` / `collectJarSources:869`  (function name)                 -> SYM
  * `Class.method:117-160` / `GameRenderer:475`    (qualified symbol)             -> SYM
  * `:1723` / `:315-323`   (bare; continues the previous ref on the same line)     -> BARE

Usage: notes_linerefs.py [--include-archive] [--strict] [notes_root]
  --include-archive  also scan 90-archive/** (history is allowed to be stale)
  --strict           exit 1 if any reference is found (default: exit 0, hints only)
notes_root defaults to the parent of this script's directory.
"""
import os
import re
import signal
import sys

# let `... | head` / `... | grep` close the pipe without a BrokenPipeError traceback
try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    pass

# source-file extensions that make a token a *file* reference
_EXT = ("ets java cpp cc cxx c h hpp hh inl kt kts gradle json json5 toml xml "
        "properties md txt yaml yml sh bash py js ts tsx so jar apk hap hsp")
EXT_RE = re.compile(r"\.(?:" + _EXT.replace(" ", "|") + r")$", re.IGNORECASE)

# a target name (path or symbol, may be empty) followed by ':N' / ':N-M' / ':N,M' / ':N/M'
# name chars include < > $ so placeholders like `<shim>.c:117` and `$SDK/.../sched.h:92`
# are captured whole instead of collapsing to a stray `c:117`
REF = re.compile(r"([A-Za-z0-9_<][A-Za-z0-9_./\\+@\-<>$]*)?(:\d+(?:[-,/]\d+)*)")

# whole markdown links `[display](target)`: skipped, the display text is a label.
# The target is captured so a bare `:N` glued to the `)` (`` [`x.md`](x.md):3 ``) can be
# attributed to the linked file.
LINK = re.compile(r"\[[^\]]*\]\(([^)]*)\)")
# URLs, so a `host:port` inside one is not mistaken for a `symbol:line`
URL = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://[^\s\)\]<>`\"']+")


def classify(name):
    """FILE if it looks like a path/filename, else SYM (a bare symbol)."""
    if "/" in name or "\\" in name or EXT_RE.search(name):
        return "FILE"
    return "SYM"


def target_of(name):
    """The aggregate key: basename for FILE refs, the symbol itself for SYM."""
    if "/" in name or "\\" in name or EXT_RE.search(name):
        return name.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return name


def snippet(line, start, end, width=78):
    left = max(0, start - 18)
    right = min(len(line), end + 26)
    s = re.sub(r"\s+", " ", line[left:right]).strip()
    if len(s) > width:
        s = s[: width - 1] + "\u2026"
    return ("\u2026" if left else "") + s + ("\u2026" if right < len(line) else "")


def main():
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__.strip())
        return 0
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    with_archive = "--include-archive" in sys.argv
    strict = "--strict" in sys.argv
    root = args[0] if args else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        sys.stderr.write("error: notes root not found: %r\n"
                         "hint: from the workspace root use 'notes'; "
                         "from inside notes/ use '.'\n" % root)
        return 2

    counts = {"FILE": 0, "SYM": 0, "BARE": 0}
    by_target = {}
    total = 0
    files = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        if not with_archive and (rel_dir == "90-archive" or rel_dir.startswith("90-archive/")):
            dirnames[:] = []
            continue
        for fn in sorted(filenames):
            if not fn.endswith(".md"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
            hits = []
            for i, line in enumerate(lines, 1):
                # spans to ignore: whole markdown links + URLs
                linkms = list(LINK.finditer(line))
                skip = [m.span() for m in linkms] + \
                       [m.span() for m in URL.finditer(line)]
                # end offset of each link -> basename of its target, so `` [x](y.md):3 ``
                # attributes the bare `:3` to `y.md`
                link_end = {}
                for m in linkms:
                    b = m.group(1).split("#")[0].strip().replace("\\", "/")
                    if b:
                        link_end[m.end()] = b.rstrip("/").rsplit("/", 1)[-1]

                def ignored(a, b, _skip=skip):
                    return any(a < s2 and s1 < b for s1, s2 in _skip)

                last = None  # last FILE/SYM target on this line, for bare `:N`
                for m in REF.finditer(line):
                    name, lspec = m.group(1), m.group(2)
                    if ignored(m.start(), m.end()):
                        continue
                    if name:
                        if not re.search(r"[A-Za-z]", name):
                            continue  # 22:16 / 127.0.0.1:40229 -- not a line ref
                        kind = classify(name)
                        tgt = target_of(name)
                    else:
                        kind = "BARE"  # a bare `:N` continues the previous ref/link
                        tgt = link_end.get(m.start()) or last or "(bare :N)"
                    # `:3.3.3` / `lwjgl:3.4.3` / `gson:2.13.1`: a digit-N directly followed
                    # by '.' is a version / maven coord, never a line ref
                    if kind != "FILE" and line[m.end():m.end() + 1] == ".":
                        continue
                    last = tgt
                    counts[kind] += 1
                    total += 1
                    by_target[tgt] = by_target.get(tgt, 0) + 1
                    hits.append((i, kind, (name or "") + lspec,
                                 snippet(line, m.start(), m.end())))
            if hits:
                files += 1
                print("== " + rel)
                for i, kind, tok, snip in hits:
                    print("  :%-5d %-4s %-38s | %s" % (i, kind, tok, snip))

    print("\nline references: %d (FILE %d / SYM %d / BARE %d) in %d files"
          % (total, counts["FILE"], counts["SYM"], counts["BARE"], files))
    if by_target:
        ranked = sorted(by_target.items(), key=lambda kv: (-kv[1], kv[0]))
        print("by target (top %d of %d):" % (min(30, len(ranked)), len(ranked)))
        for tgt, n in ranked[:30]:
            print("  %4d  %s" % (n, tgt))
    print("(informational: exit 0 by default; --strict to fail on hits)")
    return 1 if (strict and total) else 0


if __name__ == "__main__":
    sys.exit(main())
