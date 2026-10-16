# stream2sentence 1.1.0

- New opt-in `AvailableTextRun` keeps already-queued later sentences together,
  avoiding a separate speech request for endings such as “though.”. The first
  fragment keeps its usual early release; later sentences may wait for normal
  sentence-end confirmation.
- Fix grouping that could hold back the next incomplete sentence. Preserve
  each queued input’s behavior and handle abbreviation and numeric tails.
- Recognize the Urdu full stop (۔) in sentence detection and default streaming
  delimiters while keeping known multi-dot Urdu abbreviations intact.
- Avoid repeatedly scanning the same queued text and unnecessary rule-based
  tokenizer scans on unpunctuated text.

Ordinary strings and `quick_yield_every_fragment=True` keep their existing behavior.
See [the example and integration guide](docs/available-text-runs.md).
