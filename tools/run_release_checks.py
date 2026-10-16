"""Run every automated release check, including optional model integrations."""
import os
from pathlib import Path
import runpy
import subprocess
import sys
import unittest
from importlib.metadata import PackageNotFoundError, version

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
# These are interactive, live API examples, not automated test cases.
LIVE_EXAMPLES = {"test_stream_from_llm.py", "test_stream_from_llm_old_api.py"}


def main():
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ["STREAM2SENTENCE_RUN_STANZA_TESTS"] = "1"
    try:
        for package in ("emoji", "nltk", "stanza"):
            print(f"{package}={version(package)}", flush=True)
    except PackageNotFoundError as exc:
        print(f"Missing dependency: {exc}. Install with: python -m pip install -e \".[all]\"", file=sys.stderr)
        return 1

    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
    suite = unittest.TestSuite()
    for path in sorted(TESTS.glob("test_*.py")):
        if path.name in LIVE_EXAMPLES or path.name == "test_time_based.py":
            continue
        tests = unittest.defaultTestLoader.discover(str(TESTS), pattern=path.name)
        if tests.countTestCases() == 0:
            raise RuntimeError(f"No unittest cases discovered in {path.name}")
        suite.addTests(tests)
    if suite.countTestCases() == 0:
        raise RuntimeError("No tests discovered")

    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print(f"tests={result.testsRun} failures={len(result.failures)} "
          f"errors={len(result.errors)} skipped={len(result.skipped)}", flush=True)
    if not result.wasSuccessful() or result.skipped:
        return 1

    runpy.run_path(str(TESTS / "test_time_based.py"), run_name="__main__")
    print("All release checks passed, including four timing scenarios; zero skipped tests.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
