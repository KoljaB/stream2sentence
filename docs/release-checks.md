# Release checks

From a source checkout, use an activated virtual environment:

```bash
python -m pip install -e ".[all]" build twine
python tools/run_release_checks.py
python -m build
python -m twine check --strict dist/stream2sentence-1.1.2*
```

The runner checks dependencies, runs all unit tests with real NLTK and Stanza integrations enabled, and runs four timing scenarios. It fails on any failed or skipped test, missing output, text mismatch, or timing outside the allowed tolerance. First use needs network access for model data; the full run takes several minutes. The two live LLM API examples are manual demos and are not part of this automated suite. On Windows, `tests/run_test.bat` runs the same checks using the project virtual environment when present.

Passing these checks is release evidence, not a claim of complete code coverage or bug-free behavior. See [the 1.1.2 release notes](../RELEASE_NOTES.md).
