"""A small unified-diff parser.

Turns a ``git diff`` / ``diff -u`` patch into a structured form the detector can
reason about: per-file hunks, added and removed lines, and a classification of
each file as source / test / config. No external dependencies.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field
from typing import Optional

__all__ = ["FileDiff", "Hunk", "Line", "parse_diff", "classify_path"]

_HUNK_RE = re.compile(r"^@@ -(?P<os>\d+)(?:,(?P<ol>\d+))? \+(?P<ns>\d+)(?:,(?P<nl>\d+))? @@(?P<ctx>.*)$")


@dataclass
class Line:
    kind: str          # '+', '-', ' '
    text: str          # content without the leading +/-/space
    old_no: Optional[int]
    new_no: Optional[int]


@dataclass
class Hunk:
    old_start: int
    new_start: int
    header: str
    lines: list = field(default_factory=list)   # list[Line]

    @property
    def added(self):
        return [ln for ln in self.lines if ln.kind == "+"]

    @property
    def removed(self):
        return [ln for ln in self.lines if ln.kind == "-"]


@dataclass
class FileDiff:
    old_path: Optional[str]
    new_path: Optional[str]
    hunks: list = field(default_factory=list)   # list[Hunk]
    is_new: bool = False
    is_delete: bool = False
    is_rename: bool = False
    kind: str = "source"      # source | test | config | docs | data | unknown

    @property
    def path(self) -> str:
        return self.new_path or self.old_path or "?"

    @property
    def added_lines(self):
        return [ln for h in self.hunks for ln in h.added]

    @property
    def removed_lines(self):
        return [ln for h in self.hunks for ln in h.removed]

    def added_text(self) -> str:
        return "\n".join(ln.text for ln in self.added_lines)

    def removed_text(self) -> str:
        return "\n".join(ln.text for ln in self.removed_lines)


# ---- path classification --------------------------------------------------- #

_TEST_RE = re.compile(
    r"(^|/)(tests?|testing|spec|specs|__tests__)(/|$)"           # test directories
    r"|(^|/)test_[^/]*\.\w+$"                                     # test_foo.py
    r"|(^|/)[^/]*_test\.\w+$"                                     # foo_test.py / foo_test.go
    r"|(^|/)[^/]*\.(test|spec)\.\w+$"                             # foo.test.js / foo.spec.ts
    r"|(^|/)conftest\.py$",
    re.I)
# JVM / C# test classes: FooTest.java — case-sensitive T, restricted extensions, so this
# never catches Python files like `unittest.py` or `latest.py`.
_JVM_TEST_RE = re.compile(r"(^|/)[A-Za-z0-9]*(Test|Tests|Spec|IT)\.(java|kt|kts|scala|cs|groovy)$")
_CONFIG_RE = re.compile(
    r"(^|/)(conftest\.py|pytest\.ini|tox\.ini|setup\.cfg|pyproject\.toml|\.coveragerc|"
    r"jest\.config\.\w+|\.mocharc\.\w+|vitest\.config\.\w+|karma\.conf\.\w+|"
    r"phpunit\.xml(\.dist)?|\.rspec|Makefile|noxfile\.py|\.github/workflows/[^/]+\.ya?ml)$", re.I)
_DOCS_RE = re.compile(r"\.(md|rst|txt|adoc)$|(^|/)(docs?|CHANGELOG|CHANGES|HISTORY)", re.I)
_DATA_RE = re.compile(r"\.(json|ya?ml|csv|lock|cfg|ini|toml|xml|sql)$", re.I)


def classify_path(path: str) -> str:
    p = path.strip()
    if _CONFIG_RE.search(p):
        return "config"
    if _TEST_RE.search(p) or _JVM_TEST_RE.search(p):
        return "test"
    if _DOCS_RE.search(p):
        return "docs"
    if _DATA_RE.search(p):
        return "data"
    return "source"


# ---- parser ---------------------------------------------------------------- #

def _strip_prefix(path: str) -> str:
    if path in ("/dev/null", ""):
        return path
    # strip a/ b/ git prefixes
    if path[:2] in ("a/", "b/"):
        path = path[2:]
    return posixpath.normpath(path)


def parse_diff(text: str) -> list:
    """Parse a unified diff into a list of :class:`FileDiff`. Tolerant of junk lines."""
    files: list[FileDiff] = []
    cur: Optional[FileDiff] = None
    cur_hunk: Optional[Hunk] = None
    old_no = new_no = 0
    lines = text.splitlines()
    i = 0
    pending_old = None

    def close_file():
        nonlocal cur, cur_hunk
        if cur is not None:
            cur.kind = classify_path(cur.path)
            files.append(cur)
        cur, cur_hunk = None, None

    while i < len(lines):
        ln = lines[i]
        if ln.startswith("diff --git"):
            close_file()
            m = re.match(r"diff --git a/(.+?) b/(.+)$", ln)
            cur = FileDiff(old_path=_strip_prefix("a/" + m.group(1)) if m else None,
                           new_path=_strip_prefix("b/" + m.group(2)) if m else None)
            cur_hunk = None
            pending_old = None
            i += 1
            continue
        if ln.startswith("new file mode"):
            if cur: cur.is_new = True
            i += 1; continue
        if ln.startswith("deleted file mode"):
            if cur: cur.is_delete = True
            i += 1; continue
        if ln.startswith("rename from") or ln.startswith("rename to"):
            if cur: cur.is_rename = True
            i += 1; continue
        if ln.startswith("--- "):
            p = ln[4:].strip()
            pending_old = None if p == "/dev/null" else _strip_prefix(p)
            if cur is None:
                cur = FileDiff(old_path=pending_old, new_path=None)
            else:
                cur.old_path = pending_old if pending_old else cur.old_path
            i += 1; continue
        if ln.startswith("+++ "):
            p = ln[4:].strip()
            np = None if p == "/dev/null" else _strip_prefix(p)
            if cur is None:
                cur = FileDiff(old_path=pending_old, new_path=np)
            else:
                cur.new_path = np if np else cur.new_path
            if p == "/dev/null":
                cur.is_delete = True
            if pending_old is None and cur.old_path is None:
                cur.is_new = True
            i += 1; continue
        m = _HUNK_RE.match(ln)
        if m:
            if cur is None:
                cur = FileDiff(old_path=None, new_path=None)
            old_no = int(m.group("os"))
            new_no = int(m.group("ns"))
            cur_hunk = Hunk(old_start=old_no, new_start=new_no, header=m.group("ctx").strip())
            cur.hunks.append(cur_hunk)
            i += 1; continue
        if cur_hunk is not None and ln[:1] in ("+", "-", " "):
            kind = ln[0]
            text_ = ln[1:]
            if kind == "+":
                cur_hunk.lines.append(Line("+", text_, None, new_no)); new_no += 1
            elif kind == "-":
                cur_hunk.lines.append(Line("-", text_, old_no, None)); old_no += 1
            else:
                cur_hunk.lines.append(Line(" ", text_, old_no, new_no)); old_no += 1; new_no += 1
            i += 1; continue
        if ln.startswith("\\ No newline"):
            i += 1; continue
        # unknown / index lines
        i += 1

    close_file()
    return files
