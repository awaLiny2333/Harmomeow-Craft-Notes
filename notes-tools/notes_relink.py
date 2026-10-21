#!/usr/bin/env python3
"""Rewrite relative markdown links in notes/ after the 20-design reorganisation.

Two cases:
  1. a link whose TARGET file moved  -> point it at the new location;
  2. a link inside a file that ITSELF moved -> recompute every relative link against the
     file's new base directory (a moved file's `../00-current/x.md` becomes `../../00-current/x.md`).

Only link destinations `](target)` are rewritten (fragments preserved); http(s)/mailto and
anchor-only links are left alone. Prints how many links changed.

Usage: notes_relink.py [--dry-run]
"""
import os
import re
import sys

NOTES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # notes/ (this file lives in notes/notes-tools/)

# old (relative to notes/) -> new (relative to notes/)
# NOTE: this map is per-move-batch and is REPLACED each time the script is used (the script is only
# meant to be run immediately after a `git mv` batch).  Two earlier batches (the 2026-09-15 10-research
# cleanup and the 20-design reorganisation) are already applied and their links already resolve -- they
# must NOT be kept here, because a stale "new -> old" entry makes `base_old` wrong for a file that was
# moved in an earlier batch, which re-bases its links one level too shallow.
# Batch B+C (render/perf convergence + research/adaptation cleanup, 2026-10-02):
MOVED = {
    "20-design/render/Vulkan后端-跟进与结案.md": "90-archive/Vulkan后端-跟进与结案.md",
    "20-design/render/Vulkan后端-实现历程与原理.md": "20-design/render/Vulkan后端-实现与原理.md",
    "20-design/render/Vulkan后端-绕过可行性-调研与方案.md": "20-design/render/Vulkan后端-取证存档.md",
    "20-design/lwjgl/LWJGL3单代收敛-决策依据.md": "20-design/lwjgl/LWJGL3世代管理-方案.md",
    "40-adaptation/launcher-rebuild.md": "90-archive/launcher-rebuild.md",
    "10-research/hmcl.md": "10-research/hmcl-存储模型.md",
}

OLD_ABS = {os.path.normpath(os.path.join(NOTES, o)): os.path.normpath(os.path.join(NOTES, n))
           for o, n in MOVED.items()}
NEW_ABS = {v: k for k, v in OLD_ABS.items()}          # new abs -> old abs
LINK = re.compile(r"\]\(([^)\s]+?)(#[^)\s]*)??\)")


def main():
    dry = "--dry-run" in sys.argv
    total = 0
    touched = []
    for root, dirs, files in os.walk(NOTES):
        if "/.git" in root:
            continue
        for fn in files:
            if not (fn.endswith(".md") or fn.endswith(".txt")):
                continue
            path = os.path.join(root, fn)
            base_new = os.path.dirname(path)
            # base the file's links were authored against (before the move)
            base_old = os.path.dirname(NEW_ABS.get(path, path))
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            n = [0]

            def repl(m):
                target, frag = m.group(1), m.group(2) or ""
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    return m.group(0)
                # IDEMPOTENCY GUARD (2026-09-15): if the link already resolves from the file's
                # CURRENT dir, it has been rewritten before -- leave it alone. Without this a
                # second run re-bases every already-fixed link (one `../` too deep).
                if os.path.exists(os.path.normpath(os.path.join(base_new, target))):
                    return m.group(0)
                resolved = os.path.normpath(os.path.join(base_old, target))
                new_abs = OLD_ABS.get(resolved, resolved)
                new_rel = os.path.relpath(new_abs, base_new)
                if new_rel != target:
                    n[0] += 1
                    return "](" + new_rel + frag + ")"
                return m.group(0)

            new_text = LINK.sub(repl, text)
            if new_text != text:
                total += n[0]
                touched.append("%s (%d)" % (os.path.relpath(path, NOTES), n[0]))
                if not dry:
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(new_text)
    print("links rewritten: %d, files touched: %d" % (total, len(touched)))
    for t in touched:
        print("  " + t)


if __name__ == "__main__":
    main()
