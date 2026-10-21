#!/usr/bin/env python3
"""Check that relative markdown links in the notes repo resolve.

Usage: python3 check_links.py [ROOT]      # default ROOT = cwd
       from the workspace root:  python3 notes/notes-tools/check_links.py notes
       from inside notes/:       python3 notes-tools/check_links.py .

NOTE: passing a ROOT that does not exist used to report "checked 0 links / all OK",
a silent false green (e.g. `check_links.py notes` run from inside notes/ looks for
`notes/notes`). That is now a hard error.
Non-UTF-8 files (plain-text dumps) are decoded leniently instead of aborting the run.
"""
import os, re, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
if not os.path.isdir(ROOT):
    sys.exit("error: root directory not found: %r\n"
             "hint: from the workspace root use 'notes'; from inside notes/ use '.'" % ROOT)
LINK = re.compile(r"\]\(([^)]+)\)")
SKIP_PREFIX = ("http://", "https://", "#", "mailto:", "data:")
bad = []
n = 0
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d != ".git"]
    for fn in filenames:
        if not fn.endswith((".md", ".txt")):
            continue
        path = os.path.join(dirpath, fn)
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        for i, line in enumerate(lines, 1):
            for m in LINK.finditer(line):
                t = m.group(1).strip()
                if t.startswith(SKIP_PREFIX):
                    continue
                t = t.split("#")[0]
                if not t:
                    continue
                n += 1
                if not os.path.exists(os.path.normpath(os.path.join(dirpath, t))):
                    bad.append("%s:%d  %s" % (path, i, m.group(1)))
print("checked %d relative links" % n)
if bad:
    print("BROKEN (%d):" % len(bad))
    for b in bad:
        print("  " + b)
    sys.exit(1)
print("all OK")
