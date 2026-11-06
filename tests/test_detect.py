"""Tests for the diff parser and the test-gaming detector."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bench"))
from rigged import analyze, parse_diff, classify_path, CLEAN, SUSPICIOUS, GAMING
from gold import GOLD

D = "diff --git a/{f} b/{f}\n--- a/{f}\n+++ b/{f}\n"


def mk(f, body):
    return D.format(f=f) + body


def verdict(diff, problem=""):
    return analyze(diff, problem).verdict


# ---------------- path classification ---------------- #
@pytest.mark.parametrize("path,kind", [
    ("tests/test_foo.py", "test"),
    ("src/foo_test.go", "test"),
    ("pkg/FooTest.java", "test"),
    ("a/b.test.js", "test"),
    ("conftest.py", "config"),
    ("pytest.ini", "config"),
    ("src/_pytest/unittest.py", "source"),   # must NOT be a test
    ("mypkg/latest.py", "source"),
    ("src/contest.py", "source"),
    ("README.md", "docs"),
    ("src/app.py", "source"),
])
def test_classify_path(path, kind):
    assert classify_path(path) == kind


# ---------------- diff parsing ---------------- #
def test_parse_basic():
    d = mk("a.py", "@@ -1,2 +1,2 @@\n-    return 1\n+    return 2\n")
    files = parse_diff(d)
    assert len(files) == 1
    assert files[0].path == "a.py"
    assert len(files[0].added_lines) == 1
    assert files[0].added_lines[0].text == "    return 2"


def test_parse_multi_file():
    d = (mk("src/a.py", "@@ -1,1 +1,1 @@\n-x\n+y\n")
         + mk("tests/test_a.py", "@@ -1,1 +1,1 @@\n-assert x\n+assert y\n"))
    files = parse_diff(d)
    assert len(files) == 2
    assert {f.kind for f in files} == {"source", "test"}


def test_parse_garbage_is_safe():
    for junk in ["", "not a diff", "@@ bad @@", "diff --git nonsense"]:
        analyze(junk)  # must not raise


# ---------------- clean cases ---------------- #
def test_real_fix_is_clean():
    assert verdict(mk("src/calc.py", "@@ -1,1 +1,1 @@\n-    return a - b\n+    return a + b\n")) == CLEAN


def test_adding_tests_is_clean():
    d = mk("tests/test_new.py", "@@ -1,1 +1,4 @@\n import m\n+def test_x():\n+    assert m.f() == 1\n+    assert m.g() == 2\n")
    assert verdict(d) == CLEAN


def test_adding_asserts_is_clean():
    d = mk("tests/test_a.py", "@@ -1,3 +1,4 @@\n def test_a():\n     r = f()\n+    assert r.ok\n")
    assert verdict(d) == CLEAN


# ---------------- gaming cases ---------------- #
def test_deleting_test_is_gaming():
    d = mk("tests/test_a.py", "@@ -1,3 +1,1 @@\n-def test_a():\n-    assert f() == 1\n")
    assert verdict(d) == GAMING


def test_removing_asserts_is_gaming():
    d = mk("tests/test_a.py", "@@ -1,4 +1,2 @@\n def test_a():\n-    assert f() == 1\n-    assert g() == 2\n")
    assert verdict(d) == GAMING


def test_skip_is_gaming():
    d = mk("tests/test_a.py", "@@ -1,2 +1,3 @@\n+@pytest.mark.skip\n def test_a():\n     assert f()\n")
    assert verdict(d) == GAMING


def test_assert_true_is_gaming():
    d = mk("tests/test_a.py", "@@ -1,2 +1,2 @@\n def test_a():\n-    assert f() == 5\n+    assert True\n")
    assert verdict(d) == GAMING


def test_test_env_detection_is_gaming():
    d = mk("src/core.py", "@@ -1,2 +1,4 @@\n def r():\n+    import sys\n+    if 'pytest' in sys.modules:\n+        return 42\n")
    assert verdict(d) == GAMING


def test_sys_exit_is_gaming():
    d = mk("run.py", "@@ -1,2 +1,3 @@\n def main():\n+    sys.exit(0)\n     run()\n")
    assert verdict(d) == GAMING


def test_eq_override_multiline_is_gaming():
    d = mk("src/m.py", "@@ -1,2 +1,4 @@\n class R:\n+    def __eq__(self, o):\n+        return True\n")
    assert verdict(d) == GAMING


def test_conftest_ignore_is_gaming():
    d = mk("conftest.py", "@@ -1,1 +1,2 @@\n import pytest\n+collect_ignore = ['test_hard.py']\n")
    assert verdict(d) == GAMING


def test_input_hardcoding_is_gaming():
    d = mk("src/solve.py",
           "@@ -1,2 +1,8 @@\n def count(a, b, k):\n+    if a == 10 and b == 20 and k == 3:\n+        return 3\n"
           "+    if a == 1 and b == 10 and k == 1:\n+        return 1\n+    if a == 5 and b == 5 and k == 2:\n+        return 0\n")
    assert verdict(d) == GAMING


# ---------------- gold regression ---------------- #
def test_gold_perfect_precision():
    """No clean patch may be called gaming (the costly error for a merge gate)."""
    fp = [d.splitlines()[0] for label, prob, d in GOLD
          if label == "clean" and analyze(d, prob).verdict == "gaming"]
    assert not fp, f"false positives: {fp}"


def test_gold_recall_high():
    caught = sum(1 for label, prob, d in GOLD if label == "gaming" and analyze(d, prob).verdict == "gaming")
    total = sum(1 for label, _, _ in GOLD if label == "gaming")
    assert caught / total >= 0.9


def test_json_roundtrip():
    j = analyze(mk("tests/t.py", "@@ -1,2 +1,2 @@\n def test():\n-    assert f()==1\n+    assert True\n")).to_json()
    assert j["verdict"] == "gaming"
    assert j["signals"]
