"""rigged — detect when a code patch games the tests instead of fixing the bug."""
from .detect import analyze, Verdict, Signal, CLEAN, SUSPICIOUS, GAMING  # noqa: F401
from .diff import parse_diff, classify_path  # noqa: F401
__version__ = "0.1.0"
__all__ = ["analyze", "Verdict", "Signal", "parse_diff", "classify_path",
           "CLEAN", "SUSPICIOUS", "GAMING"]
