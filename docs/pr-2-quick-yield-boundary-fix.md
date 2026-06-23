# Fix for #2: Context-Aware Quick-Yield Boundaries

The fix prevents quick-yield mode from splitting a streamed fragment when punctuation is still likely to belong to a number, currency amount, technical token, URL, abbreviation, or other non-sentence unit.

## Problem

`quick_yield_single_sentence_fragment` previously treated every configured fragment delimiter as safe to yield immediately. That made low-latency output fast, but it also meant partial tokens could be split too early.

Example:

```text
$3.
5
```

The period after `3` is not a sentence boundary; it is part of `$3.5`. The splitter needed a small amount of context before deciding whether punctuation ends a sentence.

## Implementation

The quick-yield boundary decision now lives in `stream2sentence/quick_yield_boundary.py`.

That detector returns one of three decisions:

- `SPLIT`: the delimiter is safe to yield as a sentence or fragment boundary.
- `REJECT`: the delimiter is part of the current token, so quick-yield must keep buffering.
- `HOLD`: there is not enough right-side context yet, so quick-yield waits for one more streamed character.

The main stream splitter stores a pending boundary when the detector returns `HOLD`. Once the next character arrives, it rechecks that same delimiter with the extra context. If the next character continues a token, the split is rejected. If it does not, the fragment is yielded up to the confirmed delimiter and the suffix remains in the buffer.

## Low-Context Behavior

The detector does not need a large context window. It uses:

- the current buffer to the left of the delimiter;
- the delimiter itself;
- at most one character of lookahead.

This keeps the behavior conservative when context is extremely low.

```text
Input so far: "$3."
Decision: HOLD

Next char: "5"
Decision: REJECT
Buffer remains: "$3.5"
```

```text
Input so far: "Hello."
Decision: HOLD

Next char: " "
Decision: SPLIT
Yielded text: "Hello."
```

If the stream ends while a delimiter is pending, the normal flush path tokenizes and yields the remaining buffer.

## Language Data

Language-specific data was moved into `stream2sentence/data/language_contexts.json`.

The JSON currently stores:

- language aliases, so configured language codes and names resolve consistently;
- language-specific abbreviations;
- generic currency symbols used by token-continuation checks.

The detector combines generic data with the configured language. This keeps the code small and makes future language-specific additions a data change rather than a code change.

## Cases Covered

The added tests cover cases where quick-yield should not split inside:

- decimal prices and local currency formats;
- thousands separators and decimal separators;
- time values and ranges;
- version numbers;
- package names and release identifiers;
- domain names, URLs, and email addresses;
- file names and paths;
- IP addresses and network identifiers;
- command-line flags and technical tokens;
- local abbreviations;
- metrics, percentages, and temperatures;
- multilingual examples for Mandarin, Hindi, Spanish, French, Arabic, Portuguese, Russian, German, Japanese, and Turkish.

## Verification

The following checks passed after the change:

```powershell
.\.venv\Scripts\python.exe -m py_compile stream2sentence\quick_yield_boundary.py stream2sentence\stream2sentence.py tests\test_stream2sentence.py tests\test_stream_from_llm.py tests\test_stream_from_llm_old_api.py
.\.venv\Scripts\python.exe -m unittest -k quick_yield tests.test_stream2sentence
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Final full discovery result:

```text
Ran 168 tests in 92.627s
OK (skipped=2)
```

The two skipped tests are live OpenAI stream smoke scripts and are skipped when the optional `openai` package or `OPENAI_API_KEY` is unavailable.
