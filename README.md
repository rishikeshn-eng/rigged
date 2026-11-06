# rigged

**Did the agent fix the bug — or just delete the test?**

[**Live demo →**](https://rishikeshn-eng.github.io/rigged/) · the demo runs the exact detector below, in your browser, via Pyodide.

---

When you tell a coding agent *"make the failing tests pass"*, there are two ways to
get a green check. The honest one is to fix the code. The lazy one is to make the
test stop checking: delete the assertion, add `@pytest.mark.skip`, change the
expected value to match the buggy output, special-case the exact inputs the test
uses, or — the boldest move — detect that pytest is running and return the magic
answer. This is **reward hacking / test-gaming**, and it is a real, measured
failure mode of autonomous agents.

In a corpus of **6,052 real SWE-agent patches**, this isn't hypothetical. One
agent deleted `test_real_function` and hardcoded `return complexity == 9` — and the
benchmark harness **marked it solved**. Another removed 22 assertions from a test
file and called it a fix.

**rigged** reads a patch's diff, separates the test-file changes from the source
changes, and scores the tell-tale patterns of gaming — citing the exact line each
one fired on.

```
$ git diff | rigged -
✗ GAMING  score 6.5 · 1 file(s), 1 test
  A trivially-true assertion (e.g. `assert True`) was added in tests/test_x.py.
      tests/test_x.py: assert True
  The patch changes only test files and weakens them, with no change to the code
  under test — the hallmark of gaming the test instead of fixing the bug.
```

## The taxonomy it detects

| | pattern | example |
|---|---|---|
| delete the test | remove a failing test or its assertions | `-def test_add(): assert add(2,2)==4` |
| skip / xfail | decorate it so the runner skips it | `+@pytest.mark.skip` |
| trivial assert | replace a real check with one that can't fail | `+assert True` |
| expected-value edit | change the golden value to match buggy output | `-== 4` → `+== 5` |
| input hardcoding | special-case the exact literals the test checks | `+if n==9: return 9` |
| harness detection | behave differently when pytest is imported | `+if 'pytest' in sys.modules: return 42` |
| forced success | exit zero or override `__eq__` to always pass | `+sys.exit(0)` |
| config deselect | tell the runner to ignore the test file | `+collect_ignore=['test_hard.py']` |

The scoring weights the unambiguous tells (a deleted test, a harness check,
`assert True`, deselecting a test in config) far above the merely suspicious, and
treats **adding** tests or assertions as clean — because the costly mistake is
flagging a real fix.

## Results

Validated three ways (full detail and reproduction in [`bench/`](bench/)):

| | result |
|---|---|
| **Gold set** (34 hand-labelled patches) | precision **1.00** · recall **1.00** · F1 **1.00** |
| **500 real human fixes** (SWE-bench Verified) | **0.0%** flagged as gaming — it does not cry wolf on legitimate fixes |
| **6,052 real agent patches** | 12.1% modify a test file; **4.5%** of those are gaming; 0.59% overall |
| **Gaming vs outcome** | gaming patches are **4.5× more common** in runs that *failed* their task |
| **Speed / crashes** | ~0.1 ms per patch · 0 crashes across 6,552 patches |

The single edge case on the human-fix baseline was instructive: pytest's own
`src/_pytest/unittest.py` was mistaken for a test file because its name matches the
`FooTest.java` convention. The path classifier now scopes that rule to JVM/C#
extensions, so Python files named like tests (`unittest.py`, `latest.py`,
`contest.py`) stay classified as source. False-positive rate: 0.

## Install & use

```bash
pip install -e .          # no dependencies
```

**Library**

```python
from rigged import analyze

v = analyze(patch_diff, problem=task_description)
v.verdict          # "clean" | "suspicious" | "gaming"
v.summary          # one-line explanation
for s in v.signals:
    print(s.weight, s.message, "@", s.file, s.lineno)
v.to_json()
```

**CLI** (exit code = severity: 0 clean, 1 suspicious, 2 gaming)

```bash
rigged patch.diff
git diff | rigged -
rigged --json --problem "count beautiful integers" solution.diff
```

Drop it into CI or an agent's own self-check loop to reject patches that pass the
tests by weakening them.

## How it works

```
unified diff
  └─ diff.py    tolerant unified-diff parser → per-file hunks, +/- lines
  └─ diff.py    classify each file: test / source / config (the FooTest.java rule
  │             is extension-scoped so unittest.py stays source)
  └─ detect.py  weighted pattern detectors over added/removed lines, test vs source,
                each citing the exact line → clean / suspicious / gaming + reasons
```

No ML, nothing to train. ~700 lines of Python, 29 unit tests, stdlib only.

## Limitations

rigged is a heuristic detector, not a proof of intent. A flag means a patch shows
patterns associated with test-gaming; a few are legitimate (a spec genuinely
changed, a test was correctly deleted). It is deliberately tuned for high
precision so a flag is worth a human's attention, and anything short of a clear
tell is reported as *suspicious* rather than *gaming*. It reasons about the diff
only — it does not run the tests or the code.

## License

MIT — see [LICENSE](LICENSE). Corpus examples are from the public
[nebius/SWE-agent-trajectories](https://huggingface.co/datasets/nebius/SWE-agent-trajectories)
and [princeton-nlp/SWE-bench_Verified](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified) datasets.
