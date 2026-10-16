# stream2sentence 1.1.0

- adds opt-in `AvailableTextRun` to keep queued later sentences together while preserving early output for the first fragment
- improves multilingual sentence boundaries, Urdu punctuation, and Chinese/Japanese spacing (#16, #17, #18)
- fixes Stanza language selection when using multiple languages
- fixes duplicate output after `flush()` and preserves queued text when tokenization fails
- supports custom tokenizers returning iterators
- adds complete release checks and includes the MIT license in both package formats
