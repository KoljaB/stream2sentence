"""Run the quick unit tests; Stanza integration and timing scenarios are skipped."""
import os
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
# Live examples need an API; test_time_based.py runs in real time.
SKIPPED = {"test_stream_from_llm.py", "test_stream_from_llm_old_api.py", "test_time_based.py"}


def main():
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ.pop("STREAM2SENTENCE_RUN_STANZA_TESTS", None)
    start = time.perf_counter()
    suite = unittest.TestSuite()
    for path in sorted(TESTS.glob("test_*.py")):
        if path.name in SKIPPED:
            continue
        tests = unittest.defaultTestLoader.discover(str(TESTS), pattern=path.name)
        if tests.countTestCases() == 0:
            raise RuntimeError(f"No unittest cases discovered in {path.name}")
        suite.addTests(tests)

    result = unittest.TextTestRunner(verbosity=0).run(suite)
    print(f"seconds={time.perf_counter() - start:.1f}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
