"""CLI for rigged.

    rigged patch.diff                 analyse a diff file
    git diff | rigged -               analyse a diff from stdin
    rigged --json patch.diff          machine-readable output
    rigged --problem "..." patch.diff  pass the task description for input-hardcoding checks

Exit status: 0 clean, 1 suspicious, 2 gaming, 3 usage/parse error — so CI can gate a
merge: ``rigged "$PATCH" || echo "possible test-gaming"``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .detect import analyze, CLEAN, SUSPICIOUS, GAMING

_EXIT = {CLEAN: 0, SUSPICIOUS: 1, GAMING: 2}
_COL = {CLEAN: "\033[32m", SUSPICIOUS: "\033[33m", GAMING: "\033[31m"}
_ICON = {CLEAN: "✓", SUSPICIOUS: "⚠", GAMING: "✗"}
_R, _D, _B = "\033[0m", "\033[2m", "\033[1m"


def _color():
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _pretty(v, color):
    def c(x):
        return x if color else ""
    out = [f"{c(_COL[v.verdict])}{c(_B)}{_ICON[v.verdict]} {v.verdict.upper()}{c(_R)}"
           f"  {c(_D)}score {v.score:.1f} · {v.files_changed} file(s), "
           f"{v.test_files_changed} test{c(_R)}"]
    out.append(f"  {v.summary}")
    for s in v.signals:
        out.append(f"  {c(_COL[GAMING if s.weight >= 3 else SUSPICIOUS])}•{c(_R)} {s.message}")
        if s.line:
            out.append(f"      {c(_D)}{s.file}: {s.line.strip()[:90]}{c(_R)}")
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(prog="rigged",
                                description="Detect when a code patch games the tests instead of fixing the bug.")
    p.add_argument("patch", nargs="?", help="path to a unified diff ('-' for stdin)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--problem", default="", help="the task description (improves input-hardcoding checks)")
    p.add_argument("--quiet", "-q", action="store_true")
    a = p.parse_args(argv)

    if a.patch == "-" or (a.patch is None and not sys.stdin.isatty()):
        diff = sys.stdin.read()
    elif a.patch is None:
        p.print_help()
        return 3
    else:
        with open(a.patch, encoding="utf-8", errors="replace") as f:
            diff = f.read()

    v = analyze(diff, a.problem)
    if a.json:
        print(json.dumps(v.to_json(), indent=2))
    elif not a.quiet:
        print(_pretty(v, _color()))
    return _EXIT.get(v.verdict, 3)


if __name__ == "__main__":
    sys.exit(main())
