# stream2sentence 1.1.0

- Add opt-in `AvailableTextRun` to keep already-queued later sentences together, avoiding separate speech requests for short endings such as “though.” The first fragment keeps its usual early release; later sentences still need normal sentence-end confirmation.
- Fix queued-run boundaries after partial output, preserve each queued input’s behavior, and let incomplete following sentences keep their early-fragment behavior. Avoid repeated scans of the same queued text.
- Add word-based fragment lookahead (PR #16), preferring confirmed sentence endings over earlier soft delimiters. Harden abbreviation, decimal, and numeric-tail handling.
- Extend multilingual consensus boundaries (PR #17), including conservative checks for quoted text and numeric or abbreviation contexts. Recognize the Urdu full stop (۔) while preserving known multi-dot abbreviations.
- Preserve original separators when joining short sentences (PR #18), including adjacent multilingual text. Support custom tokenizers that return one-shot iterators.
- Make `SentenceSplitter.flush()` drain queued input and reset stream state, preventing duplicate output on repeated flushes or reuse. Preserve unprocessed queued input when a tokenizer fails so the caller can retry.
- Keep CJK closing punctuation with the preceding sentence, and cache Stanza pipelines by language so interleaved splitters use the correct model.
- Add a strict release-check command covering all automated tests, optional tokenizer integrations, and four timing scenarios. Timing comparisons now reject missing or extra output. Include the MIT license in source and wheel distributions.

Requires Python 3.10+. NLTK and Stanza remain optional extras.

Ordinary strings and `quick_yield_every_fragment=True` do not enable queued-sentence grouping. See [the example and integration guide](docs/available-text-runs.md) and [release checks](README.md#release-checks).
